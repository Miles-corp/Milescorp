"""Interface commune des fournisseurs IA.

Tous les fournisseurs (distant, local) implémentent cette interface afin que
le reste de MILES n'ait pas à connaître leur implémentation particulière.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProviderError(Exception):
    """Erreur levée par un fournisseur IA."""


class AIProvider(ABC):
    """Interface abstraite pour un fournisseur de modèle IA."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> str:
        """Envoyer une liste de messages et retourner la réponse textuelle.

        Args:
            messages: Liste de dictionnaires {"role": "user"|"assistant"|"system", "content": str}.

        Returns:
            Le texte de la réponse de l'assistant.

        Raises:
            AIProviderError: si le fournisseur est indisponible ou retourne une erreur.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Retourner True si le fournisseur semble joignable (sans effectuer de requête complète)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom lisible du fournisseur."""
