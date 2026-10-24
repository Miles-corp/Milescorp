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
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            out = write_env(
                env_path,
                {"MILES_PROVIDER": "remote"},
                "MILES_PROVIDER=local\nAUTRE=valeur\n",
            )
            with open(env_path, encoding="utf-8") as fh:
                content = fh.read()
            self.assertEqual(out, env_path)
            self.assertIn("MILES_PROVIDER=remote", content)
            self.assertNotIn("MILES_PROVIDER=local", content)
            self.assertIn("AUTRE=valeur", content)

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

    def _run(self, env_path: str, choice: str, model: str, key: str, extra: tuple = ()):
        answers = iter((choice, model, key) + extra)

        def fake(prompt: str) -> str:
            return next(answers)

        captured = io.StringIO()
        with redirect_stdout(captured):
            result = run_setup(env_path, ask=fake, pick=fake, show=print)
        return result, captured.getvalue()

    def test_setup_never_echoes_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            result, output = self._run(
                env_path, "groq", "", "cle-tres-secrete-99", extra=("n",)
            )
            self.assertEqual(result, 0)
            self.assertNotIn("cle-tres-secrete-99", output)
            with open(env_path, encoding="utf-8") as fh:
                env_content = fh.read()
            self.assertIn("MILES_REMOTE_API_KEY=cle-tres-secrete-99", env_content)
            self.assertIn("MILES_API_KEY_GROQ=cle-tres-secrete-99", env_content)
            self.assertIn("MILES_PROVIDER=remote", env_content)
            # Modèle par défaut du catalogue appliqué
            self.assertIn(
                f"MILES_REMOTE_MODEL={PROVIDERS['groq'][1]}", env_content
            )

    def test_sibling_services_reduced_steps(self) -> None:
        """Un service du même compte (groupe Google) : clé seule, pas de modèle."""
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            answers = iter(
                [
                    "gemini",  # fournisseur
                    "",        # modèle (défaut)
                    "cle-gemini-111",
                    "o",       # configurer le service du même compte (mistral)
                    "cle-mistral-222",
                    "n",       # aucun autre fournisseur
                ]
            )

            def fake(prompt: str) -> str:
                return next(answers)

            captured = io.StringIO()
            with redirect_stdout(captured):
                result = run_setup(env_path, ask=fake, pick=fake, show=print)
            self.assertEqual(result, 0)
            output = captured.getvalue()
            self.assertIn("[étapes réduites]", output)
            self.assertNotIn("cle-gemini-111", output)
            self.assertNotIn("cle-mistral-222", output)
            with open(env_path, encoding="utf-8") as fh:
                env_content = fh.read()
            self.assertIn("MILES_API_KEY_GEMINI=cle-gemini-111", env_content)
            self.assertIn("MILES_API_KEY_MISTRAL=cle-mistral-222", env_content)
            # Le PREMIER fournisseur reste le bloc actif.
            self.assertIn("MILES_REMOTE_API_KEY=cle-gemini-111", env_content)
            self.assertNotIn("MILES_REMOTE_API_KEY=cle-mistral-222", env_content)

    def test_sibling_declined_keeps_single_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            answers = iter(
                ["gemini", "", "cle-gemini-111", "n", "n"]
            )

            def fake(prompt: str) -> str:
                return next(answers)

            captured = io.StringIO()
            with redirect_stdout(captured):
                result = run_setup(env_path, ask=fake, pick=fake, show=print)
            self.assertEqual(result, 0)
            with open(env_path, encoding="utf-8") as fh:
                env_content = fh.read()
            self.assertIn("MILES_API_KEY_GEMINI=cle-gemini-111", env_content)
            self.assertNotIn("MILES_API_KEY_MISTRAL", env_content)

    def test_additional_provider_quick_and_active_unchanged(self) -> None:
        """Un second fournisseur configuré n'écrase pas le bloc actif."""
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            answers = iter(
                [
                    "groq",             # fournisseur actif
                    "",                 # modèle (défaut)
                    "cle-groq-111",
                    "o",                # autre fournisseur
                    "gemini",
                    "cle-gemini-222",   # rapide : clé seule
                    "n",                # pas de service Google supplémentaire
                    "n",                # fin
                ]
            )

            def fake(prompt: str) -> str:
                return next(answers)

            captured = io.StringIO()
            with redirect_stdout(captured):
                result = run_setup(env_path, ask=fake, pick=fake, show=print)
            self.assertEqual(result, 0)
            with open(env_path, encoding="utf-8") as fh:
                env_content = fh.read()
            self.assertIn("MILES_API_KEY_GROQ=cle-groq-111", env_content)
            self.assertIn("MILES_API_KEY_GEMINI=cle-gemini-222", env_content)
            self.assertIn("MILES_REMOTE_API_KEY=cle-groq-111", env_content)
            self.assertNotIn("MILES_REMOTE_API_KEY=cle-gemini-222", env_content)

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

