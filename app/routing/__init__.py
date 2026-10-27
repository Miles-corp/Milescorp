"""Package de routage des demandes MILES (Q1)."""

from app.routing.router import (
    APPROFONDI_ROLE,
    RAPIDE_ROLE,
    classifier,
    cible,
    journaliser,
    rendre_compte,
    router_actif,
)

__all__ = [
    "APPROFONDI_ROLE",
    "RAPIDE_ROLE",
    "classifier",
    "cible",
    "journaliser",
    "rendre_compte",
    "router_actif",
]
