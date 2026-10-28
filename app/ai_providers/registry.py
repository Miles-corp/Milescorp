"""Registre des fournisseurs MILES (L2, extensible).

Ajouter un fournisseur = 1 ligne dans ``FABRIQUES`` + 1 module adaptateur
implémentant ``AIProvider`` (chat, is_available, name). Aucune seconde
architecture parallèle : tout le reste de MILES consomme ``AIProvider``.

Règles :
- **aucun modèle d'identifiant inventé** : ``build_provider`` exige un
  modèle (fourni par la configuration utilisateur) ;
- URLs par défaut uniquement pour les protocoles connus (compat OpenAI) ;
- les échecs lèvent ValueError avec un message explicite, sans secret.
"""

from __future__ import annotations

from typing import Any

from app.ai_providers.anthropic import AnthropicProvider
from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.gemini import GeminiProvider, GEMINI_BASE
from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider

#: Fabric : nom -> (classe, url_base_defaut | None, protocole)
#: protocole : "openai" (compat OpenAI : POST {base}/v1/chat/completions),
#: "anthropic" (native), "gemini" (native).
FABRIQUES: dict[str, dict[str, Any]] = {
    "groq": {
        "classe": RemoteProvider,
        "base": "https://api.groq.com/openai/v1",
        "protocole": "openai",
    },
    "openai": {
        "classe": RemoteProvider,
        "base": "https://api.openai.com/v1",
        "protocole": "openai",
    },
    "anthropic": {
        "classe": AnthropicProvider,
        "base": "https://api.anthropic.com",
        "protocole": "anthropic",
    },
    "gemini": {
        "classe": GeminiProvider,
        "base": GEMINI_BASE,
        "protocole": "gemini",
    },
}


def fournisseurs_soutenus() -> list[str]:
    """Noms de fournisseurs supportés (ordre stable pour l'interface)."""
    return list(FABRIQUES)


def est_soutenu(nom: str) -> bool:
    return (nom or "").strip().lower() in FABRIQUES


def build_provider(
    nom: str,
    *,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = 30,
) -> AIProvider:
    """Construire le bon adaptateur pour le fournisseur demandé.

    Args:
        nom: identifiant du fournisseur (voir fournisseurs_soutenus()).
        model: **obligatoire** — jamais d'identifiant inventé par MILES.
        api_key: clé du fournisseur (None = non configuré, l'adaptateur
            refusera proprement plutôt que d'appeler sans identité).
        base_url: surcharge d'URL de base (défaut = URL du protocole).
        timeout: délai en secondes.

    Raises:
        ValueError: fournisseur inconnu ou modèle manquant (aucun secret
            dans le message).
    """
    cle = (nom or "").strip().lower()
    if cle not in FABRIQUES:
        raise ValueError(
            f"Fournisseur inconnu : {nom!r} (supportes : "
            f"{', '.join(FABRIQUES)})"
        )
    modele = str(model or "").strip()
    if not modele:
        raise ValueError(
            f"Modele manquant pour {cle} : choisissez-le avec /model <nom>."
        )
    fabrique = FABRIQUES[cle]
    base = base_url or fabrique["base"]
    return fabrique["classe"](
        base_url=base, model=modele, api_key=api_key, timeout=timeout
    )


__all__ = [
    "AIProvider",
    "AIProviderError",
    "AnthropicProvider",
    "FABRIQUES",
    "GeminiProvider",
    "LocalProvider",
    "RemoteProvider",
    "build_provider",
    "est_soutenu",
    "fournisseurs_soutenus",
]
