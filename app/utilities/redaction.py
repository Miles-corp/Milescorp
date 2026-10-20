"""Détection et neutralisation des secrets dans les textes sortants.

Source unique de vérité pour les motifs de secrets de MILES. Utilisé par :
- l'interface web (``app/interface/web.py``) avant toute journalisation ;
- la persistance des conversations (``app/memory/transcript.py``) avant écriture
  sur disque.

Aucune clé API, aucun mot de passe et aucun jeton ne doit quitter le
processus ni être écrit dans un fichier ou un journal.
"""

from __future__ import annotations

import re
from typing import Pattern

#: Marqueur remplacement d'un secret détecté.
REDACTED = "[REDACTED]"

# Motifs de secrets qui ne doivent jamais quitter le processus.
_SECRET_PATTERNS: tuple[Pattern[str], ...] = (
    # Clés de type "sk-..." (fournisseur IA distant).
    re.compile(r"sk-[A-Za-z0-9_\-]{4,}"),
    # En-têtes d'authentification "Bearer ..." / "Basic ...".
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._\-]{4,}"),
    # Paires "cle=valeur" pour les noms de secrets connus.
    re.compile(
        r"(?i)\b(?:api[_-]?key|apikey|token|secret|password|passwd|pwd"
        r"|credential|private[_-]?key|access[_-]?key)\b"
        r"\s*[:=]\s*[\"']?[^\s\"',;]+"
    ),
    # Valeurs isolées de type "password: monmotdepasse".
    re.compile(
        r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key)\b"
        r"\s*[:=]\s*[\"']?[^\s\"',;]{4,}"
    ),
)


def sanitize_text(text: object) -> str:
    """Remplacer les secrets potentiels d'un message par un marqueur.

    Appliqué avant toute écriture dans les journaux internes ou sur disque.
    Le texte d'origine n'est jamais renvoyé au client HTTP.
    """
    sanitized = str(text)
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(REDACTED, sanitized)
    return sanitized


def contains_secret(text: object) -> bool:
    """Indiquer si un texte contient un motif de secret détectable."""
    candidate = str(text)
    return any(pattern.search(candidate) for pattern in _SECRET_PATTERNS)
