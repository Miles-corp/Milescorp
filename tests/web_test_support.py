"""Support de test pour l'interface web MILES.

L'interface web exige une authentification par jeton (Phase 6.1) : les
tests doivent donc ouvrir une session avant toute requête sensible.

Ce module fournit :

- un jeu d'identifiants de test ;
- un constructeur d'application web authentifiée ;
- un petit client HTTP qui ouvre une session et joint automatiquement les
  en-têtes ``X-MILES-Session`` et ``X-MILES-CSRF``.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import Any, Optional

from app.config.settings import Settings
from app.interface.web import MilesHandler, WebApp
from app.interface.web_auth import (
    CSRF_HEADER,
    SESSION_HEADER,
    WebAuthenticator,
    WebCredentialStore,
)

#: Jeton d'accès utilisé par les tests.
TEST_TOKEN = "jeton-de-test-miles-0123456789"

#: Identifiant utilisateur associé.
TEST_USER = "utilisateur-test"

#: Agent utilisateur des requêtes de test.
#:
#: La session web est liée à l'agent utilisateur du client qui l'ouvre
#: (Phase 6.1, durcissement) : toutes les requêtes d'un même client de
#: test doivent donc présenter le même agent. Le module l'envoie sur
#: TOUTES ses requêtes, y compris la connexion.
TEST_USER_AGENT = "MILES-Test-Agent/1.0"

#: Second utilisateur (test d'isolation entre utilisateurs).
OTHER_TOKEN = "jeton-de-test-autre-0123456789"
OTHER_USER = "autre-utilisateur"


def build_authenticator(
    users: Optional[dict[str, str]] = None,
) -> WebAuthenticator:
    """Construire un authentificateur de test."""
    return WebAuthenticator(
        WebCredentialStore(users if users is not None else {TEST_USER: TEST_TOKEN})
    )


def build_app(
    *,
    users: Optional[dict[str, str]] = None,
    settings: Optional[Settings] = None,
    **kwargs: Any,
) -> WebApp:
    """Construire une application web authentifiée pour les tests."""
    return WebApp(
        settings=settings or Settings(),
        authenticator=build_authenticator(users),
        **kwargs,
    )


class WebTestServer:
    """Serveur web local sur un port libre, avec client HTTP authentifié."""

    def __init__(
        self,
        app: WebApp,
        *,
        token: str = TEST_TOKEN,
        authenticate: bool = True,
    ) -> None:
        MilesHandler.app = app
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), MilesHandler)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._token = token
        self._session: Optional[dict[str, Any]] = None
        if authenticate:
            self.login()

    @property
    def port(self) -> int:
        return self._port

    @property
    def session(self) -> Optional[dict[str, Any]]:
        return self._session

    def login(self, token: Optional[str] = None) -> dict[str, Any]:
        """Ouvrir une session authentifiée."""
        payload = self.raw_request(
            "POST",
            "/session",
            {"token": token if token is not None else self._token},
            headers={"Content-Type": "application/json"},
            authenticate=False,
        )
        self._session = payload.get("json") or None
        return self._session or {}

    def auth_headers(self) -> dict[str, str]:
        """Retourner les en-têtes de session et de jeton CSRF."""
        if not self._session:
            return {}
        return {
            SESSION_HEADER: str(self._session["session_id"]),
            CSRF_HEADER: str(self._session["csrf_token"]),
        }

    def raw_request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        headers: Optional[dict[str, str]] = None,
        authenticate: bool = True,
    ) -> Any:
        """Effectuer une requête HTTP brute (sans ajout automatique)."""
        url = f"http://127.0.0.1:{self._port}{path}"
        data = None
        request_headers = dict(headers or {})
        # Agent utilisateur constant : la session est liée au client.
        request_headers.setdefault("User-Agent", TEST_USER_AGENT)
        if body is not None and not isinstance(body, (bytes, bytearray)):
            data = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        if authenticate:
            request_headers.update(self.auth_headers())
        req = urllib.request.Request(
            url, data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return self._decode(resp.status, resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            return self._decode(
                exc.code, exc.read().decode("utf-8", "replace")
            )

    @staticmethod
    def _decode(status: int, text: str) -> dict[str, Any]:
        result: dict[str, Any] = {"status": status, "body": text}
        if text.strip():
            try:
                result["json"] = json.loads(text)
            except json.JSONDecodeError:
                result["json"] = None
        else:
            result["json"] = None
        return result

    def __enter__(self) -> "WebTestServer":
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
