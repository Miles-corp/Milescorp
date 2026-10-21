"""Messages publics et diagnostics techniques pour les erreurs de fournisseur.

Sépare deux usages qui ne doivent jamais être confondus :

- le **message public**, destiné à l'utilisateur ou au client HTTP : il ne
  doit révéler ni clé API, ni corps de réponse, ni détail technique ;
- le **détail technique**, destiné aux journaux locaux : il conserve de quoi
  diagnostiquer mais passe par la rédaction des secrets.

Ce module est la source unique utilisée par l'interface terminal
(``app/interface/cli.py``) et par l'interface web (``app/interface/web.py``).
"""

from __future__ import annotations

from app.utilities.redaction import sanitize_text

#: Messages publics, par situation. Aucun ne contient de détail technique.
_PUBLIC_MESSAGES = {
    "auth": "Erreur du fournisseur IA : authentification refusée.",
    "quota": "Erreur du fournisseur IA : quota atteint chez le fournisseur.",
    "not_found": "Erreur du fournisseur IA : modèle ou ressource introuvable.",
    "timeout": "Erreur du fournisseur IA : délai d'attente dépassé.",
    "invalid": "Erreur du fournisseur IA : réponse invalide du fournisseur.",
    "unavailable": "Erreur du fournisseur IA : fournisseur indisponible.",
    "network": "Erreur du fournisseur IA : échec de la communication avec le fournisseur.",
}


def _classify(detail: str) -> str:
    """Déterminer la situation d'une erreur fournisseur à partir de son texte."""
    lowered = detail.lower()
    if "401" in lowered or "403" in lowered or "authentification" in lowered:
        return "auth"
    if "429" in lowered or "quota" in lowered or "rate limit" in lowered:
        return "quota"
    if "404" in lowered or "introuvable" in lowered or "not found" in lowered:
        return "not_found"
    if "timeout" in lowered or "délai" in lowered or "delai" in lowered:
        return "timeout"
    if "invalide" in lowered or "non-json" in lowered:
        return "invalid"
    if "indisponible" in lowered or "impossible de joindre" in lowered:
        return "unavailable"
    return "network"


def public_provider_error(exc: Exception) -> str:
    """Retourner un message public sûr pour une erreur de fournisseur.

    Le message d'origine n'est jamais transmis : il peut contenir une clé
    d'API, un jeton, un corps de réponse du fournisseur ou une URL interne.
    Seule une classification contrôlée est exposée.
    """
    return _PUBLIC_MESSAGES[_classify(str(exc))]


def technical_detail(exc: Exception) -> str:
    """Retourner un diagnostic technique expurgé de tout secret.

    Le résultat est destiné aux journaux locaux uniquement. Il contient le
    type de l'exception et son message après application de la rédaction des
    secrets.
    """
    return f"{type(exc).__name__}: {sanitize_text(exc)}"
