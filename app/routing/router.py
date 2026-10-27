"""Routeur de demandes MILES : classification déterministe rapide/approfondi (Q1).

Activé uniquement via l'environnement ``MILES_ROUTER=1`` (désactivé par
défaut, aucun impact silencieux). Aucune clé, aucun secret dans le module.
Décision toujours rendue visible à l'utilisateur (règle DEC-005 : aucun
basculement silencieux).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("miles.routing")

#: Variable d'activation (désactivé par défaut).
ROUTER_ENV = "MILES_ROUTER"

#: Rôles de fournisseurs configurables (noms de cible).
RAPIDE_ROLE = "rapide"
APPROFONDI_ROLE = "approfondi"

#: Mots-clés de classification (déterministe, sans appel réseau).
DEEP_MARKERS: tuple[str, ...] = (
    "analyse", "analyser", "comparer", "compare", "recherche", "explorer",
    "architect", "refactor", "implémente", "implemente", "implantation",
    "démontre", "demontrer", "prouve", "étudie", "etudie", "diagnostique",
    "diagnostiquer", "audite", "audit", "revue", "specification", "spécification",
    "architecture", "étude", "etude", "conception", "design", "test complet",
    "planifie", "planifier", "stratégie", "strategie",
)
FAST_MARKERS: tuple[str, ...] = (
    "résume", "resume", "résumé", "resume court", "traduis", "liste",
    "définition", "definition", "orthographe", "corrige", "corriger",
    "format", "convertis", "convertir", "réponds rapidement", "en un mot",
)
#: Seuil de longueur (caractères) : au-delà, demande approfondie.
LONGUEUR_APPROFONDI: int = 400


def router_actif() -> bool:
    """Le routeur n'est actif que si MILES_ROUTER=1 (désactivé par défaut)."""
    return os.environ.get(ROUTER_ENV, "").strip() == "1"


def _nettoyer_option(texte: str) -> tuple[str, str | None]:
    """Extraire l'option forcée /fast ou /deep et retourner (texte, option)."""
    mots = texte.strip().split(" ", 1)
    if not mots:
        return "", None
    premiere = mots[0].lower()
    reste = mots[1] if len(mots) > 1 else ""
    if premiere in ("/fast", "/f"):
        return reste.strip(), "fast"
    if premiere in ("/deep", "/d"):
        return reste.strip(), "deep"
    return texte, None


def classifier(texte: str) -> dict:
    """Classer une demande en « rapide » ou « approfondi » (déterministe).

    Retourne un dict {choice, reason, reason_code, clean} :
    - choice : "rapide" ou "approfondi"
    - reason : libellé court, sans secret
    - reason_code : identifiant stable pour les journaux
    - clean : texte sans l'option /fast|/deep éventuelle
    """
    clean, option = _nettoyer_option(texte)
    if option == "fast":
        return {"choice": RAPIDE_ROLE, "reason": "option /fast forcée", "reason_code": "opt_fast", "clean": clean}
    if option == "deep":
        return {"choice": APPROFONDI_ROLE, "reason": "option /deep forcée", "reason_code": "opt_deep", "clean": clean}

    bas = clean.lower()
    if len(clean) >= LONGUEUR_APPROFONDI:
        return {"choice": APPROFONDI_ROLE, "reason": "demande longue", "reason_code": "longueur", "clean": clean}
    if any(m in bas for m in DEEP_MARKERS):
        return {"choice": APPROFONDI_ROLE, "reason": "mot-clé approfondi", "reason_code": "motcle_deep", "clean": clean}
    if any(m in bas for m in FAST_MARKERS):
        return {"choice": RAPIDE_ROLE, "reason": "mot-clé rapide", "reason_code": "motcle_fast", "clean": clean}
    return {"choice": RAPIDE_ROLE, "reason": "défaut", "reason_code": "defaut", "clean": clean}


def cible(role: str, settings) -> str | None:
    """Nom de la cible pour un rôle, ou None si indisponible.

    Rôles configurables via settings : ``router_rapide`` et
    ``router_approfondi`` (None = non configuré → indisponible).
    """
    cle = "router_rapide" if role == RAPIDE_ROLE else "router_approfondi"
    nom = str(settings.get(cle, "") or "").strip()
    return nom or None


def rendre_compte(decision: dict, nom_fournisseur_actif: str, settings) -> str:
    """Ligne de report à afficher TOUJOURS à l'utilisateur.

    Exemples :
      [routeur : rapide -> flash-local]
      [routeur : approfondi -> non disponible]  + explication honnête
    """
    role = decision["choice"]
    if role == RAPIDE_ROLE:
        nom = cible(RAPIDE_ROLE, settings) or nom_fournisseur_actif
        return f"[routeur : rapide -> {nom} ({decision['reason']})]"
    # Approfondi : si le rôle n'est pas configuré, le dire — ne JAMAIS
    # prétendre l'avoir utilisé.
    nom = cible(APPROFONDI_ROLE, settings)
    if nom is None:
        return ("[routeur : approfondi -> non disponible] "
                f"rôle approfondi non configuré ({decision['reason']}), "
                "aucune réponse ne sera présentée comme approfondie.")
    return f"[routeur : approfondi -> {nom} ({decision['reason']})]"


def journaliser(decision: dict) -> None:
    """Journaliser le choix de classification (aucun secret : choix + raison)."""
    logger.info(
        "routeur: classement '%s' (%s)",
        decision["choice"], decision["reason_code"],
    )
