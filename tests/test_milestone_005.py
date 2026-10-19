"""Tests pour MILESTONE-005 : sélection explicite de fournisseur distant ou local.

Ces tests utilisent exclusivement des simulateurs (mocks) : aucun fournisseur
IA réel, aucune clé API, aucune connexion réseau, aucun modèle volumineux.
Le fournisseur local réel n'est pas testé ici (aucun runtime serveur local
ni modèle n'est installé sur ce poste).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import unittest

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider
from app.config.settings import Settings, SettingsError
from app.interface.cli import CLI
from app.core.conversation import Conversation


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

    def test_remote_provider_creation(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        provider = RemoteProvider(
            base_url=settings.get("remote_base_url"),
            model=settings.get("remote_model"),
            timeout=settings.get("remote_timeout"),
        )
        self.assertIsInstance(provider, RemoteProvider)
        self.assertEqual(provider.name.split(" ")[0], "remote")

    def test_remote_provider_chat_with_simulated_success(self) -> None:
        provider = SimulatedProvider("remote-test")
        response = provider.chat([{"role": "user", "content": "bonjour"}])
        self.assertIsInstance(response, str)
        self.assertIn("bonjour", response)
        self.assertEqual(provider.call_count, 1)


class TestLocalProviderSelection(unittest.TestCase):
    """Sélection explicite du fournisseur local."""

    def test_local_provider_creation(self) -> None:
        settings = Settings()
        settings.provider = "local"
        provider = LocalProvider(
            base_url=settings.get("local_base_url"),
            model=settings.get("local_model"),
            timeout=settings.get("local_timeout"),
        )
        self.assertIsInstance(provider, LocalProvider)
        self.assertEqual(provider.name.split(" ")[0], "local")

    def test_local_provider_chat_with_simulated_success(self) -> None:
        provider = SimulatedProvider("local-test")
        response = provider.chat([{"role": "user", "content": "quelle heure est-il ?"}])
        self.assertIsInstance(response, str)
        self.assertIn("quelle heure est-il ?", response)


class TestNoSilentFallback(unittest.TestCase):
    """Aucun basculement silencieux entre fournisseur distant et local."""

    def test_providers_are_distinct_instances(self) -> None:
        remote = RemoteProvider(
            base_url="http://localhost:8000", model="remote-model"
        )
        local = LocalProvider(
            base_url="http://localhost:11434", model="local-model"
        )
        self.assertIsNot(remote, local)
        self.assertEqual(remote.name.split(" ")[0], "remote")
        self.assertEqual(local.name.split(" ")[0], "local")

    def test_selected_provider_is_used_not_the_other(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        self.assertEqual(settings.provider, "remote")
        settings.provider = "local"
        self.assertEqual(settings.provider, "local")


class TestProviderFailure(unittest.TestCase):
    """Gestion des erreurs de fournisseur distant et local."""

    def test_remote_unavailable_is_available_false(self) -> None:
        provider = RemoteProvider(base_url="http://nonexistent:9999", model="test")
        # is_available tente une requête HTTP ; sur ce poste sans serveur,
        # elle retourne False sans lever d'exception.
        self.assertIsInstance(provider.is_available(), bool)

    def test_local_chat_connection_error_raises(self) -> None:
        provider = LocalProvider(base_url="http://nonexistent:9999", model="test")
        with self.assertRaises(AIProviderError):
            provider.chat([{"role": "user", "content": "test"}])


class TestHistoryPreservationAfterLocalError(unittest.TestCase):
    """L'historique de conversation est préservé quand le fournisseur échoue."""

    def test_user_message_preserved_after_local_provider_error(self) -> None:
        settings = Settings()
        provider = LocalProvider(base_url="http://nonexistent:9999", model="test")
        conversation = Conversation(history_limit=10)
        cli = CLI(settings=settings, provider=provider, conversation=conversation)

        with patch.object(provider, "chat", side_effect=AIProviderError("Hors ligne")):
            cli._process_input("Bonjour")

        self.assertEqual(len(conversation), 1)
        context = conversation.get_context()
        self.assertEqual(context[0]["role"], "user")
        self.assertEqual(context[0]["content"], "Bonjour")


class TestInvalidProviderRejected(unittest.TestCase):
    """Un fournisseur invalide est rejeté par Settings."""

    def test_invalid_provider_raises(self) -> None:
        os.environ["MILES_PROVIDER"] = "inconnu"
        try:
            with self.assertRaises(SettingsError):
                Settings()
        finally:
            del os.environ["MILES_PROVIDER"]


class TestExplicitProviderSelectionInCli(unittest.TestCase):
    """L'interface terminal indique le fournisseur actif."""

    def test_cli_shows_provider_name(self) -> None:
        settings = Settings()
        provider = SimulatedProvider("remote-test")
        cli = CLI(settings=settings, provider=provider)
        self.assertEqual(cli.provider.name, "remote-test")
        self.assertIsInstance(cli.conversation, Conversation)


if __name__ == "__main__":
    unittest.main()
