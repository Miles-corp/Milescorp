"""Client MILES côté serveur, pour le site Companion.

Le navigateur ne voit **jamais** le jeton porteur de MILES. Le serveur ouvre
lui-même une session avec le jeton lu dans l'environnement (ou dans `.env`),
la garde en mémoire, et ne relaie que des routes explicitement autorisées.

Cette couche remplace deux pratiques du pont Readdy :

- ``window.prompt`` qui demandait le jeton à l'utilisateur dans le navigateur ;
- le relais générique de ``/api/*``, qui exposait toute route de l'agent.

Toute erreur est traduite en code court, sans recopier une réponse brute ni un
en-tête ``Set-Cookie``.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_URL = "http://127.0.0.1:8080"
TOKEN_ENV = ("COMPANION_MILES_TOKEN", "MILES_WEB_AUTH_TOKEN")


class MilesError(Exception):
    """Erreur MILES avec un statut HTTP exploitable et un message sans secret."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


#: Routes relayées. Chaque entrée est (méthode, expression régulière).
ALLOWED: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GET", re.compile(r"^/status$")),
    ("GET", re.compile(r"^/provider$")),
    ("GET", re.compile(r"^/memory$")),
    ("GET", re.compile(r"^/log$")),
    ("GET", re.compile(r"^/tools$")),
    ("GET", re.compile(r"^/missions$")),
    ("GET", re.compile(r"^/mission/[A-Za-z0-9_-]{1,80}$")),
    ("GET", re.compile(r"^/api/device$")),
    ("GET", re.compile(r"^/api/project$")),
    ("GET", re.compile(r"^/api/tasks$")),
    ("POST", re.compile(r"^/message$")),
    ("POST", re.compile(r"^/remember$")),
    ("POST", re.compile(r"^/forget$")),
    ("POST", re.compile(r"^/mission$")),
    ("POST", re.compile(r"^/mission/[A-Za-z0-9_-]{1,80}/(answer|authorize|cancel)$")),
    ("POST", re.compile(r"^/tool$")),
    ("POST", re.compile(r"^/api/tasks/[A-Za-z0-9_-]{1,80}/status$")),
)

#: Délai normal et délai long (une réponse d'IA peut prendre du temps).
TIMEOUT_S = 12.0
TIMEOUT_LONG_S = 120.0


def _env_value(name: str) -> str:
    """Valeur d'environnement, puis `.env` local (jamais journalisée)."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    path = Path(os.environ.get("MILES_ENV_FILE", str(ROOT.parents[2] / ".env")))
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            if key.strip() == name:
                return raw.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def token_configured() -> bool:
    return any(_env_value(name) for name in TOKEN_ENV)


class MilesClient:
    """Session MILES persistante côté serveur, renouvelée à l'expiration."""

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None) -> None:
        self.base_url = (base_url or os.environ.get("COMPANION_MILES_URL", DEFAULT_URL)).rstrip("/")
        self._token = token if token is not None else next(
            (_env_value(name) for name in TOKEN_ENV if _env_value(name)), ""
        )
        self._session_id = ""
        self._csrf = ""
        self._lock = threading.RLock()
        self._last_refresh = 0.0

    @property
    def available(self) -> bool:
        return bool(self._token)

    def _login(self) -> None:
        if not self._token:
            raise MilesError("MILES non configuré : jeton absent sur la box.", 503)
        payload = json.dumps({"token": self._token}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/session",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - jamais le jeton dans le message
            raise MilesError(
                "MILES injoignable ou jeton refusé (%s)." % type(exc).__name__, 503
            ) from exc
        session = data.get("session_id")
        if not isinstance(session, str) or not session:
            raise MilesError("Session MILES refusée.", 503)
        self._session_id = session
        self._csrf = str(data.get("csrf_token") or "")
        self._last_refresh = time.time()

    @staticmethod
    def _allowed(method: str, path: str) -> bool:
        clean = path.split("?", 1)[0]
        return any(method == verb and pattern.match(clean) for verb, pattern in ALLOWED)

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> tuple[int, dict[str, Any]]:
        """Appeler une route autorisée ; retourne (statut, JSON)."""
        method = method.upper()
        if not self._allowed(method, path):
            raise MilesError("Route MILES non autorisée.", 404)
        if not self.available:
            raise MilesError("MILES non configuré : jeton absent sur la box.", 503)

        with self._lock:
            if not self._session_id:
                self._login()
            status, data = self._once(method, path, payload, timeout)
            if status == 401:
                self._session_id = ""
                self._login()
                status, data = self._once(method, path, payload, timeout)
            return status, data

    def _once(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]],
        timeout: Optional[float],
    ) -> tuple[int, dict[str, Any]]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        headers["X-MILES-Session"] = self._session_id
        if method != "GET":
            headers["X-MILES-CSRF"] = self._csrf
        req = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        effective_timeout = timeout or (TIMEOUT_LONG_S if path == "/message" else TIMEOUT_S)
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        except Exception as exc:  # noqa: BLE001
            raise MilesError(
                "MILES injoignable sur 127.0.0.1:8080 (%s)." % type(exc).__name__, 502
            ) from exc
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            data = {"error": "réponse MILES illisible"}
        if not isinstance(data, dict):
            data = {"value": data}
        return status, data

    # ---------------------------------------------------------- raccourcis
    def status(self) -> dict[str, Any]:
        return self.request("GET", "/status")[1]

    def provider(self) -> dict[str, Any]:
        return self.request("GET", "/provider")[1]

    def missions(self) -> dict[str, Any]:
        return self.request("GET", "/missions")[1]

    def mission(self, mission_id: str) -> dict[str, Any]:
        return self.request("GET", "/mission/%s" % mission_id)[1]


_CLIENT: Optional[MilesClient] = None
_CLIENT_LOCK = threading.Lock()


def get_client() -> MilesClient:
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = MilesClient()
        return _CLIENT


def reset_client() -> None:
    global _CLIENT
    with _CLIENT_LOCK:
        _CLIENT = None
