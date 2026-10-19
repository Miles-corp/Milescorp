"""Package mémoire de MILES.

Ce module expose une classe History pratique construite au-dessus de
Conversation, pour un usage orienté session.
"""

from __future__ import annotations

from app.core.conversation import Conversation, Message


class History:
    """Historique de conversation pour une session active.

    Enveloppe Conversation avec une API centrée sur l'échange utilisateur /
    assistant.
    """

    def __init__(self, history_limit: int = 10) -> None:
        self._conversation = Conversation(history_limit=history_limit)

    def user_said(self, content: str) -> None:
        self._conversation.add_user_message(content)

    def assistant_replied(self, content: str) -> None:
        self._conversation.add_assistant_message(content)

    def context(self) -> list[dict[str, str]]:
        return self._conversation.get_context()

    def reset(self) -> None:
        self._conversation.clear()

    def __len__(self) -> int:
        return len(self._conversation)
