"""Mémoire persistante locale de MILES.

Stocke des souvenirs explicites et des préférences utilisateur dans une base
SQLite sur la machine de l'utilisateur. Aucun envoi vers un fournisseur distant.
Le stockage de souvenirs est exclusivement à la demande de l'utilisateur :
aucune conversation n'est enregistrée automatiquement.

Thread-safe : la connexion SQLite est partagée entre threads (check_same_thread=False)
et protégée par un verrou réentrant (RLock) car get_context_memories appelle
list_memories en interne.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
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

    SCHEMA_VERSION = 3

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
        self._lock = threading.RLock()

        if self.enabled:
            self._initialize()

    # --- Cycle de vie ---

    def _initialize(self) -> None:
        """Créer le répertoire et la base si nécessaire, vérifier l'intégrité."""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
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
                owner_user_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Migration : une base créée avant la version 2 (souvenirs rattachés
        # à un propriétaire) ne possède pas la colonne owner_user_id. Les
        # souvenirs existants restent sans propriétaire : ils sont partagés
        # (visibles par tous) plutôt qu'attribués arbitrairement à quelqu'un.
        columns = {
            str(row[1])
            for row in cursor.execute("PRAGMA table_info(memories)").fetchall()
        }
        if "owner_user_id" not in columns:
            cursor.execute(
                "ALTER TABLE memories ADD COLUMN owner_user_id "
                "TEXT NOT NULL DEFAULT ''"
            )
        # Migration v3 (spécification MEMOIRE_AVANCEE) : type de savoir et
        # liens entre souvenirs. Ajouts NON destructifs ; le défaut
        # 'inconnu' conserve le comportement historique (rien n'est prouvé).
        if "kind" not in columns:
            cursor.execute(
                "ALTER TABLE memories ADD COLUMN kind "
                "TEXT NOT NULL DEFAULT 'inconnu'"
            )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relation TEXT NOT NULL,
                confidence TEXT NOT NULL DEFAULT 'signale',
                created_at TEXT NOT NULL,
                UNIQUE(source_id, target_id, relation)
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
        with self._lock:
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

    #: Valeurs autorisées pour le type de savoir (spéc. MEMOIRE_AVANCEE).
    KINDS = ("inconnu", "fait", "hypothese")

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 1,
        owner_user_id: str = "",
        kind: str = "inconnu",
    ) -> int:
        """Enregistrer un souvenir explicite.

        Args:
            content: texte du souvenir.
            category: catégorie libre (ex. "travail", "personnel").
            importance: niveau d'importance (1 par défaut).
            owner_user_id: propriétaire du souvenir. La chaîne vide
                désigne un souvenir **partagé** (console locale) : il est
                visible par tous mais n'est attribué à personne.
            kind: type de savoir — 'inconnu' (défaut honnête, rien n'est
                prouvé), 'fait' (uniquement promotion humaine via /fait),
                'hypothese' (proposition explicite).

        Returns:
            l'identifiant du souvenir créé.

        Raises:
            PersistentMemoryError: si la mémoire est désactivée/indisponible,
                                   le contenu contient un secret, ou kind invalide.
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

        if kind not in self.KINDS:
            raise PersistentMemoryError(
                f"Type de savoir invalide : {kind!r} (valeurs : {', '.join(self.KINDS)})."
            )

        if self._contains_secret(content):
            raise PersistentMemoryError(
                "Le souvenir contient un mot probable (clé API, mot de passe, token). "
                "Enregistrement refusé."
            )

        now = self._now_iso()
        with self._lock:
            assert self._conn is not None
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO memories (
                    content, category, importance, owner_user_id, kind,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content.strip(),
                    category,
                    int(importance),
                    str(owner_user_id or ""),
                    kind,
                    now,
                    now,
                ),
            )
            mem_id = int(cursor.lastrowid)
            # Règles strictes de détection (spéc. §4) : jamais d'affirmation,
            # uniquement des liens marqués 'signale'.
            self._detecter_liens(cursor, mem_id, content.strip(),
                                 str(owner_user_id or ""), now)
            self._conn.commit()
            return mem_id

    @staticmethod
    def _normaliser(texte: str) -> str:
        """Forme canonique (minuscules, sans accents, espaces simples)."""
        import unicodedata
        brut = str(texte).lower().strip().rstrip(".")
        sans_accents = "".join(
            c for c in unicodedata.normalize("NFKD", brut)
            if not unicodedata.combining(c)
        )
        return " ".join(sans_accents.split())

    @classmethod
    def _sans_negation(cls, texte: str) -> str:
        """Retirer les marqueurs de négation (règle STRICTE de la spec).

        Deux phrases identiques après ce traitement, mais différentes à
        l'origine, sont signalées comme potentiellement contradictoires —
        JAMAIS comme un fait confirmé.
        """
        t = cls._normaliser(texte)
        for marqueur in ("ne ", "n'", "pas ", "jamais ", "plus "):
            t = t.replace(marqueur, " ")
        return " ".join(t.split())

    def _detecter_liens(self, cursor: Any, mem_id: int, contenu: str,
                        owner: str, now: str) -> None:
        """Détecter duplique/contradit avec les souvenirs VISIBLES (lecture stricte).

        Visibilité : mêmes règles que list_memories (même propriétaire ou partagé).
        Les liens sont toujours créés avec confidence='signale' : la machine
        propose, un humain confirme (commande /confirmer).
        """
        if owner:
            candidats = cursor.execute(
                "SELECT id, content FROM memories "
                "WHERE id != ? AND (owner_user_id = ? OR owner_user_id = '')",
                (mem_id, owner),
            ).fetchall()
        else:
            candidats = cursor.execute(
                "SELECT id, content FROM memories WHERE id != ?",
                (mem_id,),
            ).fetchall()
        norm = self._normaliser(contenu)
        norm_sans_neg = self._sans_negation(contenu)
        for autre_id, autre in candidats:
            autre_norm = self._normaliser(autre)
            relation = None
            if autre_norm == norm:
                relation = "duplique"
            elif (autre_norm != norm
                    and self._sans_negation(autre) == norm_sans_neg):
                relation = "contradit"
            if relation:
                cursor.execute(
                    "INSERT OR IGNORE INTO memory_links "
                    "(source_id, target_id, relation, confidence, created_at) "
                    "VALUES (?, ?, ?, 'signale', ?)",
                    (min(mem_id, autre_id), max(mem_id, autre_id),
                     relation, now),
                )

    def list_links(
        self,
        relation: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lister les liens (contradictions/dupliqués) visibles.

        Visibilité : les DEUX extrémités doivent être visibles pour
        l'appelant (souvenirs de l'utilisateur ou partagés). Les liens
        entre souvenirs d'un autre utilisateur ne sont jamais exposés.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )
        conditions = []
        valeurs: list[Any] = []
        if relation is not None:
            conditions.append("l.relation = ?")
            valeurs.append(relation)
        if owner_user_id is not None:
            conditions.append(
                "(s.owner_user_id = ? OR s.owner_user_id = '') "
                "AND (t.owner_user_id = ? OR t.owner_user_id = '')"
            )
            valeurs.extend([str(owner_user_id), str(owner_user_id)])
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._lock:
            assert self._conn is not None
            rows = self._conn.execute(
                f"""
                SELECT l.id, l.source_id, l.target_id, l.relation,
                       l.confidence, l.created_at,
                       s.content AS source_content,
                       t.content AS target_content
                FROM memory_links l
                JOIN memories s ON s.id = l.source_id
                JOIN memories t ON t.id = l.target_id
                {where}
                ORDER BY l.created_at DESC
                """,
                tuple(valeurs),
            ).fetchall()
        return [dict(row) for row in rows]

    def confirm_link(self, link_id: int, owner_user_id: str | None = None) -> bool:
        """Confirmer humainement un lien (confidence 'signale' -> 'confirme').

        Refuse si l'appelant ne voit pas les deux extrémités (isolation).
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )
        with self._lock:
            assert self._conn is not None
            row = self._conn.execute(
                """
                SELECT l.id FROM memory_links l
                JOIN memories s ON s.id = l.source_id
                JOIN memories t ON t.id = l.target_id
                WHERE l.id = ?
                  AND (? IS NULL OR (s.owner_user_id = ? OR s.owner_user_id = ''))
                  AND (? IS NULL OR (t.owner_user_id = ? OR t.owner_user_id = ''))
                """,
                (link_id, owner_user_id, owner_user_id,
                 owner_user_id, owner_user_id),
            ).fetchone()
            if row is None:
                return False
            cursor = self._conn.execute(
                "UPDATE memory_links SET confidence = 'confirme' WHERE id = ?",
                (link_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def set_kind(
        self, memory_id: int, kind: str, owner_user_id: str | None = None
    ) -> bool:
        """Changer le type de savoir d'un souvenir ('fait' ou 'hypothese').

        Promotion en 'fait' : UNIQUEMENT par appel humain explicite (spec §3).
        Refusé si l'appelant ne voit pas le souvenir.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )
        if kind not in ("fait", "hypothese"):
            raise PersistentMemoryError(
                f"Type non autorisé ici : {kind!r} (fait ou hypothese)."
            )
        with self._lock:
            assert self._conn is not None
            cursor = self._conn.execute(
                """
                UPDATE memories SET kind = ?, updated_at = ?
                WHERE id = ?
                  AND (? IS NULL OR owner_user_id = ? OR owner_user_id = '')
                """,
                (kind, self._now_iso(), memory_id,
                 owner_user_id, owner_user_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def resume_memoire(memoires: list[dict[str, Any]],
                       max_car: int = 2000) -> str:
        """Rappel compact TOUT COURT (spéc §5) — fonction pure, aucun réseau.

        Ordre : faits d'abord, puis hypothèses, puis inconnus (partagés
        compris), chaque souvenir marqué [fait]/[hypothèse]/[?], contenu
        tronqué à max_car (le appelant applique aussi ses propres bornes).
        """
        ordre = {"fait": 0, "hypothese": 1, "inconnu": 2}
        tri = sorted(
            memoires, key=lambda m: (ordre.get(str(m.get("kind", "inconnu")), 3), -int(m.get("importance", 1) or 1))
        )
        morceaux: list[str] = []
        total = 0
        for m in tri:
            kind = str(m.get("kind", "inconnu"))
            marque = {"fait": "[fait] ", "hypothese": "[hypothèse] "}.get(kind, "")
            morceau = f"{marque}{m.get('content', '')}"
            if total + len(morceau) > max_car:
                break
            morceaux.append(morceau)
            total += len(morceau)
        return "\n".join(morceaux)

    def list_memories(
        self,
        category: str | None = None,
        limit: int | None = None,
        owner_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lister les souvenirs enregistrés.

        Args:
            category: filtrer par catégorie (optionnel).
            limit: nombre max de souvenirs retournés (optionnel).
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur **et** les souvenirs partagés (sans
                propriétaire) sont retournés : c'est l'isolation entre
                utilisateurs.

        Returns:
            liste de dictionnaires {id, content, category, importance,
            owner_user_id, created_at, updated_at}.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        with self._lock:
            assert self._conn is not None
            cursor = self._conn.cursor()
            conditions = []
            valeurs: list[Any] = []
            if category is not None:
                conditions.append("category = ?")
                valeurs.append(category)
            if owner_user_id is not None:
                conditions.append("(owner_user_id = ? OR owner_user_id = '')")
                valeurs.append(str(owner_user_id))
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            valeurs.append(limit if limit is not None else -1)
            rows = cursor.execute(
                f"""
                SELECT id, content, category, importance, owner_user_id,
                       kind, created_at, updated_at
                FROM memories
                {where}
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
                """,
                tuple(valeurs),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_memory(
        self, memory_id: int, owner_user_id: str | None = None
    ) -> dict[str, Any] | None:
        """Retourner un souvenir par son identifiant, ou None.

        Args:
            memory_id: identifiant du souvenir.
            owner_user_id: si fourni, le souvenir n'est retourné que s'il
                appartient à cet utilisateur ou s'il est partagé.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        with self._lock:
            assert self._conn is not None
            if owner_user_id is None:
                row = self._conn.execute(
                    """
                    SELECT id, content, category, importance, owner_user_id,
                           created_at, updated_at
                    FROM memories
                    WHERE id = ?
                    """,
                    (memory_id,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    """
                    SELECT id, content, category, importance, owner_user_id,
                           created_at, updated_at
                    FROM memories
                    WHERE id = ? AND (owner_user_id = ? OR owner_user_id = '')
                    """,
                    (memory_id, str(owner_user_id)),
                ).fetchone()
        return dict(row) if row is not None else None

    def delete_memory(
        self, memory_id: int, owner_user_id: str | None = None
    ) -> bool:
        """Supprimer un souvenir ciblé. Retourne True si supprimé.

        Args:
            memory_id: identifiant du souvenir.
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur (ou partagés) peuvent être supprimés.
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        with self._lock:
            assert self._conn is not None
            cursor = self._conn.cursor()
            if owner_user_id is None:
                cursor.execute(
                    "DELETE FROM memories WHERE id = ?", (memory_id,)
                )
            else:
                cursor.execute(
                    "DELETE FROM memories "
                    "WHERE id = ? AND (owner_user_id = ? OR owner_user_id = '')",
                    (memory_id, str(owner_user_id)),
                )
            self._conn.commit()
            return cursor.rowcount > 0

    def clear_all_memories(self, owner_user_id: str | None = None) -> int:
        """Effacer les souvenirs. Retourner le nombre supprimé.

        Args:
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur sont effacés (les souvenirs partagés — sans
                propriétaire — ne sont pas touchés). Sans filtre, tous
                les souvenirs sont effacés (comportement historique).
        """
        if not self.is_available:
            raise PersistentMemoryError(
                "Mémoire persistante indisponible ou désactivée."
            )

        with self._lock:
            assert self._conn is not None
            cursor = self._conn.cursor()
            if owner_user_id is None:
                cursor.execute("DELETE FROM memories")
            else:
                cursor.execute(
                    "DELETE FROM memories WHERE owner_user_id = ?",
                    (str(owner_user_id),),
                )
            self._conn.commit()
            return cursor.rowcount

    def get_context_memories(
        self, owner_user_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Retourner les souvenirs les plus pertinents pour le contexte IA.

        Respecte max_memories_in_context et max_content_length.

        Args:
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur (et les partagés) sont retournés — isolation
                entre utilisateurs en contexte IA.
        """
        if not self.is_available:
            return []

        memories = self.list_memories(
            limit=self.max_memories_in_context, owner_user_id=owner_user_id
        )
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
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            assert self._conn is not None
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM preferences WHERE key = ?", (key,))
            self._conn.commit()
            return cursor.rowcount > 0

    def __enter__(self) -> "PersistentMemory":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
