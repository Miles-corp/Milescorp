"""Tests de l'isolation de la suite et du traitement des valeurs vides.

Deux défauts sont couverts ici.

1. **Isolation des tests** : ``tests/__init__.py`` redirige ``MILES_ENV_FILE``
   vers un chemin destiné à rester inexistant. Un chemin fixe et prévisible
   est un piège : si une exécution (autre branche, test d'intégration,
   script) écrit dans ce chemin, le fichier existe ensuite pour toutes les
   sessions suivantes. C'est la cause exacte de deux échecs constatés dans
   ``tests/test_status_provider_diagnostics.py`` : un ``.env`` laissé dans
   ``%TEMP%`` fournissait un ``MILES_REMOTE_MODEL=`` vide à toute la suite.
   L'isolation doit donc se faire dans un répertoire unique par session.

2. **Valeurs vides** : une variable vide n'est pas une configuration. Elle
   doit laisser la main à la source suivante, puis à la valeur par défaut.
   Sans cette règle, ``MILES_REMOTE_MODEL=`` produisait un modèle vide
   (erreurs fournisseur incompréhensibles) et ``MILES_HISTORY_LIMIT=``
   faisait échouer le démarrage au lieu de retomber sur sa valeur par défaut.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import tests as tests_package
from app.config.settings import Settings

#: Variables susceptibles de venir de l'environnement du développeur.
_MANAGED_VARIABLES = (
    "MILES_PROVIDER",
    "MILES_REMOTE_MODEL",
    "MILES_REMOTE_BASE_URL",
    "MILES_REMOTE_API_KEY",
    "MILES_LOCAL_MODEL",
    "MILES_HISTORY_LIMIT",
    "MILES_MEMORY_ENABLED",
    "MILES_MISSION_MAX_STEPS",
)


def _empty_environment(env_file: str) -> dict[str, str]:
    """Environnement où aucune variable MILES_* ne vient du développeur."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("MILES_")}
    env["MILES_ENV_FILE"] = env_file
    return env


class _EnvFileMixin:
    """Création d'un fichier .env temporaire et d'un JSON absent."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.absent_env = os.path.join(self._tmpdir.name, "absent.env")
        self.absent_json = os.path.join(self._tmpdir.name, "absent.json")

    def _write_env(self, content: str) -> str:
        path = os.path.join(self._tmpdir.name, f"env-{len(os.listdir(self._tmpdir.name))}.env")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _settings(self, env_file: str, env: dict[str, str] | None = None) -> Settings:
        values = _empty_environment(env_file)
        values.update(env or {})
        with patch.dict(os.environ, values, clear=True):
            return Settings(config_path=self.absent_json)


class TestSessionIsolation(unittest.TestCase):
    """Le chemin .env des tests doit être propre à la session."""

    def test_isolation_path_is_redirected(self) -> None:
        path = os.environ.get("MILES_ENV_FILE")
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".env"))

    def test_isolation_path_is_not_the_legacy_fixed_path(self) -> None:
        """Le chemin fixe laissé par une exécution antérieure est abandonné."""
        path = os.environ.get("MILES_ENV_FILE")
        self.assertNotEqual(
            os.path.normcase(os.path.abspath(path)),
            os.path.normcase(os.path.abspath(tests_package.LEGACY_ISOLATION_PATH)),
        )

    def test_isolation_file_does_not_exist(self) -> None:
        """Le fichier d'isolation ne doit jamais exister pendant la suite."""
        self.assertFalse(os.path.exists(os.environ["MILES_ENV_FILE"]))

    def test_isolation_directory_is_dedicated(self) -> None:
        """Le répertoire d'isolation est un répertoire temporaire dédié."""
        directory = tests_package.isolation_directory()
        self.assertIsNotNone(directory)
        self.assertTrue(os.path.isdir(directory))
        self.assertTrue(os.path.basename(directory).startswith("miles-tests-env-"))
        self.assertEqual(
            os.path.dirname(os.environ["MILES_ENV_FILE"]), directory
        )

    def test_two_sessions_get_different_paths(self) -> None:
        """Deux sessions successives n'utilisent pas le même chemin."""
        env = {key: value for key, value in os.environ.items() if key != "MILES_ENV_FILE"}
        code = "import os, tests; print(os.environ['MILES_ENV_FILE'])"
        paths = []
        for _ in range(2):
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            paths.append(result.stdout.strip())
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0], paths[1])
        for path in paths:
            self.assertFalse(os.path.exists(path))


class TestDefaultValues(_EnvFileMixin, unittest.TestCase):
    """Sans aucune source de configuration, les défauts documentés s'appliquent."""

    def test_defaults_apply_when_no_source(self) -> None:
        settings = self._settings(self.absent_env)
        self.assertEqual(settings.provider, "remote")
        self.assertEqual(settings.get("remote_model"), "miles-default")
        self.assertEqual(settings.get("local_model"), "miles-local")
        self.assertEqual(settings.get("history_limit"), 10)
        self.assertEqual(settings.get("remote_timeout"), 30)
        self.assertEqual(settings.get("mission_max_steps"), 12)

    def test_defaults_apply_with_stray_environment(self) -> None:
        """Le chemin d'isolation de la session ne doit pas dégrader les défauts."""
        settings = self._settings(os.environ["MILES_ENV_FILE"])
        self.assertEqual(settings.get("remote_model"), "miles-default")


class TestEmptyValuesAreIgnored(_EnvFileMixin, unittest.TestCase):
    """Une valeur vide est traitée comme une source absente."""

    def test_empty_dotenv_value_falls_back_to_default(self) -> None:
        path = self._write_env("MILES_REMOTE_MODEL=\n")
        settings = self._settings(path)
        self.assertEqual(settings.get("remote_model"), "miles-default")

    def test_whitespace_dotenv_value_falls_back_to_default(self) -> None:
        path = self._write_env("MILES_REMOTE_MODEL=   \n")
        settings = self._settings(path)
        self.assertEqual(settings.get("remote_model"), "miles-default")

    def test_empty_numeric_value_falls_back_instead_of_failing(self) -> None:
        """``MILES_HISTORY_LIMIT=`` ne doit pas empêcher le démarrage."""
        path = self._write_env("MILES_HISTORY_LIMIT=\n")
        settings = self._settings(path)
        self.assertEqual(settings.get("history_limit"), 10)

    def test_empty_process_value_lets_dotenv_win(self) -> None:
        path = self._write_env("MILES_REMOTE_MODEL=mon-modele\n")
        settings = self._settings(path, {"MILES_REMOTE_MODEL": ""})
        self.assertEqual(settings.get("remote_model"), "mon-modele")

    def test_empty_process_value_falls_back_to_default(self) -> None:
        settings = self._settings(self.absent_env, {"MILES_REMOTE_MODEL": "   "})
        self.assertEqual(settings.get("remote_model"), "miles-default")

    def test_non_empty_value_still_wins(self) -> None:
        """Non-régression : une valeur renseignée garde la priorité."""
        path = self._write_env("MILES_REMOTE_MODEL=depuis-le-fichier\n")
        settings = self._settings(path, {"MILES_REMOTE_MODEL": "depuis-le-processus"})
        self.assertEqual(settings.get("remote_model"), "depuis-le-processus")

    def test_empty_api_key_stays_absent(self) -> None:
        """Une clé vide reste absente : jamais de chaîne vide propagée."""
        path = self._write_env("MILES_REMOTE_API_KEY=\n")
        settings = self._settings(path)
        self.assertIsNone(settings.get("remote_api_key"))

    def test_empty_boolean_value_falls_back_to_default(self) -> None:
        path = self._write_env("MILES_MEMORY_ENABLED=\n")
        settings = self._settings(path)
        self.assertFalse(settings.memory_enabled)


if __name__ == "__main__":
    unittest.main()
