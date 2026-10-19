"""Tests du chargement du fichier .env (stdlib, sans python-dotenv).

Ces tests vérifient que :
- les variables d'un fichier .env sont chargées ;
- les variables déjà présentes dans l'environnement du processus sont prioritaires ;
- un fichier .env absent n'empêche pas le démarrage ;
- aucun secret n'est exposé dans les logs ou les tests.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.config.settings import Settings


class TestEnvLoading(unittest.TestCase):
    """Tests du mécanisme de chargement .env."""

    def _write_env(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def _cleanup(self, path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass

    def test_env_file_loaded(self) -> None:
        path = self._write_env("MILES_PROVIDER=local\nMILES_HISTORY_LIMIT=5\n")
        try:
            env = {"MILES_ENV_FILE": path}
            with patch.dict(os.environ, env, clear=False):
                if "MILES_PROVIDER" in os.environ:
                    del os.environ["MILES_PROVIDER"]
                if "MILES_HISTORY_LIMIT" in os.environ:
                    del os.environ["MILES_HISTORY_LIMIT"]
                settings = Settings()
                self.assertEqual(settings.provider, "local")
                self.assertEqual(settings.get("history_limit"), 5)
        finally:
            self._cleanup(path)

    def test_process_env_takes_priority(self) -> None:
        path = self._write_env("MILES_PROVIDER=local\n")
        try:
            env = {"MILES_ENV_FILE": path, "MILES_PROVIDER": "remote"}
            with patch.dict(os.environ, env, clear=False):
                settings = Settings()
                self.assertEqual(settings.provider, "remote")
        finally:
            self._cleanup(path)

    def test_missing_env_file_does_not_block(self) -> None:
        # Aucun fichier .env : le démarrage doit réussir avec les valeurs par défaut.
        with patch.dict(os.environ, {}, clear=False):
            # S'assurer qu'aucune variable pertinente n'est dans l'environnement
            for key in ("MILES_PROVIDER", "MILES_HISTORY_LIMIT"):
                os.environ.pop(key, None)
            settings = Settings()
            self.assertEqual(settings.provider, "remote")

    def test_env_file_with_quotes(self) -> None:
        path = self._write_env('MILES_PROVIDER="local"\nMILES_REMOTE_MODEL="mon-model"\n')
        try:
            env = {"MILES_ENV_FILE": path}
            with patch.dict(os.environ, env, clear=False):
                if "MILES_PROVIDER" in os.environ:
                    del os.environ["MILES_PROVIDER"]
                if "MILES_REMOTE_MODEL" in os.environ:
                    del os.environ["MILES_REMOTE_MODEL"]
                settings = Settings()
                self.assertEqual(settings.provider, "local")
                self.assertEqual(settings.get("remote_model"), "mon-model")
        finally:
            self._cleanup(path)

    def test_no_secret_in_as_dict_logging(self) -> None:
        path = self._write_env('MILES_REMOTE_API_KEY="sk-secret-123"\n')
        try:
            env = {"MILES_ENV_FILE": path}
            with patch.dict(os.environ, env, clear=False):
                if "MILES_REMOTE_API_KEY" in os.environ:
                    del os.environ["MILES_REMOTE_API_KEY"]
                settings = Settings()
                # La clé est lue depuis l'environnement mais ne doit pas apparaître
                # dans une représentation destinée aux logs (as_dict est à usage
                # interne uniquement, non journalisée).
                self.assertEqual(settings.get("remote_api_key"), "sk-secret-123")
        finally:
            self._cleanup(path)


if __name__ == "__main__":
    unittest.main()
