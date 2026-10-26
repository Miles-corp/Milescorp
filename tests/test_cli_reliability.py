"""Tests de fiabilité de l'interface terminal (CLI).

Ces tests vérifient que :
- L'historique de conversation est préservé quand le fournisseur IA lève une erreur.
- Les commandes de terminal (/clear, /status) fonctionnent correctement.
- Aucun fournisseur IA réel ni clé API n'est utilisé.
"""

from __future__ import annotations

import io
import unittest
from unittest import mock

from app.ai_providers.base import AIProvider, AIProviderError
from app.core.conversation import Conversation
from app.interface.cli import CLI
from app.config.settings import Settings


class FailingProvider(AIProvider):
    """Fournisseur qui lève systématiquement AIProviderError."""

    def __init__(self) -> None:
        self._name = "failing-test"

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return False

    def chat(self, messages: list[dict[str, str]]) -> str:
        raise AIProviderError("Fournisseur simulé en panne.")


class TestCLIProviderError(unittest.TestCase):
    """Vérifier que les erreurs de fournisseur ne cassent pas la session."""

    def setUp(self) -> None:
        self.settings = Settings()
        self.provider = FailingProvider()
        # NOTE : ne PAS passer conversation au constructeur CLI — voir défaut L-005
        # (cli.py ignore l'argument conversation à cause de `conversation or Conversation(...)`).
        self.cli = CLI(settings=self.settings, provider=self.provider)
        self.conversation = self.cli.conversation

    def test_user_message_preserved_after_provider_error(self) -> None:
        """Quand le fournisseur échoue, le message utilisateur reste dans l'historique."""
        self.cli._process_input("Bonjour")
        self.assertEqual(len(self.conversation), 1)
        context = self.conversation.get_context()
        self.assertEqual(context[0]["role"], "user")
        self.assertEqual(context[0]["content"], "Bonjour")

    def test_no_assistant_message_added_on_error(self) -> None:
        """Aucun message assistant n'est ajouté quand le fournisseur échoue."""
        self.cli._process_input("Bonjour")
        context = self.conversation.get_context()
        assistant_messages = [m for m in context if m["role"] == "assistant"]
        self.assertEqual(len(assistant_messages), 0)

    def test_can_retry_after_error(self) -> None:
        """L'utilisateur peut envoyer un nouveau message après une erreur."""
        self.cli._process_input("Premier message")
        self.cli._process_input("Deuxième message")
        self.assertEqual(len(self.conversation), 2)
        context = self.conversation.get_context()
        self.assertEqual(context[0]["content"], "Premier message")
        self.assertEqual(context[1]["content"], "Deuxième message")

    def test_clear_command_empties_history(self) -> None:
        """La commande /clear vide l'historique."""
        self.conversation.add_user_message("test")
        self.assertEqual(len(self.conversation), 1)
        self.cli._handle_command("/clear")
        self.assertEqual(len(self.conversation), 0)

    def test_status_command_no_provider(self) -> None:
        """La commande /status ne lève pas d'exception sans fournisseur."""
        try:
            self.cli._handle_command("/status")
        except Exception as exc:
            self.fail(f"/status a levé une exception : {exc}")




class TestCLIInputEncoding(unittest.TestCase):
    """Tests de lecture de l'entree standard (encodage UTF-8)."""

    def setUp(self) -> None:
        self.settings = Settings()
        self.cli = CLI(settings=self.settings)

    def test_read_input_normal(self) -> None:
        """Lecture normale de 'hello'."""
        with mock.patch("sys.stdin", io.BytesIO(b"hello\n")):
            result = self.cli._read_input()
        self.assertEqual(result, "hello")

    def test_read_input_french_accents(self) -> None:
        """Lecture d'un texte francais avec accents."""
        text = "Bonjour, ?a fonctionne ? No?l."
        with mock.patch("sys.stdin", io.BytesIO(text.encode("utf-8") + b"\n")):
            result = self.cli._read_input()
        self.assertEqual(result, text)

    def test_read_input_unicode(self) -> None:
        """Lecture de caracteres Unicode valides."""
        text = "H?llo 🌍 caf?"
        with mock.patch("sys.stdin", io.BytesIO(text.encode("utf-8") + b"\n")):
            result = self.cli._read_input()
        self.assertEqual(result, text)

    def test_read_input_eof(self) -> None:
        """Comportement en fin de fichier (EOF)."""
        with mock.patch("sys.stdin", io.BytesIO(b"")):
            with self.assertRaises(EOFError):
                self.cli._read_input()

    def test_read_input_encoding_error(self) -> None:
        """Gestion controlee d'une erreur d'encodage simulee."""
        with mock.patch("sys.stdin", io.BytesIO(b"hell\xc3\n")):
            result = self.cli._read_input()
        self.assertIsInstance(result, str)

    def test_process_input_help(self) -> None:
        """La commande /help fonctionne."""
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            self.cli._process_input("/help")
        self.assertIn("Commandes disponibles", out.getvalue())

    def test_process_input_quit(self) -> None:
        """La commande /quit arrete la boucle."""
        self.cli._process_input("/quit")
        self.assertFalse(self.cli._running)


if __name__ == "__main__":
    unittest.main()
