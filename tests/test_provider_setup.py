"""Tests de l'assistant de configuration des fournisseurs (S6 minimal, MI-008).

Invariants : la clé n'est jamais affichée, jamais écrite ailleurs que dans le
.env demandé, la fusion préserve les lignes existantes non gérées, l'écriture
est atomique (pas de fichier temporaire résiduel), et une clé inattendue/vide
abandonne sans modifier aucun fichier.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from app.config.setup import PROVIDERS, run_setup, write_env


class TestWriteEnv(unittest.TestCase):
    def test_merge_preserves_unmanaged_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            existing = "# commentaire\nMILES_HISTORY_LIMIT=10\n"
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write(existing)
            write_env(
                env_path,
                {"MILES_PROVIDER": "remote", "MILES_REMOTE_API_KEY": "cle-secret"},
                existing,
            )
            with open(env_path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("# commentaire", content)
            self.assertIn("MILES_HISTORY_LIMIT=10", content)
            self.assertIn("MILES_PROVIDER=remote", content)
            self.assertIn("MILES_REMOTE_API_KEY=cle-secret", content)

    def test_replace_existing_managed_line(self) -> None:
        out = write_env(
            ".unused",  # jamais créé : on passe le contenu directement
            {"MILES_PROVIDER": "remote"},
            "MILES_PROVIDER=local\nAUTRE=valeur\n",
        )
        self.assertEqual(out, ".unused")

    def test_atomic_no_tmp_file_left(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            write_env(env_path, {"MILES_PROVIDER": "remote"}, "")
            leftovers = [
                f for f in os.listdir(tmp) if f.startswith(".miles-setup-")
            ]
            self.assertEqual(leftovers, [])


class TestRunSetup(unittest.TestCase):
    """L'assistant n'affiche jamais la clé et sécurise les cas d'erreur."""

    def _run(self, env_path: str, choice: str, model: str, key: str):
        answers = iter([choice, model, key])

        def fake(prompt: str) -> str:
            return next(answers)

        captured = io.StringIO()
        with redirect_stdout(captured):
            result = run_setup(env_path, ask=fake, pick=fake, show=print)
        return result, captured.getvalue()

    def test_setup_never_echoes_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            result, output = self._run(env_path, "groq", "", "cle-tres-secrete-99")
            self.assertEqual(result, 0)
            self.assertNotIn("cle-tres-secrete-99", output)
            with open(env_path, encoding="utf-8") as fh:
                env_content = fh.read()
            self.assertIn("MILES_REMOTE_API_KEY=cle-tres-secrete-99", env_content)
            self.assertIn("MILES_PROVIDER=remote", env_content)
            # Modèle par défaut du catalogue appliqué
            self.assertIn(
                f"MILES_REMOTE_MODEL={PROVIDERS['groq'][1]}", env_content
            )

    def test_unknown_provider_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            result, _ = self._run(env_path, "inconnu", "", "x")
            self.assertEqual(result, 1)
            self.assertFalse(os.path.exists(env_path))

    def test_empty_key_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            result, _ = self._run(env_path, "groq", "", "")
            self.assertEqual(result, 1)
            self.assertFalse(os.path.exists(env_path))

    def test_key_with_quote_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            result, _ = self._run(env_path, "groq", "", 'cle"injection')
            self.assertEqual(result, 1)
            self.assertFalse(os.path.exists(env_path))


if __name__ == "__main__":
    unittest.main()

