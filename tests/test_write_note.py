"""Tests de l'outil d'écriture action_write_note (S3, première écriture).

Invariants (aucune écriture sans autorisation valide) :
- la confirmation humaine est exigée (risque MEDIUM) ;
- la permission `ecriture_note` est exigée (refusée par défaut) ;
- le chemin doit rester strictement sous data/notes ;
- les noms sensibles sont refusés ;
- l'écrasement d'une note existante est interdit ;
- le contenu est borné et non vide.
"""

from __future__ import annotations

import os
import unittest
import uuid

from app.tools.service import ToolService

NOTES_DIR = os.path.join("data", "notes")


def _fresh_service() -> ToolService:
    return ToolService(granted_permissions={"lecture_systeme", "ecriture_note"})


def _unique_name() -> str:
    return f"note-{uuid.uuid4().hex[:12]}.md"


class TestWriteNoteGate(unittest.TestCase):
    """Les deux barrières : permission puis confirmation."""

    def setUp(self) -> None:
        self.created: list[str] = []

    def tearDown(self) -> None:
        for name in self.created:
            full = os.path.join(NOTES_DIR, name)
            if os.path.exists(full):
                os.unlink(full)

    def _cleanup_later(self, name: str) -> str:
        self.created.append(name)
        return name

    def test_default_service_refuses_write_permission(self) -> None:
        service = ToolService()  # uniquement lecture_systeme
        name = self._cleanup_later(_unique_name())
        result = service.request_tool(
            "action_write_note",
            {"path": f"data/notes/{name}", "content": "essai"},
            actor_id="session-test",
        )
        self.assertFalse(result.success)
        self.assertFalse(os.path.exists(os.path.join(NOTES_DIR, name)))

    def test_confirmation_required_and_no_write_without_it(self) -> None:
        service = _fresh_service()
        name = self._cleanup_later(_unique_name())
        result = service.request_tool(
            "action_write_note",
            {"path": f"data/notes/{name}", "content": "première note"},
            actor_id="session-test",
        )
        self.assertTrue(result.confirmation_required)
        self.assertFalse(os.path.exists(os.path.join(NOTES_DIR, name)))

    def test_write_with_valid_confirmation(self) -> None:
        service = _fresh_service()
        name = self._cleanup_later(_unique_name())
        first = service.request_tool(
            "action_write_note",
            {"path": f"data/notes/{name}", "content": "note confirmée"},
            actor_id="session-test",
        )
        self.assertTrue(first.confirmation_required)
        done = service.request_tool(
            "action_write_note",
            {"path": f"data/notes/{name}", "content": "note confirmée"},
            user_confirmed=True,
            confirmation_token=first.confirmation_token,
            actor_id="session-test",
        )
        self.assertTrue(done.success)
        full = os.path.join(NOTES_DIR, name)
        self.assertTrue(os.path.exists(full))
        with open(full, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "note confirmée")


class TestWriteNoteBoundaries(unittest.TestCase):
    """Bornes de l'outil : confinement, sensibilité, écrasement, contenu."""

    def setUp(self) -> None:
        self.service = _fresh_service()
        self.created: list[str] = []

    def tearDown(self) -> None:
        for name in self.created:
            full = os.path.join(NOTES_DIR, name)
            if os.path.exists(full):
                os.unlink(full)

    def _run(self, path: str, content: str):
        name = os.path.basename(path)
        if name not in (".env", "config.json") and "." in name:
            self.created.append(name)
        first = self.service.request_tool(
            "action_write_note",
            {"path": path, "content": content},
            actor_id="session-test",
        )
        if not first.confirmation_required:
            return first
        return self.service.request_tool(
            "action_write_note",
            {"path": path, "content": content},
            user_confirmed=True,
            confirmation_token=first.confirmation_token,
            actor_id="session-test",
        )

    def test_path_outside_notes_refused(self) -> None:
        result = self._run("app/interface/cli.py", "tentative d'écriture")
        self.assertFalse(result.success)
        self.assertFalse(os.path.exists("app/interface/cli.py.bak"))

    def test_sensitive_filename_refused(self) -> None:
        result = self._run("data/notes/.env", "MILES_REMOTE_API_KEY=x")
        self.assertFalse(result.success)
        self.assertFalse(os.path.exists(os.path.join(NOTES_DIR, ".env")))

    def test_overwrite_refused(self) -> None:
        name = _unique_name()
        self.created.append(name)
        first = self._run(f"data/notes/{name}", "version une")
        self.assertTrue(first.success)
        second = self._run(f"data/notes/{name}", "version deux")
        self.assertFalse(second.success)
        with open(os.path.join(NOTES_DIR, name), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "version une")

    def test_empty_content_refused(self) -> None:
        result = self._run(f"data/notes/{_unique_name()}", "   ")
        self.assertFalse(result.success)

    def test_bad_extension_refused(self) -> None:
        result = self._run("data/notes/mauvais.exe", "contenu")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
