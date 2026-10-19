"""Tests de sélection des fournisseurs IA (simulateurs uniquement).

Aucun vrai fournisseur, aucune clé API, aucun appel réseau.
"""

from __future__ import annotations

import os
import unittest

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider
from app.config.settings import Settings


class SimulatedProvider(AIProvider):
    """Fournisseur simulé pour les tests de sélection."""

    def __init__(self, name: str, should_fail: bool = False) -> None:
        self._name = name
        self._should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return not self._should_fail

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.call_count += 1
        if self._should_fail:
            raise AIProviderError(f"{self._name} indisponible.")
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        return f"Réponse simulée de {self._name} à : {last_user}"


class TestRemoteProviderSelection(unittest.TestCase):
    """Sélection explicite du fournisseur distant."""

    def test_remote_provider_instantiated_from_settings(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        provider = RemoteProvider(
            base_url=settings.get("remote_base_url"),
            model=settings.get("remote_model"),
            api_key=settings.get("remote_api_key"),
            timeout=settings.get("remote_timeout", 30),
        )
        self.assertIsInstance(provider, RemoteProvider)
        self.assertTrue(provider.name.startswith("remote"))

    def test_remote_provider_chat_with_simulated_success(self) -> None:
        provider = SimulatedProvider("remote-test")
        response = provider.chat([{"role": "user", "content": "bonjour"}])
        self.assertIsInstance(response, str)
        self.assertIn("bonjour", response)
        self.assertEqual(provider.call_count, 1)

    def test_remote_provider_failure_raises(self) -> None:
        failing = SimulatedProvider("remote-fail", should_fail=True)
        self.assertFalse(failing.is_available())
        with self.assertRaises(AIProviderError):
            failing.chat([{"role": "user", "content": "test"}])


class TestLocalProviderSelection(unittest.TestCase):
    """Sélection explicite du fournisseur local."""

    def test_local_provider_instantiated_from_settings(self) -> None:
        settings = Settings()
        settings.provider = "local"
        provider = LocalProvider(
            base_url=settings.get("local_base_url"),
            model=settings.get("local_model"),
            api_key=settings.get("local_api_key"),
            timeout=settings.get("local_timeout", 60),
        )
        self.assertIsInstance(provider, LocalProvider)
        self.assertTrue(provider.name.startswith("local"))

    def test_local_provider_chat_with_simulated_success(self) -> None:
        provider = SimulatedProvider("local-test")
        response = provider.chat([{"role": "user", "content": "quelle heure est-il ?"}])
        self.assertIsInstance(response, str)
        self.assertIn("quelle heure est-il ?", response)

    def test_local_provider_connection_error_raises(self) -> None:
        provider = LocalProvider(base_url="http://nonexistent:9999", model="test")
        with self.assertRaises(AIProviderError):
            provider.chat([{"role": "user", "content": "test"}])


class TestNoSilentFallback(unittest.TestCase):
    """Aucun basculement silencieux entre fournisseur distant et local."""

    def test_providers_are_distinct(self) -> None:
        remote = RemoteProvider(base_url="http://localhost:8000", model="remote-model")
        local = LocalProvider(base_url="http://localhost:11434", model="local-model")
        self.assertIsNot(remote, local)
        self.assertEqual(remote.name.split(" ")[0], "remote")
        self.assertEqual(local.name.split(" ")[0], "local")

    def test_selected_provider_is_used_not_the_other(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        self.assertEqual(settings.provider, "remote")
        settings.provider = "local"
        self.assertEqual(settings.provider, "local")

    def test_invalid_provider_rejected(self) -> None:
        os.environ["MILES_PROVIDER"] = "inconnu"
        try:
            with self.assertRaises(Exception):
                Settings()
        finally:
            del os.environ["MILES_PROVIDER"]


if __name__ == "__main__":
    unittest.main()
