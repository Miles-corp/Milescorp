"""Tests de la commande /log et de la route web GET /log (S5, MI-007).

Invariants : lecture seule du journal du ToolService, aucune entrée brute
de paramètres (empreintes uniquement), route web protégée par session.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from app.config.settings import Settings
from app.interface.cli import CLI
from app.tools.service import ToolService
from tests.web_test_support import WebTestServer, build_app


def _make_service_with_entries(count: int = 3) -> ToolService:
    service = ToolService()
    for i in range(count):
        service.audit.record(
            tool_id=f"outil-{i}",
            user_confirmed=(i % 2 == 0),
            permission_granted=True,
            result="success",
        )
    return service


def _run_log(cli: CLI, command: str = "/log") -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli._handle_command(command)
    return buffer.getvalue()


class TestCLILog(unittest.TestCase):
    def test_log_without_service(self) -> None:
        cli = CLI(settings=Settings(), provider=None)
        output = _run_log(cli)
        self.assertIn("Aucun journal d'outils disponible.", output)

    def test_log_lists_recent_entries(self) -> None:
        cli = CLI(
            settings=Settings(),
            provider=None,
            tool_service=_make_service_with_entries(3),
        )
        output = _run_log(cli)
        self.assertIn("outil-0", output)
        self.assertIn("outil-2", output)
        self.assertIn("success", output)
        self.assertIn("Journal des outils", output)

    def test_log_limit_count(self) -> None:
        cli = CLI(
            settings=Settings(),
            provider=None,
            tool_service=_make_service_with_entries(5),
        )
        output = _run_log(cli, "/log 2")
        self.assertNotIn("outil-0", output)
        self.assertIn("outil-4", output)
        self.assertIn("2 dernier", output)

    def test_log_empty_journal(self) -> None:
        cli = CLI(settings=Settings(), provider=None, tool_service=ToolService())
        output = _run_log(cli)
        self.assertIn("Aucune activité enregistrée.", output)

    def test_log_invalid_count(self) -> None:
        cli = CLI(
            settings=Settings(),
            provider=None,
            tool_service=_make_service_with_entries(2),
        )
        output = _run_log(cli, "/log abc")
        self.assertIn("Usage", output)


class TestWebLogRoute(unittest.TestCase):
    def test_log_requires_session(self) -> None:
        app = build_app(settings=Settings(), tool_service=ToolService())
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/log", authenticate=False)
            self.assertEqual(result["status"], 401)

    def test_log_returns_entries(self) -> None:
        app = build_app(
            settings=Settings(),
            tool_service=_make_service_with_entries(2),
        )
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/log")
            self.assertEqual(result["status"], 200)
            payload = result["json"]
            self.assertEqual(payload["count"], 2)
            self.assertEqual(payload["entries"][0]["tool_id"], "outil-0")
            self.assertIn("parameters_hash", payload["entries"][0])

    def test_log_without_service_is_503(self) -> None:
        app = build_app(settings=Settings())
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/log")
            self.assertEqual(result["status"], 503)


if __name__ == "__main__":
    unittest.main()
