"""Utilitaires partagés par les tests du site Miles Companion.

Chaque test travaille sur une base SQLite et un journal temporaires : aucune
écriture dans `data/`, aucune dépendance à un état laissé par une session
précédente (leçon de DEC-017).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from app.interface.companion import server as companion
from app.interface.companion import store as store_module


class CompanionTestServer:
    """Serveur sur un port libre, client avec cookies et en-têtes contrôlés."""

    def __init__(self, *, token: Optional[str] = None) -> None:
        self._httpd = companion.Server(("127.0.0.1", 0), companion.Handler)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )
        self.token = token

    @property
    def origin(self) -> str:
        return "http://127.0.0.1:%d" % self.port

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: Any = None,
        headers: Optional[dict[str, str]] = None,
        origin: Optional[str] = "auto",
        csrf: Optional[str] = None,
    ) -> dict[str, Any]:
        url = self.origin + path
        data = None
        sent_headers: dict[str, str] = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            sent_headers.setdefault("Content-Type", "application/json")
        if origin == "auto" and method in ("POST", "PATCH", "DELETE"):
            sent_headers.setdefault("Origin", self.origin)
        elif origin and origin != "auto":
            sent_headers["Origin"] = origin
        if csrf:
            sent_headers["X-CSRF-Token"] = csrf
        req = urllib.request.Request(url, data=data, headers=sent_headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", "replace")
                return {
                    "status": resp.status,
                    "body": raw,
                    "json": _maybe_json(raw),
                    "headers": dict(resp.headers.items()),
                }
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            return {
                "status": exc.code,
                "body": raw,
                "json": _maybe_json(raw),
                "headers": dict(exc.headers.items()),
            }

    def login(self, username: str, password: str) -> dict[str, Any]:
        result = self.request(
            "/api/companion/auth/login",
            method="POST",
            body={"username": username, "password": password},
        )
        if result["status"] == 200 and isinstance(result["json"], dict):
            result["csrf"] = result["json"].get("csrf_token")
        return result

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def __enter__(self) -> "CompanionTestServer":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _maybe_json(raw: str) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


class CompanionStoreCase(unittest.TestCase):
    """Base jetable + journal jetable pour chaque test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._previous = {
            "COMPANION_DB": os.environ.get("COMPANION_DB"),
            "COMPANION_AUDIT_LOG": os.environ.get("COMPANION_AUDIT_LOG"),
            "MILES_ENV_FILE": os.environ.get("MILES_ENV_FILE"),
        }
        os.environ["COMPANION_DB"] = str(self.tmp / "companion.db")
        os.environ["COMPANION_AUDIT_LOG"] = str(self.tmp / "audit.jsonl")
        os.environ["MILES_ENV_FILE"] = str(self.tmp / "absent.env")
        store_module.reset_store()
        self.store = store_module.get_store()

    def tearDown(self) -> None:
        store_module.reset_store()
        for key, value in self._previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()
