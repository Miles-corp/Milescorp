"""Tests des fournisseurs IA avec des simulateurs (mocks).

Aucune clé API, aucune connexion réseau, aucun vrai modèle n'est utilisé.
Ces tests vérifient la séparation entre fournisseur distant et fournisseur local
ainsi que la gestion de l'indisponibilité.
"""

from __future__ import annotations

import unittest

from app.ai_providers.base import AIProvider, AIProviderError


class SimulatedProvider(AIProvider):
    """Fournisseur simulé pour les tests."""

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
            raise AIProviderError(f"Le fournisseur {self._name} est indisponible.")
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        return f"Réponse simulée de {self._name} à : {last_user}"


class TestProviders(unittest.TestCase):
    """Tests de l'interface commune des fournisseurs IA."""

    def test_remote_and_local_have_common_interface(self) -> None:
        remote = SimulatedProvider("remote-test")
        local = SimulatedProvider("local-test")

        for provider in (remote, local):
            self.assertIsInstance(provider, AIProvider)
            self.assertIsInstance(provider.name, str)
            self.assertIsInstance(provider.is_available(), bool)
            response = provider.chat([{"role": "user", "content": "bonjour"}])
            self.assertIsInstance(response, str)
            self.assertIn("bonjour", response)

    def test_provider_failure_raises(self) -> None:
        failing = SimulatedProvider("failing", should_fail=True)
        self.assertFalse(failing.is_available())
        with self.assertRaises(AIProviderError):
            failing.chat([{"role": "user", "content": "test"}])

    def test_provider_call_count(self) -> None:
        provider = SimulatedProvider("counter")
        provider.chat([{"role": "user", "content": "a"}])
        provider.chat([{"role": "user", "content": "b"}])
        self.assertEqual(provider.call_count, 2)

    def test_context_passed_to_provider(self) -> None:
        provider = SimulatedProvider("context-test")
        messages = [
            {"role": "system", "content": "Tu es utile."},
            {"role": "user", "content": "quelle heure est-il ?"},
        ]
        response = provider.chat(messages)
        self.assertIn("quelle heure est-il ?", response)


if __name__ == "__main__":
    unittest.main()
