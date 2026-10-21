"""Premier outil MILES : lecture du statut du programme.

Outil en lecture seule, sans effet de bord. Il retourne un état de
**référence statique** : ces valeurs sont fixes et ne reflètent pas l'état
en direct de l'instance en cours d'exécution (le moteur exécute les
handlers dans un sous-processus, qui ne partage pas l'état de l'application).
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
