"""Persistance locale des conversations MILES.

Stocke les transcriptions de conversation dans une base SQLite locale afin
que l'historique survive à un redémarrage du programme.

Ce module est distinct de la « mémoire persistante » de souvenirs
(``app/memory/persistent.py``) : il ne s'agit pas d'une mémoire sémantique de
type RAG, mais de l'historique fidèle des échanges, par conversation.

Garanties :
- aucune clé API, aucun mot de passe et aucun jeton n'est écrit sur disque
  (le contenu est expurgé avant écriture) ;
- l'ordre des messages est garanti par un numéro de séquence unique par
  conversation ;
- une base absente, corrompue ou inaccessible n'empêche pas le programme de
  démarrer : la persistance est simplement désactivée.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.utilities.redaction import sanitize_text

#: Rôles autorisés dans une transcription.
VALID_ROLES = ("user", "assistant", "system")


class TranscriptError(Exception):
    """Erreur liée à la persistance des conversations."""


class ConversationTranscript:
    """Stockage local des transcriptions de conversation (SQLite).

    Attributs :
        db_path : chemin du fichier de base de données SQLite.
        enabled : si False, toutes les opérations sont des no-op.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        enabled: bool = False,
        db_path: str | None = None,
    ) -> None:
        self.enabled = enabled
        self.db_path = db_path or os.path.join("data", "conversations.db")
        self._conn: Optional[sqlite3.Connection] = None
        self._available = False
        self._lock = threading.RLock()

        if self.enabled:
            self._initialize()

    # --- Cycle de vie ---

    def _initialize(self) -> None:
        """Créer la base si nécessaire. Ne lève pas d'exception en cas d'échec."""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._create_schema()
            self._available = True
        except (sqlite3.Error, OSError):
            # Dégradation gracieuse : la persistance est désactivée, le
            # programme continue à fonctionner en mémoire seule.
            self._available = False
            self._conn = None

    def _create_schema(self) -> None:
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transcript_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (conversation_id, sequence),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transcript_messages_conversation
            ON transcript_messages (conversation_id, sequence)
            """
        )
        row = cursor.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (self.SCHEMA_VERSION,),
            )
        elif row[0] < self.SCHEMA_VERSION:
            cursor.execute(
                "UPDATE schema_version SET version = ?",
                (self.SCHEMA_VERSION,),
            )
        self._conn.commit()

    def close(self) -> None:
        """Fermer la connexion à la base de données."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                self._available = False

    @property
    def is_available(self) -> bool:
        """Indiquer si la persistance est opérationnelle."""
        return self.enabled and self._available and self._conn is not None

    def __enter__(self) -> "ConversationTranscript":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- Conversations ---

    def create_conversation(self, title: str = "") -> Optional[str]:
        """Créer une conversation et retourner son identifiant.

        Retourne None si la persistance est indisponible.
        """
        if not self.is_available:
            return None
        conversation_id = uuid.uuid4().hex
        now = self._now_iso()
        with self._lock:
            assert self._conn is not None
            try:
                self._conn.execute(
                    """
                    INSERT INTO conversations (id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (conversation_id, title, now, now),
                )
                self._conn.commit()
            except sqlite3.Error:
                return None
        return conversation_id

    def list_conversations(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lister les conversations récentes (les plus récentes d'abord)."""
        if not self.is_available:
            return []
        with self._lock:
            assert self._conn is not None
            try:
                rows = self._conn.execute(
                    """
                    SELECT c.id, c.title, c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM transcript_messages m
                             WHERE m.conversation_id = c.id) AS message_count
                    FROM conversations c
                    ORDER BY c.updated_at DESC, c.rowid DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.Error:
                return []
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        """Retourner les métadonnées d'une conversation, ou None."""
        if not self.is_available:
            return None
        with self._lock:
            assert self._conn is not None
            try:
                row = self._conn.execute(
                    """
                    SELECT id, title, created_at, updated_at
                    FROM conversations WHERE id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
            except sqlite3.Error:
                return None
        return dict(row) if row is not None else None

    def get_last_conversation_id(self) -> Optional[str]:
        """Retourner l'identifiant de la conversation la plus récente."""
        conversations = self.list_conversations(limit=1)
        if not conversations:
            return None
        return str(conversations[0]["id"])

    def delete_conversation(self, conversation_id: str) -> bool:
        """Supprimer une conversation et tous ses messages."""
        if not self.is_available:
            return False
        with self._lock:
            assert self._conn is not None
            try:
                cursor = self._conn.execute(
                    "DELETE FROM transcript_messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                self._conn.execute(
                    "DELETE FROM conversations WHERE id = ?",
                    (conversation_id,),
                )
                self._conn.commit()
            except sqlite3.Error:
                return False
            return cursor.rowcount > 0

    # --- Messages ---

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Optional[int]:
        """Enregistrer un message dans une conversation.

        Le contenu est expurgé de tout secret détectable avant écriture.

        Retourne l'identifiant du message enregistré, ou None si la
        persistance est indisponible ou si l'écriture a échoué.
        """
        if not self.is_available:
            return None
        if not conversation_id:
            return None
        if role not in VALID_ROLES:
            raise TranscriptError(
                f"Rôle invalide : {role!r}. Rôles acceptés : {VALID_ROLES}"
            )

        safe_content = sanitize_text(content)
        now = self._now_iso()

        with self._lock:
            assert self._conn is not None
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                    FROM transcript_messages WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
                sequence = int(row["next_sequence"])
                cursor = self._conn.execute(
                    """
                    INSERT INTO transcript_messages
                        (conversation_id, sequence, role, content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conversation_id, sequence, role, safe_content, now),
                )
                self._conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
                self._conn.commit()
                return int(cursor.lastrowid)
            except sqlite3.Error:
                try:
                    self._conn.rollback()
                except sqlite3.Error:
                    pass
                return None

    def load_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        """Charger les messages d'une conversation, dans l'ordre d'écriture."""
        if not self.is_available:
            return []
        with self._lock:
            assert self._conn is not None
            try:
                rows = self._conn.execute(
                    """
                    SELECT id, conversation_id, sequence, role, content, created_at
                    FROM transcript_messages
                    WHERE conversation_id = ?
                    ORDER BY sequence ASC
                    """,
                    (conversation_id,),
                ).fetchall()
            except sqlite3.Error:
                return []
        return [dict(row) for row in rows]

    def count_messages(self, conversation_id: str) -> int:
        """Compter les messages d'une conversation."""
        if not self.is_available:
            return 0
        with self._lock:
            assert self._conn is not None
            try:
                row = self._conn.execute(
                    """
                    SELECT COUNT(*) AS total FROM transcript_messages
                    WHERE conversation_id = ?
                    """,
                    (conversation_id,),
                ).fetchone()
            except sqlite3.Error:
                return 0
        return int(row["total"])

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
