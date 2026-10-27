"""Tests du cockpit projet (lecture des documents et écriture contrôlée).

Deux niveaux :

- tests unitaires du module ``app.interface.project_board`` sur un répertoire
  temporaire (aucun fichier du dépôt n'est modifié) ;
- tests HTTP réels sur un serveur local, avec session et jeton CSRF, comme les
  autres tests de l'interface web.

Aucun test n'écrit dans le vrai ``docs/coordination/TASKS.md``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.interface import project_board
from app.interface.project_board import TaskWriteError
from tests.web_test_support import WebTestServer, build_app

HEADER = (
    "| ID | Titre | Description | Statut | Assigné à | Fichiers concernés "
    "| Résultat attendu | Bloqué par | Créé le | Mis à jour le |\n"
    "|----|-------|-------------|--------|-----------|--------------------"
    "|------------------|------------|---------|---------------|\n"
)

ROW_TODO = (
    "| TASK-DEV-099 | Cockpit projet | Vue de pilotage du projet "
    "| TODO | Agent A | app/interface/web.py | Cockpit fonctionnel "
    "| — | 2026-10-27 | 2026-10-27 |\n"
)
ROW_OTHER_AGENT = (
    "| TASK-DEV-098 | Audit independant | Auditer la vue "
    "| IN_PROGRESS | Agent B | tests/ | Rapport d'audit "
    "| — | 2026-10-27 | 2026-10-27 |\n"
)
ROW_DONE = (
    "| TASK-001 | Coordination | Documents de coordination "
    "| DONE | Agent A | AGENTS.md | Documents coherents "
    "| — | 2026-10-19 | 2026-10-19 |\n"
)

STATUS_TEXT = """# STATUS
## État instantané (2026-10-27, Agent A)

- État de test.

## Blocages

- Aucun blocage technique.
"""

DECISIONS_TEXT = """# DECISIONS
## DEC-001 — Premiere decision

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Statut** : ACCEPTEE
"""

MESSAGES_TEXT = """# MESSAGES
| ID | Auteur → Destinataire | Date | Statut | Objet |
|----|-----------------------|------|--------|-------|
| M-001 | Agent A → Agent B | 2026-10-19 | [EN ATTENTE] | Verifier la vue |
| M-002 | Agent B → Agent A | 2026-10-19 | [RÉPONDU] | Recu |
"""


class CoordinationFixture(unittest.TestCase):
    """Crée un répertoire de coordination temporaire."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="miles_board_")
        self.root = Path(self._tmp.name)
        self.coordination = self.root / "docs" / "coordination"
        self.coordination.mkdir(parents=True)
        self.write_tasks(HEADER + ROW_TODO + ROW_OTHER_AGENT + ROW_DONE)
        (self.coordination / "STATUS.md").write_text(STATUS_TEXT, encoding="utf-8")
        (self.coordination / "DECISIONS.md").write_text(DECISIONS_TEXT, encoding="utf-8")
        (self.coordination / "MESSAGES.md").write_text(MESSAGES_TEXT, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_tasks(self, text: str, newline: str = "\n") -> None:
        payload = text.replace("\n", newline).encode("utf-8")
        (self.coordination / "TASKS.md").write_bytes(payload)

    def tasks_bytes(self) -> bytes:
        return (self.coordination / "TASKS.md").read_bytes()

    def audit_entries(self) -> list[dict]:
        path = self.root / "data" / "project_board_audit.jsonl"
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


class TestParseDocuments(CoordinationFixture):
    def test_tasks_are_parsed_with_all_columns(self) -> None:
        tasks, issues = project_board.parse_tasks(
            (self.coordination / "TASKS.md").read_text(encoding="utf-8")
        )
        self.assertEqual(len(tasks), 3)
        self.assertEqual(issues, [])
        cockpit = next(t for t in tasks if t["id"] == "TASK-DEV-099")
        self.assertEqual(cockpit["status_base"], "TODO")
        self.assertEqual(cockpit["owner"], "Agent A")
        self.assertEqual(cockpit["updated"], "2026-10-27")
        self.assertFalse(cockpit["malformed"])

    def test_status_suffix_is_tolerated_but_reported_as_base(self) -> None:
        tasks, issues = project_board.parse_tasks(
            HEADER + ROW_TODO.replace("| TODO |", "| DONE (analyse rendue) |")
        )
        self.assertEqual(tasks[0]["status_base"], "DONE")
        self.assertEqual(issues, [])

    def test_malformed_row_is_flagged_not_guessed(self) -> None:
        broken = "| TASK-DEV-097 | Tache cassee | DONE | Agent A | x | y | — | 2026-10-19 | 2026-10-19 |\n"
        tasks, issues = project_board.parse_tasks(HEADER + broken)
        self.assertTrue(tasks[0]["malformed"])
        self.assertEqual(len(issues), 1)
        self.assertIn("colonnes", issues[0]["problem"])

    def test_duplicate_identifier_is_flagged(self) -> None:
        tasks, issues = project_board.parse_tasks(
            HEADER + ROW_TODO + ROW_TODO.replace("Cockpit projet", "Doublon")
        )
        self.assertEqual(len(tasks), 2)
        self.assertTrue(any("2 fois" in issue["problem"] for issue in issues))

    def test_board_summary_health_and_pending_messages(self) -> None:
        board = project_board.build_board(self.coordination)
        self.assertEqual(board["summary"]["total"], 3)
        self.assertEqual(board["summary"]["by_status"]["TODO"], 1)
        self.assertEqual(board["summary"]["by_status"]["IN_PROGRESS"], 1)
        self.assertEqual(board["summary"]["by_status"]["DONE"], 1)
        self.assertEqual(board["messages"]["pending_count"], 1)
        self.assertEqual(board["decisions"][0]["id"], "DEC-001")
        self.assertIn("IN_PROGRESS", board["transitions"])
        self.assertEqual(board["agents"], ["Agent A", "Agent B"])
        self.assertTrue(board["documents"]["TASKS.md"]["exists"])
        self.assertEqual(board["issues"], [])

    def test_missing_document_is_reported(self) -> None:
        (self.coordination / "DECISIONS.md").unlink()
        board = project_board.build_board(self.coordination)
        self.assertFalse(board["documents"]["DECISIONS.md"]["exists"])
        self.assertTrue(any("DECISIONS.md" in issue["problem"] for issue in board["issues"]))

    def test_unknown_document_directory_is_reported(self) -> None:
        board = project_board.build_board(self.root / "absent")
        self.assertEqual(board["tasks"], [])
        self.assertEqual(len(board["issues"]), 4)


class TestSetTaskStatus(CoordinationFixture):
    def test_todo_to_in_progress_writes_and_audits(self) -> None:
        result = project_board.set_task_status(
            task_id="TASK-DEV-099",
            new_status="IN_PROGRESS",
            agent="Agent A",
            docs_dir=self.coordination,
            today=date(2026, 10, 27),
        )
        self.assertTrue(result["changed"])
        self.assertEqual(result["previous_status"], "TODO")
        self.assertEqual(result["task"]["status"], "IN_PROGRESS")
        text = (self.coordination / "TASKS.md").read_text(encoding="utf-8")
        self.assertIn("| TASK-DEV-099 | Cockpit projet", text)
        self.assertIn("| IN_PROGRESS | Agent A |", text)
        entries = self.audit_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["previous_status"], "TODO")
        self.assertEqual(entries[0]["new_status"], "IN_PROGRESS")
        self.assertEqual(entries[0]["agent"], "Agent A")

    def test_other_rows_are_untouched(self) -> None:
        before = self.tasks_bytes().decode("utf-8").splitlines()
        project_board.set_task_status(
            task_id="TASK-DEV-099",
            new_status="IN_PROGRESS",
            agent="Agent A",
            docs_dir=self.coordination,
        )
        after = self.tasks_bytes().decode("utf-8").splitlines()
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertIn("TASK-DEV-099", after[changed[0]])

    def test_same_status_is_a_noop_without_write(self) -> None:
        before = self.tasks_bytes()
        result = project_board.set_task_status(
            task_id="TASK-DEV-099",
            new_status="TODO",
            agent="Agent A",
            docs_dir=self.coordination,
        )
        self.assertFalse(result["changed"])
        self.assertEqual(before, self.tasks_bytes())
        self.assertEqual(self.audit_entries(), [])

    def test_done_task_cannot_be_reopened(self) -> None:
        before = self.tasks_bytes()
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-001",
                new_status="IN_PROGRESS",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "invalid_transition")
        self.assertEqual(caught.exception.http_status, 409)
        self.assertEqual(before, self.tasks_bytes())

    def test_other_agent_cannot_move_task_in_progress(self) -> None:
        before = self.tasks_bytes()
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-098",
                new_status="DONE",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "forbidden_owner")
        self.assertEqual(caught.exception.http_status, 403)
        self.assertEqual(before, self.tasks_bytes())
        self.assertEqual(self.audit_entries(), [])

    def test_owner_can_close_its_own_task(self) -> None:
        result = project_board.set_task_status(
            task_id="TASK-DEV-098",
            new_status="DONE",
            agent="Agent B",
            docs_dir=self.coordination,
        )
        self.assertTrue(result["changed"])
        self.assertEqual(result["task"]["status"], "DONE")
        self.assertEqual(self.audit_entries()[0]["agent"], "Agent B")

    def test_unknown_status_is_refused(self) -> None:
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-099",
                new_status="FINI",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "invalid_status")

    def test_unknown_agent_is_refused(self) -> None:
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-099",
                new_status="IN_PROGRESS",
                agent="Agent C",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "invalid_agent")

    def test_path_like_identifier_is_refused_before_any_io(self) -> None:
        for candidate in ("../../etc/passwd", "TASK-DEV-099/../../x", "TASK-1"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(TaskWriteError) as caught:
                    project_board.set_task_status(
                        task_id=candidate,
                        new_status="IN_PROGRESS",
                        agent="Agent A",
                        docs_dir=self.coordination,
                    )
                self.assertEqual(caught.exception.code, "invalid_task_id")

    def test_unknown_task_is_refused(self) -> None:
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-123",
                new_status="IN_PROGRESS",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "task_not_found")

    def test_duplicated_identifier_blocks_writing(self) -> None:
        self.write_tasks(HEADER + ROW_TODO + ROW_TODO)
        before = self.tasks_bytes()
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-099",
                new_status="IN_PROGRESS",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "ambiguous_task")
        self.assertEqual(before, self.tasks_bytes())

    def test_malformed_row_blocks_writing(self) -> None:
        broken = "| TASK-DEV-096 | Tache cassee | DONE | Agent A | x | y | — | 2026-10-19 | 2026-10-19 |\n"
        self.write_tasks(HEADER + broken)
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-096",
                new_status="IN_PROGRESS",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "malformed_row")

    def test_crlf_line_endings_are_preserved(self) -> None:
        self.write_tasks(HEADER + ROW_TODO + ROW_OTHER_AGENT + ROW_DONE, newline="\r\n")
        project_board.set_task_status(
            task_id="TASK-DEV-099",
            new_status="IN_PROGRESS",
            agent="Agent A",
            docs_dir=self.coordination,
        )
        raw = self.tasks_bytes()
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"| IN_PROGRESS | Agent A |\n", raw)

    def test_audit_failure_cancels_the_write(self) -> None:
        # Un fichier occupe la place du répertoire d'audit : l'écriture doit
        # être refusée AVANT toute modification du document.
        (self.root / "data").write_text("not a directory", encoding="utf-8")
        before = self.tasks_bytes()
        with self.assertRaises(TaskWriteError) as caught:
            project_board.set_task_status(
                task_id="TASK-DEV-099",
                new_status="IN_PROGRESS",
                agent="Agent A",
                docs_dir=self.coordination,
            )
        self.assertEqual(caught.exception.code, "audit_unavailable")
        self.assertEqual(before, self.tasks_bytes())


class TestProjectBoardHttp(CoordinationFixture):
    def build(self):
        return build_app(coordination_dir=str(self.coordination))

    def test_project_route_requires_session(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/project", authenticate=False)
        self.assertEqual(result["status"], 401)

    def test_project_route_returns_board_and_health(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/project")
        self.assertEqual(result["status"], 200)
        payload = result["json"]
        self.assertEqual(len(payload["tasks"]), 3)
        self.assertIn("health", payload)
        self.assertIn("provider", payload["health"])
        self.assertIn("transitions", payload)
        self.assertEqual(payload["summary"]["by_status"]["TODO"], 1)

    def test_tasks_route_returns_summary_and_tasks(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/tasks")
        self.assertEqual(result["status"], 200)
        self.assertEqual(len(result["json"]["tasks"]), 3)
        self.assertNotIn("decisions", result["json"])

    def test_status_update_requires_csrf(self) -> None:
        with WebTestServer(self.build()) as server:
            headers = {"X-MILES-Session": server.session["session_id"]}
            result = server.raw_request(
                "POST",
                "/api/tasks/TASK-DEV-099/status",
                {"status": "IN_PROGRESS", "agent": "Agent A"},
                headers=headers,
                authenticate=False,
            )
        self.assertEqual(result["status"], 403)
        self.assertIn("CSRF", result["json"]["error"])

    def test_status_update_persists(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request(
                "POST",
                "/api/tasks/TASK-DEV-099/status",
                {"status": "IN_PROGRESS", "agent": "Agent A"},
            )
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["json"]["changed"])
        text = (self.coordination / "TASKS.md").read_text(encoding="utf-8")
        self.assertIn("| TASK-DEV-099 | Cockpit projet | Vue de pilotage du projet | IN_PROGRESS |", text)

    def test_status_update_reports_guard_reason(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request(
                "POST",
                "/api/tasks/TASK-DEV-098/status",
                {"status": "DONE", "agent": "Agent A"},
            )
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["json"]["code"], "forbidden_owner")

    def test_percent_encoded_traversal_cannot_escape(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("intact", encoding="utf-8")
        with WebTestServer(self.build()) as server:
            result = server.raw_request(
                "POST",
                "/api/tasks/..%2F..%2Foutside/status",
                {"status": "IN_PROGRESS", "agent": "Agent A"},
            )
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["json"]["code"], "invalid_task_id")
        self.assertEqual(outside.read_text(encoding="utf-8"), "intact")

    def test_static_assets_are_public_and_typed(self) -> None:
        with WebTestServer(self.build()) as server:
            css = server.raw_request("GET", "/app.css", authenticate=False)
            js = server.raw_request("GET", "/app.js", authenticate=False)
        self.assertEqual(css["status"], 200)
        self.assertIn("--accent", css["body"])
        self.assertEqual(js["status"], 200)
        self.assertIn("loadBoard", js["body"])

    def test_unknown_asset_is_not_served(self) -> None:
        # Sans session, une route inconnue répond 401 : l'existence des
        # routes n'est pas révélée. Avec session, elle répond 404.
        with WebTestServer(self.build()) as server:
            anonymous = server.raw_request(
                "GET", "/assets/web/app.css", authenticate=False
            )
            authenticated = server.raw_request("GET", "/assets/web/app.css")
        self.assertEqual(anonymous["status"], 401)
        self.assertEqual(authenticated["status"], 404)
        self.assertNotIn("root:", authenticated["body"].lower())

    def test_index_is_served_from_assets(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/", authenticate=False)
        self.assertEqual(result["status"], 200)
        self.assertIn("cockpit projet", result["body"])
        # Liens relatifs : la page est servie à la racine, et l'auditeur du
        # Lab (comme un serveur statique) résout "app.css" depuis "/".
        self.assertIn('href="app.css"', result["body"])
        self.assertIn('src="app.js"', result["body"])


if __name__ == "__main__":
    unittest.main()
