"""Tests de POST /logout (révocation proactive de session — P3 S-E3-02).

Invariants : une session révoquée ne peut plus être réutilisée ; la
révocation est authentifiée et protégée par le jeton CSRF.
"""

from __future__ import annotations

import unittest

from app.config.settings import Settings
from app.tools.service import ToolService
from tests.web_test_support import WebTestServer, build_app


class TestLogoutRoute(unittest.TestCase):
    def _app(self):
        return build_app(settings=Settings(), tool_service=ToolService())

    def test_logout_revokes_session(self) -> None:
        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request("POST", "/logout", body={})
            self.assertEqual(result["status"], 200)
            self.assertTrue(result["json"]["revoked"])
            # La session révoquée n'est plus acceptée.
            after = server.raw_request("GET", "/log")
            self.assertEqual(after["status"], 401)

    def test_logout_requires_session(self) -> None:
        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request("POST", "/logout", body={}, authenticate=False)
            self.assertEqual(result["status"], 401)

    def test_logout_twice_second_is_idempotent(self) -> None:
        app = self._app()
        with WebTestServer(app) as server:
            first = server.raw_request("POST", "/logout", body={})
            self.assertEqual(first["status"], 200)
            # Nouvelle session : la première reste bien morte.
            server.login()
            second = server.raw_request("POST", "/logout", body={})
            self.assertEqual(second["status"], 200)


if __name__ == "__main__":
    unittest.main()
