"""Messages d'attente honnêtes fondés sur l'ÉTAT RÉEL d'une mission (Q2).

Contrats :
- **Aucune phrase sans événement correspondant** : on ne parle que de ce
  que l'état réel de la mission démontre (étape N/M en cours, erreur,
  demande en attente, achèvement réel).
- **Aucune étape annoncée terminée si elle ne l'est pas** : les décomptes
  viennent exclusivement de ``plan.steps`` et des compteurs de la mission.
- **Un état d'échec ne produit jamais un message de succès.**
- **Aucun secret** : seuls états, compteurs, kind de demande et titres
  d'étapes (expurgés via ``sanitize_text``) ; jamais de contenu de
  souvenir, de paramètre d'outil ni de clé.
- Module PUR : aucune écriture, aucun I/O réseau, aucune mutation de la
  mission. L'affichage est décidé par l'appelant (CLI).
"""

from __future__ import annotations

from app.orchestration.models import Mission, MissionState, StepStatus
from app.utilities.redaction import sanitize_text

#: Événements non terminaux dont on parle pendant l'attente.
#: type -> liste de formulations (variété des mots, sens identique).
PHRASES: dict[str, list[str]] = {
    "etape_en_cours": [
        "Étape {index}/{total} : {titre}",
        "Travail en cours — étape {index} sur {total} : {titre}.",
        "Je traite l'étape {index}/{total} — {titre}.",
    ],
    "plan": [
        "Plan de {total} étapes — {terminees} déjà accomplies.",
        "Exécution en cours : {terminees}/{total} étapes terminées.",
    ],
    "tentative": [
        "Étape en échec : nouvelle tentative en cours ({erreurs} erreur(s) consignée(s)).",
        "Réessai après erreur ({erreurs} erreur(s) au journal).",
    ],
    "demande_clarification": [
        "J'ai besoin d'une précision avant de continuer.",
        "Une clarification est nécessaire pour poursuivre.",
    ],
    "demande_authorization": [
        "Autorisation requise avant de poursuivre l'étape suivante.",
        "Une confirmation humaine bloque l'exécution pour l'instant.",
    ],
    "terminee": [
        "Mission terminée : {total}/{total} étapes accomplies.",
    ],
    "terminee_partielle": [
        "Mission terminée partiellement : {terminees}/{total} étapes accomplies, {inachevees} inachevée(s).",
    ],
    "echec": [
        "Mission en échec : {erreurs} erreur(s) consignée(s), {terminees}/{total} étapes seulement accomplies.",
    ],
    "arretee": [
        "Mission arrêtée ({motif}) : {terminees}/{total} étapes accomplies.",
    ],
}


def evenement(mission: Mission) -> dict | None:
    """Extraire l'événement réel de la mission (lecture seule, pur).

    Retourne un dict ``{"type": ..., ...}`` avec uniquement des informations
    démontrables, ou ``None`` si la mission n'expose aucun événement d'attente
    (état initial, aucune étape).
    """
    state = mission.state
    steps = list(mission.plan.steps) if mission.plan is not None else []
    total = len(steps)
    terminees = sum(1 for s in steps if s.status == StepStatus.SUCCEEDED)
    echecs = sum(1 for s in steps if s.status == StepStatus.FAILED)
    erreurs = len(mission.errors)

    # Demandes en attente : priorité (l'utilisateur est sollicité).
    if mission.pending is not None:
        kind = str(getattr(mission.pending, "kind", "clarification"))
        if kind == "authorization":
            return {"type": "demande_authorization", "kind": kind}
        return {"type": "demande_clarification", "kind": kind}

    # États terminaux : on rapporte l'état RÉEL, jamais de succès improvisé.
    if state == MissionState.FAILED:
        return {"type": "echec", "erreurs": erreurs,
                "terminees": terminees, "total": total}
    if state == MissionState.PARTIAL:
        return {"type": "terminee_partielle", "terminees": terminees,
                "total": total, "inachevees": len(mission.unfinished)}
    if state == MissionState.COMPLETED:
        return {"type": "terminee", "total": total, "terminees": terminees}
    if state in (MissionState.CANCELLED, MissionState.LIMIT_REACHED):
        motif = "annulation" if state == MissionState.CANCELLED else "limite atteinte"
        return {"type": "arretee", "motif": motif,
                "terminees": terminees, "total": total}

    # États non terminaux.
    if state == MissionState.CREATED:
        return None  # rien à raconter tant que rien ne tourne
    en_cours = [i for i, s in enumerate(steps) if s.status == StepStatus.RUNNING]
    if en_cours:
        idx = en_cours[0] + 1
        titre = sanitize_text(str(steps[en_cours[0]].objective))[:80]
        return {"type": "etape_en_cours", "index": idx, "total": total, "titre": titre}
    if echecs > 0:
        # Une étape a échoué et on n'est pas en état terminal : on réessaie.
        return {"type": "tentative", "erreurs": erreurs, "terminees": terminees,
                "total": total}
    if state in (MissionState.RUNNING, MissionState.PLANNED,
                 MissionState.NEEDS_CLARIFICATION,
                 MissionState.AWAITING_AUTHORIZATION):
        return {"type": "plan", "terminees": terminees, "total": total}
    return None


def message_attente(mission: Mission, variante: int = 0) -> str | None:
    """Phrase d'attente honnête pour l'état actuel, ou None.

    Args:
        mission : objet mission (non muté).
        variante : index tournant appelé (permet la variété des mots sans
            changer le sens : deux variantes consécutives sont distinctes).

    Returns:
        La phrase, ou None si aucun événement d'attente ne s'applique.
    """
    ev = evenement(mission)
    if ev is None:
        return None
    formulations = PHRASES.get(ev["type"])
    if not formulations:
        return None
    modele = formulations[variante % len(formulations)]
    champs = {k: v for k, v in ev.items() if k != "type"}
    try:
        return modele.format(**champs)
    except (KeyError, IndexError) as exc:  # garde : jamais de crash d'affichage
        return f"[routeur-mission] message indisponible ({type(exc).__name__})"
