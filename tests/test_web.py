"""Tests de l'interface web MILES (stdlib http.server).

Tous les tests utilisent des simulateurs (mocks) : aucun vrai fournisseur IA,
aucune clé API, aucun appel réseau payant. Le serveur web est lancé sur un
port dynamique pour tester les routes réelles.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app.ai_providers.base import AIProvider, AIProviderError
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.interface.web import MilesHandler, MilesWebServer, WebApp
from tests.web_test_support import TEST_TOKEN, build_app


class SimulatedProvider(AIProvider):
    """Fournisseur simulé pour les tests web."""

    def __init__(self, name: str, should_fail: bool = False) -> None:
        self._name = name
        self._should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return not self._should_fail

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.call_count += 1
        if self._should_fail:
            raise AIProviderError(f"{self._name} indisponible.")
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        return f"Réponse simulée de {self._name} à : {last_user}"


class _FreePortServer:
    """Lance un ThreadingHTTPServer sur un port libre et l'arrête à la fin.

    L'interface web exige une authentification par jeton (Phase 6.1) :
    une session est ouverte automatiquement et les en-têtes de session et
    de jeton CSRF sont joints à chaque requête.
    """

    def __init__(self, handler_class, app: WebApp) -> None:
        MilesHandler.app = app
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._session: dict | None = None
        self._login()

    @property
    def port(self) -> int:
        return self._port

    def _login(self) -> None:
        """Ouvrir une session authentifiée auprès du serveur."""
        self._session = self._send(
            "POST",
            "/session",
            {"token": TEST_TOKEN},
            {},
            authenticated=False,
        ).get("_json")

    def _send(
        self,
        method: str,
        path: str,
        body: dict | None,
        extra_headers: dict,
        authenticated: bool = True,
    ) -> dict:
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        headers = dict(extra_headers)
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated and self._session:
            headers["X-MILES-Session"] = self._session["session_id"]
            headers["X-MILES-CSRF"] = self._session["csrf_token"]
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body_text = resp.read().decode("utf-8")
                result: dict = {"_status": resp.status, "_body": body_text}
                if body_text.strip():
                    try:
                        result["_json"] = json.loads(body_text)
                    except json.JSONDecodeError:
                        result["_json"] = None
                return result
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            result: dict = {"_status": exc.code, "_body": body_text}
            if body_text.strip():
                try:
                    result["_json"] = json.loads(body_text)
                except json.JSONDecodeError:
                    result["_json"] = None
            return result

    def __enter__(self) -> "_FreePortServer":
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def request(self, method: str, path: str, body: dict | None = None, expect_json: bool = True) -> dict:
        return self._send(method, path, body, {})


class TestWebIndex(unittest.TestCase):
    """Tests de la page d'accueil."""

    def test_index_returns_200_with_html(self) -> None:
        app = build_app(settings=Settings())
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("GET", "/", expect_json=False)
            self.assertEqual(result["_status"], 200)
            self.assertIn("MILES", result["_body"])


class TestWebStatus(unittest.TestCase):
    """Tests de la route /status."""

    def test_status_shows_provider(self) -> None:
        provider = SimulatedProvider("remote-test")
        app = build_app(settings=Settings(), provider=provider)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("GET", "/status")
            self.assertEqual(result["_status"], 200)
            self.assertEqual(result["_json"]["name"], "remote-test")
            # Aucun test implicite de disponibilite : la valeur reste
            # inconnue (None), jamais un booleen fabrique par is_available.
            self.assertIsNone(result["_json"]["available"])
            self.assertIn("non testée", result["_json"]["availability"])

    def test_status_no_provider(self) -> None:
        app = build_app(settings=Settings())
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("GET", "/status")
            self.assertEqual(result["_status"], 200)
            self.assertEqual(result["_json"]["name"], "non configuré")
            self.assertIsNone(result["_json"]["available"])


class TestWebMessage(unittest.TestCase):
    """Tests de la route /message."""

    def test_message_with_provider(self) -> None:
        provider = SimulatedProvider("remote-test")
        app = build_app(settings=Settings(), provider=provider)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})
            self.assertEqual(result["_status"], 200)
            self.assertIn("Réponse simulée de remote-test à : bonjour", result["_json"]["response"])

    def test_message_without_provider(self) -> None:
        app = build_app(settings=Settings())
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/message", {"message": "bonjour"})
            self.assertEqual(result["_status"], 400)
            self.assertIn("Aucun fournisseur IA configuré", result["_json"]["error"])

    def test_message_empty(self) -> None:
        provider = SimulatedProvider("remote-test")
        app = build_app(settings=Settings(), provider=provider)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/message", {"message": "   "})
            self.assertEqual(result["_status"], 400)
            self.assertIn("vide ou invalide", result["_json"]["error"])

    def test_provider_failure_preserves_context(self) -> None:
        failing = SimulatedProvider("failing", should_fail=True)
        app = build_app(settings=Settings(), provider=failing)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/message", {"message": "test"})
            self.assertEqual(result["_status"], 400)
            self.assertIn("indisponible", result["_json"]["error"])
            # Le contexte est préservé : le message utilisateur est dans l'historique
            self.assertTrue(result["_json"].get("context_preserved"))

    def test_provider_malformed_response_raises(self) -> None:
        # Fournisseur qui retourne du JSON invalide
        class BrokenProvider(AIProvider):
            @property
            def name(self) -> str:
                return "broken"

            def is_available(self) -> bool:
                return True

            def chat(self, messages: list[dict[str, str]]) -> str:
                raise AIProviderError("Réponse invalide (non-JSON) du fournisseur distant.")

        app = build_app(settings=Settings(), provider=BrokenProvider())
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/message", {"message": "test"})
            self.assertEqual(result["_status"], 400)
            self.assertIn("invalide", result["_json"]["error"])


class TestWebMemory(unittest.TestCase):
    """Tests des routes de mémoire persistante via le web."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_web_memory_")
        self.db_path = os.path.join(self.tmpdir, "memory.db")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_memories_empty(self) -> None:
        from app.memory.persistent import PersistentMemory

        memory = PersistentMemory(enabled=True, db_path=self.db_path)
        app = build_app(settings=Settings(), memory=memory)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("GET", "/memory")
            self.assertEqual(result["_status"], 200)
            self.assertEqual(result["_json"], [])
        memory.close()

    def test_remember_and_list(self) -> None:
        from app.memory.persistent import PersistentMemory

        memory = PersistentMemory(enabled=True, db_path=self.db_path)
        app = build_app(settings=Settings(), memory=memory)
        with _FreePortServer(MilesHandler, app) as server:
            add = server.request("POST", "/remember", {"content": "Je préfère le thé."})
            self.assertEqual(add["_status"], 200)
            self.assertIn("id", add["_json"])

            listed = server.request("GET", "/memory")
            self.assertEqual(listed["_status"], 200)
            self.assertEqual(len(listed["_json"]), 1)
            self.assertEqual(listed["_json"][0]["content"], "Je préfère le thé.")
        memory.close()

    def test_forget_memory(self) -> None:
        from app.memory.persistent import PersistentMemory

        memory = PersistentMemory(enabled=True, db_path=self.db_path)
        app = build_app(settings=Settings(), memory=memory)
        with _FreePortServer(MilesHandler, app) as server:
            add = server.request("POST", "/remember", {"content": "À supprimer"})
            mem_id = add["_json"]["id"]

            forget = server.request("POST", "/forget", {"id": mem_id})
            self.assertEqual(forget["_status"], 200)
            self.assertTrue(forget["_json"]["deleted"])

            listed = server.request("GET", "/memory")
            self.assertEqual(len(listed["_json"]), 0)
        memory.close()

    def test_memory_disabled(self) -> None:
        app = build_app(settings=Settings())  # memory_enabled=False par défaut
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/remember", {"content": "test"})
            self.assertEqual(result["_status"], 400)
            self.assertIn("indisponible", result["_json"]["error"])

    def test_forget_invalid_id(self) -> None:
        from app.memory.persistent import PersistentMemory

        memory = PersistentMemory(enabled=True, db_path=self.db_path)
        app = build_app(settings=Settings(), memory=memory)
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("POST", "/forget", {"id": "abc"})
            self.assertEqual(result["_status"], 400)
            self.assertIn("Identifiant invalide", result["_json"]["error"])
        memory.close()

    def test_unknown_route_returns_404(self) -> None:
        app = build_app(settings=Settings())
        with _FreePortServer(MilesHandler, app) as server:
            result = server.request("GET", "/inconnu")
            self.assertEqual(result["_status"], 404)


if __name__ == "__main__":
    unittest.main()
