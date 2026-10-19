"""Tests du historique de conversation et du contexte.

Ces tests n'utilisent aucun fournisseur IA réel ni clé API.
Ils s'exécutent avec la bibliothèque standard unittest de Python 3.
"""

from __future__ import annotations

import unittest

from app.core.conversation import Conversation, ConversationError


class TestConversation(unittest.TestCase):
    """Tests de la classe Conversation."""

    def test_add_user_and_assistant_messages(self) -> None:
        conv = Conversation(history_limit=5)
        conv.add_user_message("Bonjour")
        conv.add_assistant_message("Bonjour ! Comment allez-vous ?")
        self.assertEqual(len(conv), 2)

    def test_context_includes_system_prompt(self) -> None:
        conv = Conversation(history_limit=5, system_prompt="Tu es un assistant.")
        conv.add_user_message("Question")
        context = conv.get_context()
        self.assertEqual(context[0], {"role": "system", "content": "Tu es un assistant."})
        self.assertEqual(context[1], {"role": "user", "content": "Question"})

    def test_history_limit_respected(self) -> None:
        conv = Conversation(history_limit=2)
        for i in range(5):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"rep {i}")
        context = conv.get_context()
        # 2 derniers échanges = 4 messages maximum (pas de system_prompt)
        self.assertEqual(len(context), 4)

    def test_history_limit_minimum_one(self) -> None:
        conv = Conversation(history_limit=1)
        conv.add_user_message("a")
        conv.add_assistant_message("b")
        conv.add_user_message("c")
        context = conv.get_context()
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0], {"role": "user", "content": "c"})

    def test_invalid_history_limit_raises(self) -> None:
        with self.assertRaises(ConversationError):
            Conversation(history_limit=0)

    def test_clear_empties_history(self) -> None:
        conv = Conversation(history_limit=5)
        conv.add_user_message("test")
        self.assertEqual(len(conv), 1)
        conv.clear()
        self.assertEqual(len(conv), 0)
        self.assertEqual(conv.get_context(), [])

    def test_message_to_dict(self) -> None:
        msg = Message(role="user", content="coucou")
        self.assertEqual(msg.to_dict(), {"role": "user", "content": "coucou"})


if __name__ == "__main__":
    unittest.main()
