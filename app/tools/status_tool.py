"""Premier outil MILES : lecture du statut du programme.

Outil en lecture seule, sans effet de bord. Il retourne l'état courant
du programme (fournisseur IA, historique, mémoire persistante) pour
permettre au modèle de connaître le contexte actuel.
"""

from __future__ import annotations

from typing import Any, Dict


def status_tool_handler() -> Dict[str, Any]:
    """Retourner le statut courant de MILES.

    Cet outil est purement informatif : il ne modifie aucun état et ne
    produit aucun effet de bord.
    """
    return {
        "status": "ok",
        "provider": "non configure",
        "provider_available": False,
        "memory_enabled": False,
        "memory_available": False,
        "messages_in_history": 0,
    }
