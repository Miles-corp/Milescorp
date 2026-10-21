"""Package mémoire de MILES.

Historique de conversation en session (Conversation, Message), mémoire
persistante de souvenirs explicites (PersistentMemory) et persistance des
transcriptions de conversation (ConversationTranscript).

Tous les symboles sont exposés **paresseusement** : ``app.core.conversation``
importe ``app.memory.transcript`` (pour l'exception de persistance) et
``app.memory.history`` importe ``app.core.conversation``. Un import direct
créerait donc un cycle d'import.
"""

from typing import Any

__all__ = [
    "Conversation",
    "Message",
    "History",
    "PersistentMemory",
    "PersistentMemoryError",
    "ConversationTranscript",
    "TranscriptError",
]

_LAZY_IMPORTS = {
    "Conversation": ("app.core.conversation", "Conversation"),
    "Message": ("app.core.conversation", "Message"),
    "History": ("app.memory.history", "History"),
    "PersistentMemory": ("app.memory.persistent", "PersistentMemory"),
    "PersistentMemoryError": ("app.memory.persistent", "PersistentMemoryError"),
    "ConversationTranscript": ("app.memory.transcript", "ConversationTranscript"),
    "TranscriptError": ("app.memory.transcript", "TranscriptError"),
}


def __getattr__(name: str) -> Any:
    """Importer un symbole à la demande pour éviter les cycles d'import."""
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(target[0])
    return getattr(module, target[1])


def __dir__() -> list[str]:
    return sorted(__all__)
