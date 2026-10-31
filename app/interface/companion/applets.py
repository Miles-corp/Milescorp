"""Registre typé des applets du site Miles Companion.

Trois types, jamais mélangés :

``system``
    Lit une primitive réelle du poste (CPU, mémoire, disque, réseau…).
    Aucune action, aucune donnée inventée.

``render``
    Affiche un état déjà calculé ailleurs (missions, mémoire, fournisseur).
    Lecture seule.

``action``
    Déclenche un effet réel. Toute action exige une **confirmation
    explicite** et un jeton à usage unique ; les actions récurrentes
    deviennent des missions, le reste va au journal.

Le registre est la seule source de vérité : le serveur refuse un identifiant
absent, et l'interface ne peut pas inventer une action.
"""

from __future__ import annotations

from typing import Any, Optional

APPELS: tuple[dict[str, Any], ...] = (
    {
        "id": "device.telemetry",
        "title": "Capteurs du poste",
        "description": "CPU, mémoire, disque, réseau, températures : mesures réelles avec âge et source.",
        "type": "system",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "device.box",
        "title": "Boîtier",
        "description": "Relevé du backend boîtier local (port 8095), ou « indisponible » avec la raison.",
        "type": "system",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "missions.list",
        "title": "Missions récentes",
        "description": "Liste des missions avec leur état réel.",
        "type": "render",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "missions.detail",
        "title": "Détail d'une mission",
        "description": "Étapes, résultats, code écrit et liens mémoire d'une mission.",
        "type": "render",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "memory.list",
        "title": "Mémoire",
        "description": "Souvenirs explicites, nature (fait/hypothèse) et liens de contradiction.",
        "type": "render",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "provider.status",
        "title": "Fournisseur IA",
        "description": "Fournisseur actif et état configuré, sans jamais afficher de clé ni sa longueur.",
        "type": "render",
        "role": "user",
        "dev_only": False,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "journal.recent",
        "title": "Journal récent",
        "description": "Journal d'audit expurgé, visible en mode développeur.",
        "type": "render",
        "role": "user",
        "dev_only": True,
        "confirmation": None,
        "creates_mission": False,
    },
    {
        "id": "mission.create",
        "title": "Lancer une mission",
        "description": "Créer une mission à partir d'un objectif ; l'exécution reste bornée par MILES.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Lancer réellement cette mission ?",
        "creates_mission": True,
    },
    {
        "id": "mission.answer",
        "title": "Répondre à une mission",
        "description": "Transmettre une réponse à une demande de clarification en attente.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Envoyer cette réponse à la mission ?",
        "creates_mission": False,
    },
    {
        "id": "mission.authorize",
        "title": "Autoriser une action",
        "description": "Accorder ou refuser une autorisation demandée par une mission.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Appliquer cette décision d'autorisation ?",
        "creates_mission": False,
    },
    {
        "id": "mission.cancel",
        "title": "Annuler une mission",
        "description": "Demander l'arrêt d'une mission en cours.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Annuler cette mission ?",
        "creates_mission": False,
    },
    {
        "id": "routine.run",
        "title": "Lancer une routine",
        "description": "Transformer une action récurrente en mission réelle.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Lancer cette routine maintenant ?",
        "creates_mission": True,
    },
    {
        "id": "provider.activate",
        "title": "Activer un fournisseur",
        "description": "Activer un fournisseur déjà configuré sur la box.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Activer ce fournisseur pour MILES ?",
        "creates_mission": False,
    },
    {
        "id": "provider.test",
        "title": "Tester un fournisseur",
        "description": "Vérifier la disponibilité du fournisseur actif ; aucune clé n'est affichée.",
        "type": "action",
        "role": "user",
        "dev_only": False,
        "confirmation": "Lancer un test de disponibilité ?",
        "creates_mission": False,
    },
)

_BY_ID = {item["id"]: item for item in APPELS}


def all_applets() -> list[dict[str, Any]]:
    return [dict(item) for item in APPELS]


def get(applet_id: str) -> Optional[dict[str, Any]]:
    item = _BY_ID.get(applet_id)
    return dict(item) if item else None


def visible(role: str, dev_mode: bool) -> list[dict[str, Any]]:
    """Applets visibles pour un rôle et un mode, sans divulguer les autres."""
    role = "admin" if role == "admin" else "user"
    result = []
    for item in APPELS:
        if item["dev_only"] and not dev_mode:
            continue
        if item["role"] == "admin" and role != "admin":
            continue
        result.append(dict(item))
    return result


def requires_confirmation(applet_id: str) -> bool:
    item = _BY_ID.get(applet_id)
    return bool(item and item.get("confirmation"))
