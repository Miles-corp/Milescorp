"""Mémoire persistante locale de MILES.

Stocke des souvenirs explicites et des préférences utilisateur dans une base
SQLite sur la machine de l'utilisateur. Aucun envoi vers un fournisseur distant.
Le stockage de souvenirs est exclusivement à la demande de l'utilisateur :
aucune conversation n'est enregistrée automatiquement.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any


class PersistentMemoryError(Exception):
    """Erreur liée à la mémoire persistante."""


class PersistentMemory:
    """Mémoire persistante locale (SQLite).

    Attributs:
        enabled: si False, toutes les opérations sont des no-op avec un message
                 d'information.
        db_path: chemin du fichier de base de données SQLite.
        max_memories_in_context: nombre max de souvenirs retournés pour le
                                 contexte IA.
        max_content_length: longueur max du contenu d'un souvenir.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        enabled: bool = False,
        db_path: str | None = None,
        max_memories_in_context: int = 5,
        max_content_length: int = 1000,
    ) -> None:
        self.enabled = enabled
        self.db_path = db_path or os.path.join("data", "memory.db")
        self.max_memories_in_context = max_memories_in_context
        self.max_content_length = max_content_length
        self._conn: sqlite3.Connection | None = None
        self._available = False

        if self.enabled:
            self._initialize()

    # --- Cycle de vie ---

    def _initialize(self) -> None:
        """Créer le répertoire et la base si nécessaire, vérifier l'intégrité."""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._create_schema()
            self._available = True
        except (sqlite3.Error, OSError) as exc:
            self._available = False
            self._conn = None
            # Dégradation gracieuse : base corrompue ou inaccessible,
            # la mémoire est simplement indisponible, aucune exception levée.

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
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                importance INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Migration : garantir que la version est à jour
        row = cursor.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (self.SCHEMA_VERSION,),
            )
        elif row[0] < self.SCHEMA_VERSION:
            # Aucune migration destructive pour l'instant
            cursor.execute(
                "UPDATE schema_version SET version = ?",
                (self.SCHEMA_VERSION,),
            )
        self._conn.commit()

    def close(self) -> None:
        """Fermer la connexion à la base de données."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._available = False

    @property
    def is_available(self) -> bool:
        """Retourner True si la mémoire persistante est opérationnelle."""
        return self.enabled and self._available and self._conn is not None

    # --- Vidéos de sécurité ---

    def _contains_secret(self, text: str) -> bool:
        """Détecter des motifs de secrets (clés API, mots de passe, tokens)."""
        lowered = text.lower()
        suspicious = [
            "sk-",
            "api_key",
            "password",
            "secret",
            "token",
            "secret_key",
            "private_key",
        ]
        return any(motif in lowered for motif in suspicious)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- Mémoires explicites ---

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
    ) -> int:
        """Enregistrer un souvenir explicite.

        Args:
            content: texte du souvenir.
            category: catégorie libre (ex. "travail", "personnel").
            importance: niveau d'importance (1 par défaut).

        Returns:
            l'identifiant du souvenir créé.

        Raises:
            PersistentMemoryError: si la mémoire est désactivée/indisponible,
                                   ou si le contenu contient un secret.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        if not content or not content.strip():
            raise PersistentMemoryError("Le contenu du souvenir ne peut pas être vide.")

        if len(content) > self.max_content_length:
            raise PersistentMemoryError(
                f"Le souvenir dépasse {self.max_content_length} caractères."
            )

        if self._contains_secret(content):
            raise PersistentMemoryError(
                "Le souvenir contient un mot probable (clé API, mot de passe, token). "
                "Enregistrement refusé."
            )

        now = self._now_iso()
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (content, category, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (content.strip(), category, int(importance), now, now),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def list_memories(
        self,
        category: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Lister les souvenirs enregistrés.

        Args:
            category: filtrer par catégorie (optionnel).
            limit: nombre max de souvenirs retournés (optionnel).

        Returns:
            liste de dictionnaires {id, content, category, importance, created_at, updated_at}.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        assert self._conn is not None
        cursor = self._conn.cursor()
        if category is not None:
            rows = cursor.execute(
                """
                SELECT id, content, category, importance, created_at, updated_at
                FROM memories
                WHERE category = ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (category, limit if limit is not None else -1),
            ).fetchall()
        else:
            rows = cursor.execute(
                """
                SELECT id, content, category, importance, created_at, updated_at
                FROM memories
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                (limit if limit is not None else -1,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_memory(self, memory_id: int) -> dict[str, Any] | None:
        """Retourner un souvenir par son identifiant, ou None."""
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        assert self._conn is not None
        row = self._conn.execute(
            """
            SELECT id, content, category, importance, created_at, updated_at
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def delete_memory(self, memory_id: int) -> bool:
        """Supprimer un souvenir ciblé. Retourner True si supprimé."""
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def clear_all_memories(self) -> int:
        """Effacer tous les souvenirs. Retourner le nombre supprimé."""
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM memories")
        self._conn.commit()
        return cursor.rowcount

    def get_context_memories(self) -> list[dict[str, Any]]:
        """Retourner les souvenirs les plus pertinents pour le contexte IA.

        Respecte max_memories_in_context et max_content_length.
        """
        if not self.is_available:
            return []

        memories = self.list_memories(limit=self.max_memories_in_context)
        # Tronquer le contenu si nécessaire
        for m in memories:
            if len(m.get("content", "")) > self.max_content_length:
                m["content"] = m["content"][: self.max_content_length] + "…"
        return memories

    # --- Préférences ---

    def set_preference(self, key: str, value: str) -> None:
        """Définir une préférence utilisateur."""
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )
        if self._contains_secret(value):
            raise PersistentMemoryError(
                "La préférence contient un mot probable (clé, mot de passe, token). "
                "Enregistrement refusé."
            )
        now = self._now_iso()
        assert self._conn is not None
        self._conn.execute(
            """
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        self._conn.commit()

    def get_preference(self, key: str) -> str | None:
        """Retourner une préférence, ou None."""
        if not self.is_available:
            return None
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else None

    def delete_preference(self, key: str) -> bool:
        """Supprimer une préférence. Retourner True si supprimée."""
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM preferences WHERE key = ?", (key,))
        self._conn.commit()
        return cursor.rowcount > 0

    def __enter__(self) -> "PersistentMemory":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
