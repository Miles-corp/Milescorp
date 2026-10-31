"""Journal d'audit et journal d'accès du site Miles Companion.

Deux usages distincts :

- **audit** : événements durables (connexion, changement de compte, action de
  mission, activation d'un fournisseur, bascule du mode développeur). Stocké
  en base et dupliqué en JSONL lisible hors ligne.
- **accès HTTP** : anneau en mémoire (500 entrées), consultable en mode
  développeur. Il ne contient jamais de corps de requête, de cookie ni de
  jeton.

Règle unique : **rien de sensible ne sort**. Les clés dont le nom évoque un
secret sont remplacées avant écriture, et les chaînes sont tronquées. Un test
vérifie qu'une clé API passée par erreur ne se retrouve pas dans le journal.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.interface.companion import store as store_module

ROOT = Path(__file__).resolve().parent
MAX_STRING = 400
ACCESS_MAX = 500

#: Fragments de noms de champs qui déclenchent l'expurgation.
_SENSITIVE = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "authorization",
    "cookie",
    "csrf",
    "session",
)

_ACCESS: deque[dict[str, Any]] = deque(maxlen=ACCESS_MAX)
_ACCESS_LOCK = threading.Lock()


def _redact(value: Any, depth: int = 0) -> Any:
    """Expurger récursivement un détail avant stockage."""
    if depth > 6:
        return "[trop profond]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _SENSITIVE):
                result[str(key)] = "[expurgé]"
            else:
                result[str(key)] = _redact(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact(item, depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value[:MAX_STRING]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_STRING]


def _jsonl_path() -> Path:
    #: À côté de la base, à la racine du dépôt (`data/` ignoré par Git).
    default = ROOT.parents[2] / "data" / "companion-audit.jsonl"
    return Path(os.environ.get("COMPANION_AUDIT_LOG", str(default)))


def log_event(
    event: str,
    *,
    account: Optional[dict[str, Any]] = None,
    target: str = "",
    outcome: str = "ok",
    detail: Optional[dict[str, Any]] = None,
    store: Optional[store_module.Store] = None,
) -> None:
    """Écrire un événement d'audit expurgé (base + JSONL)."""
    safe_detail = _redact(detail or {})
    account_id = (account or {}).get("id") or (account or {}).get("account_id")
    username = (account or {}).get("username", "")
    now = time.time()
    db = store or store_module.get_store()
    try:
        db.execute(
            "INSERT INTO audit (at, account_id, username, event, target, outcome, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                now,
                account_id,
                username,
                str(event)[:120],
                str(target)[:200],
                str(outcome)[:20],
                json.dumps(safe_detail, ensure_ascii=False, sort_keys=True),
            ),
        )
    except Exception:  # noqa: BLE001 - le journal ne doit jamais casser l'action
        pass

    line = {
        "at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(timespec="seconds"),
        "event": str(event)[:120],
        "account": username,
        "target": str(target)[:200],
        "outcome": str(outcome)[:20],
        "detail": safe_detail,
    }
    try:
        path = _jsonl_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass


def list_events(
    *,
    limit: int = 100,
    account_id: Optional[str] = None,
    store: Optional[store_module.Store] = None,
) -> list[dict[str, Any]]:
    """Derniers événements, filtrés par compte si demandé."""
    db = store or store_module.get_store()
    limit = max(1, min(int(limit), 500))
    if account_id:
        rows = db.query(
            "SELECT * FROM audit WHERE account_id = ? ORDER BY at DESC LIMIT ?",
            (account_id, limit),
        )
    else:
        rows = db.query("SELECT * FROM audit ORDER BY at DESC LIMIT ?", (limit,))
    events = []
    for row in rows:
        try:
            detail = json.loads(row["detail"] or "{}")
        except ValueError:
            detail = {}
        events.append(
            {
                "id": row["id"],
                "at": row["at"],
                "account": row["username"],
                "event": row["event"],
                "target": row["target"],
                "outcome": row["outcome"],
                "detail": detail,
            }
        )
    return events


def record_access(
    *,
    method: str,
    path: str,
    status: int,
    account: str = "",
    duration_ms: float = 0.0,
    client: str = "",
) -> None:
    """Ajouter une ligne au journal d'accès en mémoire (jamais de secret)."""
    clean_path = str(path).split("?", 1)[0][:200]
    entry = {
        "at": time.time(),
        "method": str(method)[:8],
        "path": clean_path,
        "status": int(status),
        "account": str(account)[:60],
        "duration_ms": round(float(duration_ms), 1),
        "client": str(client)[:60],
    }
    with _ACCESS_LOCK:
        _ACCESS.append(entry)


def list_access(limit: int = 200) -> list[dict[str, Any]]:
    with _ACCESS_LOCK:
        entries = list(_ACCESS)
    return list(reversed(entries[-max(1, min(int(limit), ACCESS_MAX)):]))


def clear_access() -> None:
    with _ACCESS_LOCK:
        _ACCESS.clear()
