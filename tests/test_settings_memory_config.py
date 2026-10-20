"""Tests de la configuration du paramètre booléen memory_enabled.

Vérifie que :
- "true" active la mémoire persistante ;
- "false" la désactive réellement (et non "bool('false')" qui vaudrait True) ;
- la valeur par défaut est la désactivation ;
- une valeur invalide produit une erreur explicite ;
- le fichier de configuration JSON est traité de la même façon ;
- la désactivation empêche effectivement l'activation de la mémoire.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import miles
from app.config.settings import Settings, SettingsError
from app.security.paths import project_root


class TestMemoryEnabledFromEnv(unittest.TestCase):
    """Conversion de MILES_MEMORY_ENABLED."""

    def _settings_with(self, value: str | None) -> Settings:
        env: dict[str, str] = {}
        if value is not None:
            env["MILES_MEMORY_ENABLED"] = value
        with mock.patch.dict(os.environ, env):
            os.environ.pop("MILES_MEMORY_ENABLED", None)
            if value is not None:
                os.environ["MILES_MEMORY_ENABLED"] = value
            return Settings()

    def test_valeur_par_defaut_desactive(self) -> None:
        settings = self._settings_with(None)
        self.assertFalse(settings.memory_enabled)

    def test_valeur_true_active(self) -> None:
        settings = self._settings_with("true")
        self.assertTrue(settings.memory_enabled)

    def test_valeur_false_desactive(self) -> None:
        """Le défaut : bool("false") valait True et activait la mémoire."""
        settings = self._settings_with("false")
        self.assertFalse(settings.memory_enabled)

    def test_valeur_false_stockee_comme_booleen(self) -> None:
        settings = self._settings_with("false")
        self.assertIsInstance(settings.get("memory_enabled"), bool)
        self.assertIs(settings.get("memory_enabled"), False)

    def test_valeur_majuscule_ignore(self) -> None:
        self.assertTrue(self._settings_with("TRUE").memory_enabled)
        self.assertFalse(self._settings_with("FALSE").memory_enabled)

    def test_valeurs_booleennes_usuelles(self) -> None:
        for truthy in ("1", "true", "yes", "on"):
            with self.subTest(value=truthy):
                self.assertTrue(self._settings_with(truthy).memory_enabled)
        for falsy in ("0", "false", "no", "off"):
            with self.subTest(value=falsy):
                self.assertFalse(self._settings_with(falsy).memory_enabled)

    def test_valeur_invalide_leve_une_erreur_explicite(self) -> None:
        with self.assertRaises(SettingsError):
            self._settings_with("peut-etre")


class TestMemoryEnabledFromConfigFile(unittest.TestCase):
    """Conversion de memory_enabled fourni par un fichier JSON."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_settings_")
        self.config_path = os.path.join(self.tmpdir, "config.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _settings_with_file(self, payload: dict) -> Settings:
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return Settings(config_path=self.config_path)

    def test_fichier_avec_booleen_vrai(self) -> None:
        settings = self._settings_with_file({"memory_enabled": True})
        self.assertTrue(settings.memory_enabled)

    def test_fichier_avec_booleen_faux(self) -> None:
        settings = self._settings_with_file({"memory_enabled": False})
        self.assertFalse(settings.memory_enabled)

    def test_fichier_avec_chaine_false(self) -> None:
        """Une chaîne "false" dans le JSON ne doit pas activer la mémoire."""
        settings = self._settings_with_file({"memory_enabled": "false"})
        self.assertFalse(settings.memory_enabled)

    def test_fichier_avec_chaine_true(self) -> None:
        settings = self._settings_with_file({"memory_enabled": "true"})
        self.assertTrue(settings.memory_enabled)

    def test_fichier_avec_valeur_invalide_leve_une_erreur(self) -> None:
        with self.assertRaises(SettingsError):
            self._settings_with_file({"memory_enabled": "peut-etre"})


class TestMemoryDisabledPreventsActivation(unittest.TestCase):
    """La désactivation configurationnelle empêche l'activation réelle."""

    def test_desactivation_bloque_la_creation_de_la_base(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="miles_test_settings_")
        try:
            db_path = os.path.join(tmpdir, "memory.db")
            env = {
                "MILES_MEMORY_ENABLED": "false",
                "MILES_MEMORY_DB_PATH": db_path,
            }
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with mock.patch.object(miles.CLI, "run", return_value=None):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            self.assertIsNone(mock_cli.call_args.kwargs["memory"])
            self.assertFalse(os.path.exists(db_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_activation_cree_la_base(self) -> None:
        """L'activation crée la base dans une racine autorisée (S-005)."""
        tmpdir = tempfile.mkdtemp(
            prefix="miles_test_settings_", dir=str(project_root() / "data")
        )
        try:
            db_path = os.path.join(tmpdir, "memory.db")
            env = {
                "MILES_MEMORY_ENABLED": "true",
                "MILES_MEMORY_DB_PATH": db_path,
            }
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with mock.patch.object(miles.CLI, "run", return_value=None):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            memory = mock_cli.call_args.kwargs["memory"]
            self.assertIsNotNone(memory)
            self.assertTrue(memory.is_available)
            memory.close()
            self.assertTrue(os.path.exists(db_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_base_hors_racines_non_creee(self) -> None:
        """S-005 : une base hors racines autorisées n'est pas créée."""
        tmpdir = tempfile.mkdtemp(prefix="miles_test_settings_out_")
        try:
            db_path = os.path.join(tmpdir, "memory.db")
            env = {
                "MILES_MEMORY_ENABLED": "true",
                "MILES_MEMORY_DB_PATH": db_path,
            }
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with mock.patch.object(miles.CLI, "run", return_value=None):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            self.assertIsNone(mock_cli.call_args.kwargs["memory"])
            self.assertFalse(os.path.exists(db_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
