"""Gestion de la conversation et de l'historique des messages.

L'historique est conservé en mémoire pour la session en cours uniquement.
Aucune mémoire persistante entre lancements n'est implémentée dans cette version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """Un message de la conversation."""

    role: str  # "user", "assistant", "system"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationError(Exception):
    """Erreur liée à la gestion de la conversation."""


class Conversation:
    """Historique ordonné des messages d'une session.

    Attributs:
        history_limit: Nombre maximal de messages transmis au fournisseur IA.
        system_prompt: Instruction système optionnelle préfixant l'historique.
    """

    def __init__(
        self,
        history_limit: int = 10,
        system_prompt: str | None = None,
    ) -> None:
        if history_limit < 1:
            raise ConversationError("history_limit doit être >= 1")
        self.history_limit = history_limit
        self.system_prompt = system_prompt
        self._messages: list[Message] = []

    def add_user_message(self, content: str) -> None:
        """Ajouter un message de l'utilisateur à l'historique."""
        self._messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: str) -> None:
        """Ajouter un message de l'assistant à l'historique."""
        self._messages.append(Message(role="assistant", content=content))

    def get_context(self) -> list[dict[str, str]]:
        """Retourner le contexte à transmettre au fournisseur IA.

        Inclut le prompt système (si défini) suivi des derniers messages
        jusqu'à history_limit.
        """
        context: list[dict[str, str]] = []
        if self.system_prompt:
            context.append({"role": "system", "content": self.system_prompt})

        # Prendre les derniers messages jusqu'à la limite
        recent = self._messages[-self.history_limit :]
        context.extend(m.to_dict() for m in recent)
        return context

    def clear(self) -> None:
        """Vider l'historique de la session."""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self) -> Any:
        return iter(self._messages)
