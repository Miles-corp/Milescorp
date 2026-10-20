"""Gestion de la conversation et de l'historique des messages.

L'historique est conservé en mémoire pour la session en cours. Depuis la
version V1, il peut également être **persisté** localement via un
:class:`~app.memory.transcript.ConversationTranscript` : les messages sont
alors conservés d'un lancement à l'autre et la conversation peut être
restaurée au démarrage.

L'API mémoire seule reste inchangée : sans transcripteur, une
``Conversation`` se comporte exactement comme auparavant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover — import de type uniquement
    # Import différé : app.memory ré-exporte Conversation, ce qui créerait un
    # cycle si l'import était fait à l'exécution.
    from app.memory.transcript import ConversationTranscript


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
        transcript: Transcripteur optionnel pour la persistance locale.
        conversation_id: Identifiant de la conversation courante (None si la
            conversation n'est pas persistée).
    """

    def __init__(
        self,
        history_limit: int = 10,
        system_prompt: str | None = None,
        transcript: Optional["ConversationTranscript"] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        if history_limit < 1:
            raise ConversationError("history_limit doit être >= 1")
        self.history_limit = history_limit
        self.system_prompt = system_prompt
        self.transcript = transcript
        self.conversation_id = conversation_id
        self._messages: list[Message] = []

    # --- Persistance ---

    @property
    def is_persistent(self) -> bool:
        """Indiquer si la conversation est adossée à un transcripteur actif."""
        return (
            self.transcript is not None
            and self.transcript.is_available
            and self.conversation_id is not None
        )

    def attach_transcript(
        self,
        transcript: "ConversationTranscript",
        conversation_id: Optional[str] = None,
    ) -> None:
        """Adosser la conversation à un transcripteur.

        Si ``conversation_id`` est fourni, la conversation correspondante est
        restaurée en mémoire. Sinon, une nouvelle conversation est créée.
        """
        self.transcript = transcript
        if transcript is None or not transcript.is_available:
            self.conversation_id = None
            return

        if conversation_id is None:
            self.conversation_id = transcript.create_conversation()
        else:
            self.conversation_id = conversation_id
            self.restore()

    def restore(self, conversation_id: Optional[str] = None) -> int:
        """Restaurer une conversation depuis la persistance.

        Retourne le nombre de messages restaurés. L'historique en mémoire
        est remplacé par le contenu de la conversation persistée.
        """
        if self.transcript is None or not self.transcript.is_available:
            return 0
        target = conversation_id or self.conversation_id
        if not target:
            return 0

        rows = self.transcript.load_messages(target)
        self._messages = [
            Message(role=str(row["role"]), content=str(row["content"]))
            for row in rows
        ]
        self.conversation_id = target
        return len(self._messages)

    def new_conversation(self) -> Optional[str]:
        """Démarrer une nouvelle conversation persistée et vider l'historique."""
        self._messages.clear()
        if self.transcript is None or not self.transcript.is_available:
            self.conversation_id = None
            return None
        self.conversation_id = self.transcript.create_conversation()
        return self.conversation_id

    # --- Messages ---

    def add_user_message(self, content: str) -> None:
        """Ajouter un message de l'utilisateur à l'historique."""
        self._messages.append(Message(role="user", content=content))
        self._persist("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Ajouter un message de l'assistant à l'historique."""
        self._messages.append(Message(role="assistant", content=content))
        self._persist("assistant", content)

    def _persist(self, role: str, content: str) -> None:
        """Enregistrer un message dans la transcription, si elle est active."""
        if not self.is_persistent:
            return
        assert self.transcript is not None
        assert self.conversation_id is not None
        self.transcript.save_message(self.conversation_id, role, content)

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
        """Vider l'historique de la session.

        L'historique persisté n'est pas modifié : la conversation reste
        restaurable après un redémarrage.
        """
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def __iter__(self) -> Any:
        return iter(self._messages)
