"""Tests des premières fonctions d'assistant : /memory-search et /export.

Invariants :
- la recherche mémoire est en lecture seule ;
- l'export n'écrit JAMAIS sans confirmation humaine distincte ;
- l'export réutilise les garanties S3 (confins data/notes, .md, anti-écrasement).
"""

from __future__ import annotations

import io
import os
import unittest
import uuid
from contextlib import redirect_stdout
from unittest.mock import patch

from app.config.settings import Settings
from app.interface.cli import CLI

NOTES_DIR = os.path.join("data", "notes")


class FakeMemory:
    def __init__(self, entries):
        self.is_available = True
        self._entries = entries

    def list_memories(self):
        return self._entries


def _run(cli: CLI, command: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli._handle_command(command)
    return buffer.getvalue()


class TestMemorySearch(unittest.TestCase):
    def test_search_without_memory(self) -> None:
        cli = CLI(settings=Settings(), provider=None)
        output = _run(cli, "/memory-search facture")
        self.assertIn("indisponible", output)

    def test_search_without_term_shows_usage(self) -> None:
        cli = CLI(
            settings=Settings(),
            provider=None,
            memory=FakeMemory([]),
        )
        output = _run(cli, "/memory-search")
        self.assertIn("Usage", output)

    def test_search_matches_case_insensitive(self) -> None:
        memory = FakeMemory(
            [
                {"id": 1, "content": "Le projet s'appelle MILES", "category": "general", "importance": 3},
                {"id": 2, "content": "Autre sujet", "category": "general", "importance": 1},
            ]
        )
        cli = CLI(settings=Settings(), provider=None, memory=memory)
        output = _run(cli, "/memory-search miles")
        self.assertIn("Le projet s'appelle MILES", output)
        self.assertNotIn("Autre sujet", output)

    def test_search_no_match(self) -> None:
        memory = FakeMemory(
            [{"id": 1, "content": "rien à voir", "category": "general", "importance": 1}]
        )
        cli = CLI(settings=Settings(), provider=None, memory=memory)
        output = _run(cli, "/memory-search introuvable")
        self.assertIn("Aucun souvenir", output)


class TestExport(unittest.TestCase):
    def setUp(self) -> None:
        self.created: list[str] = []

    def tearDown(self) -> None:
        for name in self.created:
            full = os.path.join(NOTES_DIR, name)
            if os.path.exists(full):
                os.unlink(full)

    def _cli_with_message(self) -> CLI:
        cli = CLI(settings=Settings(), provider=None)
        cli.conversation.add_user_message("Message de test pour export")
        cli.conversation.add_assistant_message("Réponse simulée")
        return cli

    def test_export_without_conversation(self) -> None:
        cli = CLI(settings=Settings(), provider=None)
        output = _run(cli, "/export")
        self.assertIn("Aucune conversation", output)

    def test_export_refused_without_confirmation(self) -> None:
        cli = self._cli_with_message()
        name = f"exp-{uuid.uuid4().hex[:8]}.md"
        self.created.append(name)
        with patch("builtins.input", return_value="n"):
            output = _run(cli, f"/export {name}")
        self.assertIn("annulé", output)
        self.assertFalse(os.path.exists(os.path.join(NOTES_DIR, name)))

    def test_export_writes_note_with_content(self) -> None:
        cli = self._cli_with_message()
        name = f"exp-{uuid.uuid4().hex[:8]}.md"
        self.created.append(name)
        with patch("builtins.input", return_value="o"):
            output = _run(cli, f"/export {name}")
        self.assertIn("exportée", output)
        full = os.path.join(NOTES_DIR, name)
        self.assertTrue(os.path.exists(full))
        with open(full, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("Message de test pour export", content)
        self.assertIn("Réponse simulée", content)

    def test_export_overwrite_refused(self) -> None:
        cli = self._cli_with_message()
        name = f"exp-{uuid.uuid4().hex[:8]}.md"
        self.created.append(name)
        with patch("builtins.input", return_value="o"):
            _run(cli, f"/export {name}")
        with patch("builtins.input", return_value="o"):
            output = _run(cli, f"/export {name}")
        self.assertIn("refusé", output)

    def test_export_path_traversal_neutralized(self) -> None:
        cli = self._cli_with_message()
        self.created.append("échappée.md")
        with patch("builtins.input", return_value="o"):
            output = _run(cli, "/export ../../échappée.md")
        # La traversée est neutralisée : le fichier reste dans data/notes.
        self.assertTrue(os.path.exists(os.path.join(NOTES_DIR, "échappée.md")))
        self.assertFalse(os.path.exists(os.path.join("data", "échappée.md")))
        self.assertIn("exportée", output)


if __name__ == "__main__":
    unittest.main()
