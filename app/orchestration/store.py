"""Persistance locale des missions MILES.

Les missions (objectif, plan, étapes, résultats, erreurs, horodatages,
demandes d'autorisation en attente) sont conservées dans une base SQLite
locale afin de pouvoir consulter l'état d'une mission après un
redémarrage.

Garanties :
- aucune clé API, aucun mot de passe et aucun jeton n'est écrit sur disque
  (le contenu est expurgé avant écriture) ;
- une base absente, corrompue ou inaccessible n'empêche pas le programme
  de démarrer : la persistance est simplement désactivée ;
- les missions sont écrites dans une transaction unique : une mission
  n'est jamais à moitié écrite.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Optional

from app.orchestration.models import Mission
from app.utilities.redaction import sanitize_text

logger = logging.getLogger("miles.orchestration")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


class MissionStore:
    """Stockage local des missions (SQLite).

    Attributs :
        enabled : si False, toutes les opérations sont des no-op.
        db_path : chemin du fichier de base de données SQLite.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        enabled: bool = False,
        db_path: Optional[str] = None,
    ) -> None:
        self.enabled = enabled
        self.db_path = db_path or os.path.join("data", "missions.db")
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

            self._conn = sqlite3.connect(
                self.db_path, check_same_thread=False, isolation_level=None
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._create_schema()
            self._available = True
        except (sqlite3.Error, OSError):
            logger.warning(
                "Persistance des missions indisponible : le programme continue "
                "sans enregistrement des missions."
            )
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
            CREATE TABLE IF NOT EXISTS missions (
                id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                state TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                planner TEXT NOT NULL DEFAULT '',
                planner_note TEXT NOT NULL DEFAULT '',
                plan_json TEXT NOT NULL DEFAULT '{}',
                facts_json TEXT NOT NULL DEFAULT '[]',
                errors_json TEXT NOT NULL DEFAULT '[]',
                unfinished_json TEXT NOT NULL DEFAULT '[]',
                pending_json TEXT,
                report TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                kind TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (mission_id) REFERENCES missions(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mission_events_mission
            ON mission_events (mission_id)
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

    def __enter__(self) -> "MissionStore":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # --- Missions ---

    def save(self, mission: Mission) -> bool:
        """Enregistrer (ou mettre à jour) une mission.

        Retourne True si l'écriture a réussi.
        """
        if not self.is_available:
            return False
        payload = mission.to_dict()
        plan_json = json.dumps(payload.get("plan") or {}, default=str)
        facts_json = json.dumps(payload.get("facts") or [], default=str)
        errors_json = json.dumps(payload.get("errors") or [], default=str)
        unfinished_json = json.dumps(payload.get("unfinished") or [], default=str)
        pending_json = (
            json.dumps(payload.get("pending"), default=str)
            if payload.get("pending")
            else None
        )

        with self._lock:
            assert self._conn is not None
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute(
                    """
                    INSERT INTO missions (
                        id, objective, state, session_id, planner, planner_note,
                        plan_json, facts_json, errors_json, unfinished_json,
                        pending_json, report, created_at, updated_at,
                        started_at, finished_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        objective = excluded.objective,
                        state = excluded.state,
                        session_id = excluded.session_id,
                        planner = excluded.planner,
                        planner_note = excluded.planner_note,
                        plan_json = excluded.plan_json,
                        facts_json = excluded.facts_json,
                        errors_json = excluded.errors_json,
                        unfinished_json = excluded.unfinished_json,
                        pending_json = excluded.pending_json,
                        report = excluded.report,
                        updated_at = excluded.updated_at,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at
                    """,
                    (
                        payload["mission_id"],
                        sanitize_text(payload["objective"]),
                        payload["state"],
                        payload["session_id"],
                        payload["planner"],
                        sanitize_text(payload["planner_note"]),
                        plan_json,
                        facts_json,
                        errors_json,
                        unfinished_json,
                        pending_json,
                        sanitize_text(payload["report"]),
                        payload["created_at"],
                        payload["updated_at"],
                        payload["started_at"],
                        payload["finished_at"],
                    ),
                )
                self._conn.commit()
                return True
            except sqlite3.Error:
                try:
                    self._conn.rollback()
                except sqlite3.Error:
                    pass
                logger.warning(
                    "Echec de l'enregistrement de la mission : ecriture "
                    "impossible."
                )
                return False

    def load(self, mission_id: str) -> Optional[Mission]:
        """Charger une mission par identifiant, ou None."""
        if not self.is_available:
            return None
        with self._lock:
            assert self._conn is not None
            try:
                row = self._conn.execute(
                    "SELECT * FROM missions WHERE id = ?", (mission_id,)
                ).fetchone()
            except sqlite3.Error:
                return None
        if row is None:
            return None

        def _json(value: Any, default: Any) -> Any:
            try:
                return json.loads(value) if value else default
            except (TypeError, ValueError):
                return default

        data = {
            "mission_id": row["id"],
            "objective": row["objective"],
            "state": row["state"],
            "session_id": row["session_id"],
            "planner": row["planner"],
            "planner_note": row["planner_note"],
            "plan": _json(row["plan_json"], None),
            "facts": _json(row["facts_json"], []),
            "errors": _json(row["errors_json"], []),
            "unfinished": _json(row["unfinished_json"], []),
            "pending": _json(row["pending_json"], None),
            "report": row["report"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }
        try:
            return Mission.from_dict(data)
        except (ValueError, TypeError):
            logger.warning(
                "Mission %s illisible : elle est ignoree.", mission_id
            )
            return None

    def list_missions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lister les missions récentes (les plus récentes d'abord)."""
        if not self.is_available:
            return []
        with self._lock:
            assert self._conn is not None
            try:
                rows = self._conn.execute(
                    """
                    SELECT id, objective, state, planner, created_at, updated_at,
                           finished_at
                    FROM missions
                    ORDER BY created_at DESC, rowid DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.Error:
                return []
        return [dict(row) for row in rows]

    def delete(self, mission_id: str) -> bool:
        """Supprimer une mission et ses événements."""
        if not self.is_available:
            return False
        with self._lock:
            assert self._conn is not None
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                cursor = self._conn.execute(
                    "DELETE FROM missions WHERE id = ?", (mission_id,)
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except sqlite3.Error:
                try:
                    self._conn.rollback()
                except sqlite3.Error:
                    pass
                return False

    def record_event(self, mission_id: str, kind: str, detail: str = "") -> None:
        """Consigner un événement de mission (traçabilité)."""
        if not self.is_available:
            return
        with self._lock:
            assert self._conn is not None
            try:
                self._conn.execute(
                    """
                    INSERT INTO mission_events (mission_id, created_at, kind, detail)
                    VALUES (?, ?, ?, ?)
                    """,
                    (mission_id, _now(), kind, sanitize_text(detail)),
                )
                self._conn.commit()
            except sqlite3.Error:
                logger.warning("Echec de l'enregistrement d'un evenement de mission.")


def _now() -> float:
    """Instant courant (secondes depuis l'époque)."""
    return time.time()
