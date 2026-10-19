"""Tests de validation de la configuration (Settings).

Ces tests vérifient que :
- Les valeurs par défaut sont chargées correctement.
- Un fournisseur inconnu lève SettingsError.
- Un history_limit invalide lève SettingsError.
- Aucune clé API n'est codée en dur.
"""

from __future__ import annotations

import unittest

from app.config.settings import Settings, SettingsError


class TestSettingsDefaults(unittest.TestCase):
    """Vérifier les valeurs par défaut de Settings."""

    def test_default_provider_is_remote(self) -> None:
        settings = Settings()
        self.assertEqual(settings.provider, "remote")

    def test_default_history_limit_is_10(self) -> None:
        settings = Settings()
        self.assertEqual(settings.get("history_limit"), 10)

    def test_default_voice_disabled(self) -> None:
        settings = Settings()
        self.assertEqual(settings.get("voice_enabled"), False)

    def test_allowed_actions_default(self) -> None:
        settings = Settings()
        self.assertEqual(
            settings.get("allowed_actions"),
            ["datetime", "workdir", "list_files"],
        )


class TestSettingsValidation(unittest.TestCase):
    """Vérifier que les configurations invalides sont rejetées."""

    def test_invalid_provider_raises(self) -> None:
        # Le provider par défaut est "remote" (valide).
        Settings()
        # Pour tester l'invalide, on utilise une variable d'environnement.
        import os

        os.environ["MILES_PROVIDER"] = "inconnu"
        try:
            with self.assertRaises(SettingsError):
                Settings()
        finally:
            del os.environ["MILES_PROVIDER"]

    def test_invalid_history_limit_raises(self) -> None:
        import os

        os.environ["MILES_HISTORY_LIMIT"] = "0"
        try:
            with self.assertRaises(SettingsError):
                Settings()
        finally:
            del os.environ["MILES_HISTORY_LIMIT"]

    def test_negative_history_limit_raises(self) -> None:
        import os

        os.environ["MILES_HISTORY_LIMIT"] = "-5"
        try:
            with self.assertRaises(SettingsError):
                Settings()
        finally:
            del os.environ["MILES_HISTORY_LIMIT"]


class TestSettingsNoHardcodedSecrets(unittest.TestCase):
    """Vérifier qu'aucune clé API n'est codée en dur dans Settings."""

    def test_no_api_key_in_defaults(self) -> None:
        settings = Settings()
        self.assertNotIn("remote_api_key", settings.DEFAULTS)
        self.assertNotIn("local_api_key", settings.DEFAULTS)

    def test_api_keys_only_from_environment(self) -> None:
        import os

        os.environ["MILES_REMOTE_API_KEY"] = "test-key-123"
        try:
            settings = Settings()
            self.assertEqual(settings.get("remote_api_key"), "test-key-123")
        finally:
            del os.environ["MILES_REMOTE_API_KEY"]


if __name__ == "__main__":
    unittest.main()
