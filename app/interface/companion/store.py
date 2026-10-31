"""Persistance locale du site Miles Companion (SQLite, bibliothèque standard).

Le site est servi par la box : aucune base distante, aucun ORM, aucune
dépendance. Toutes les écritures passent par ce module, sous un verrou unique.

Choix assumés :

- **un seul fichier** (`data/companion.db`) : sauvegarde et effacement simples ;
- **WAL** : lectures pendant écriture, sans bloquer l'interface ;
- **clés étrangères** activées : la suppression d'un compte emporte ses
  sessions et préférences ;
- **aucun secret en clair** : les mots de passe sont hachés dans `auth.py`,
  les sessions ne sont stockées que sous forme de hachage.

Le chemin est configurable par ``COMPANION_DB`` (isolation des tests,
sauvegarde manuelle). Le dossier `data/` est déjà ignoré par Git.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional

ROOT = Path(__file__).resolve().parent
#: Base à la racine du dépôt, à côté des autres bases locales (`data/`),
#: comme annoncé dans l'interface et dans la documentation.
DEFAULT_DB = ROOT.parents[2] / "data" / "companion.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    password_hash TEXT NOT NULL,
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    last_login_at REAL
);

CREATE TABLE IF NOT EXISTS sessions (
    id_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    ip_hash TEXT,
    ua_hash TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    dev_mode INTEGER NOT NULL DEFAULT 0,
    locale TEXT NOT NULL DEFAULT 'fr',
    theme TEXT NOT NULL DEFAULT 'dark'
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    account_id TEXT,
    username TEXT,
    event TEXT NOT NULL,
    target TEXT,
    outcome TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS routines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    objective TEXT NOT NULL,
    created_by TEXT REFERENCES accounts(id) ON DELETE SET NULL,
    created_at REAL NOT NULL,
    last_run_at REAL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS confirmation_tokens (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    used_at REAL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    first_at REAL NOT NULL,
    locked_until REAL
);

CREATE TABLE IF NOT EXISTS paired_devices (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,
    ip_hash TEXT,
    ua_hash TEXT
);

-- La table `boxes` (adresse saisie) a été remplacée par l'appairage par QR
-- code ; elle n'a jamais contenu de ligne en dehors du développement.
DROP TABLE IF EXISTS boxes;

CREATE INDEX IF NOT EXISTS idx_audit_at ON audit(at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
CREATE INDEX IF NOT EXISTS idx_tokens_account ON confirmation_tokens(account_id);
"""


def db_path() -> Path:
    """Chemin de la base, surchargeable pour les tests."""
    override = os.environ.get("COMPANION_DB", "").strip()
    return Path(override) if override else DEFAULT_DB


class Store:
    """Connexion unique partagée, protégée par un verrou réentrant."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------- outils
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, tuple(params)))

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def transaction(self) -> "sqlite3.Connection":
        """Connexion pour une transaction explicite (`BEGIN IMMEDIATE`).

        L'appelant garde le verrou pendant toute la transaction : c'est ce qui
        rend la limite « deux admins » fiable même sous deux requêtes
        simultanées.
        """
        return self._conn

    def lock(self) -> threading.RLock:
        return self._lock

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_STORE: Optional[Store] = None
_STORE_LOCK = threading.Lock()


def get_store() -> Store:
    """Instance partagée, créée à la première utilisation."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = Store()
        return _STORE


def reset_store() -> None:
    """Fermer et oublier l'instance (tests, changement de chemin)."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is not None:
            _STORE.close()
        _STORE = None


def init_store(path: Optional[Path] = None) -> Store:
    """Créer une instance explicite (tests) et la rendre partagée."""
    global _STORE
    with _STORE_LOCK:
        if _STORE is not None:
            _STORE.close()
        _STORE = Store(path)
        return _STORE
