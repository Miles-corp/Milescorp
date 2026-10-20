"""Exécution contrôlée des étapes de mission.

L'exécuteur est le **seul** composant de l'orchestrateur autorisé à
demander l'exécution d'un outil. Il passe toujours par
:class:`app.tools.service.ToolService` : ni la politique de sécurité, ni
les permissions, ni les délais, ni l'audit ne sont réimplémentés ici.

Deux garanties fondamentales :

- l'exécuteur **ne fabrique jamais** une confirmation : si le moteur
  réclame une confirmation, l'étape est signalée comme bloquée et la
  mission attend une autorisation humaine ;
- le résultat d'un outil est une **donnée** : il n'est jamais interprété
  comme une instruction, et son contenu ne peut modifier aucune règle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.orchestration.models import (
    Mission,
    PlanStep,
    SourceRef,
    StepStatus,
)
from app.tools.service import ToolService

logger = logging.getLogger("miles.orchestration")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


class FailureKind(str):
    """Catégories d'échec (chaînes constantes)."""

    PERMISSION = "permission"
    POLICY = "policy"
    UNKNOWN_TOOL = "unknown_tool"
    AUTHORIZATION = "authorization"
    TRANSIENT = "transient"
    FATAL = "fatal"


@dataclass
class StepOutcome:
    """Résultat de l'exécution d'une étape.

    Attributs :
        status : statut obtenu pour l'étape.
        result : données retournées par l'outil (None en cas d'échec).
        error : message d'erreur factuel.
        kind : catégorie d'échec (voir :class:`FailureKind`).
        needs_authorization : True si une confirmation humaine est requise.
        confirmation_token : jeton de confirmation fourni par le moteur.
        duration_ms : durée d'exécution.
        skipped_reason : raison d'un saut (aucune donnée à traiter).
    """

    status: StepStatus = StepStatus.FAILED
    result: Any = None
    error: str = ""
    kind: str = FailureKind.FATAL
    needs_authorization: bool = False
    confirmation_token: str = ""
    duration_ms: float = 0.0
    skipped_reason: str = ""


def classify_failure(error_message: str) -> str:
    """Classer un message d'erreur du moteur.

    Seuls les échecs techniques (exécution, délai) sont considérés comme
    transitoires et donc rejouables. Un refus de permission, un refus de
    politique ou un outil inconnu ne sont **jamais** rejoués.
    """
    lowered = (error_message or "").lower()
    if "confirmation humaine requise" in lowered:
        return FailureKind.AUTHORIZATION
    if "permissions manquantes" in lowered:
        return FailureKind.PERMISSION
    if "refusée par la politique" in lowered:
        return FailureKind.POLICY
    if "outil inconnu" in lowered:
        return FailureKind.UNKNOWN_TOOL
    if "erreur d'exécution" in lowered or "délai d'attente dépassé" in lowered:
        return FailureKind.TRANSIENT
    if "interne" in lowered:
        return FailureKind.TRANSIENT
    return FailureKind.FATAL


def resolve_source_value(
    source: SourceRef,
    results: Dict[str, Any],
) -> tuple[bool, Any, str]:
    """Extraire une valeur du résultat d'une étape précédente.

    Args:
        source : description de la valeur à extraire.
        results : résultats des étapes déjà exécutées, indexés par
            identifiant d'étape.

    Returns:
        Un triplet ``(trouvé, valeur, raison)``. ``trouvé`` est False si la
        source n'a pas produit de donnée exploitable : l'étape doit alors
        être sautée, et non exécutée avec une valeur inventée.
    """
    data = results.get(source.step_id)
    if data is None:
        return False, None, f"résultat de l'étape {source.step_id} indisponible"
    if not isinstance(data, dict):
        return False, None, f"résultat de l'étape {source.step_id} non exploitable"

    raw = data.get(source.key)
    if raw is None:
        return False, None, f"clé {source.key!r} absente du résultat de {source.step_id}"
    if not isinstance(raw, list):
        return False, None, f"clé {source.key!r} du résultat de {source.step_id} non itérable"

    candidates = raw
    if isinstance(source.only_text, bool) or source.only_dirs:
        filtered = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            if source.only_dirs and not item.get("is_dir", False):
                continue
            if source.only_text and not item.get("is_text", False):
                continue
            if source.exclude_sensitive and item.get("sensitive", False):
                continue
            if source.exclude_dirs and item.get("is_dir", False):
                continue
            filtered.append(item)
        candidates = filtered

    if source.index >= len(candidates):
        return False, None, (
            f"aucun élément n°{source.index + 1} exploitable dans "
            f"{source.step_id} ({len(candidates)} élément(s) retenu(s))"
        )

    item = candidates[source.index]
    if not isinstance(item, dict):
        return False, None, "élément source inexploitable"
    if source.field not in item:
        return False, None, f"champ {source.field!r} absent de l'élément source"
    return True, item[source.field], ""


class Executor:
    """Exécute les étapes d'un plan via le service d'outils partagé."""

    def __init__(
        self,
        tool_service: ToolService,
        *,
        session_id: str = "",
        allowed_tool_ids: Optional[List[str]] = None,
        clock=time.time,
    ) -> None:
        self._tool_service = tool_service
        self._session_id = session_id
        self._allowed_tool_ids = (
            list(allowed_tool_ids) if allowed_tool_ids is not None else None
        )
        self._clock = clock

    def execute(
        self,
        step: PlanStep,
        mission: Mission,
        results: Dict[str, Any],
    ) -> StepOutcome:
        """Exécuter une étape.

        La résolution des paramètres issus d'une étape précédente est
        effectuée ici : si la donnée source est absente, l'étape est
        **sautée** (jamais exécutée avec une valeur inventée).
        """
        started = self._clock()

        # Défense en profondeur : même un plan construit hors du
        # planificateur ne peut pas utiliser un outil hors périmètre.
        if (
            self._allowed_tool_ids is not None
            and step.tool_id not in self._allowed_tool_ids
        ):
            return StepOutcome(
                status=StepStatus.FAILED,
                error=f"Outil non autorisé pour cette mission : {step.tool_id}",
                kind=FailureKind.POLICY,
                duration_ms=(self._clock() - started) * 1000.0,
            )

        parameters = dict(step.parameters)

        if step.source is not None:
            found, value, reason = resolve_source_value(step.source, results)
            if not found:
                return StepOutcome(
                    status=StepStatus.SKIPPED,
                    skipped_reason=reason,
                    duration_ms=(self._clock() - started) * 1000.0,
                )
            parameters[step.target_parameter] = value

        try:
            result = self._tool_service.request_tool(
                tool_id=step.tool_id,
                parameters=parameters,
                context_id=mission.mission_id,
                # L'acteur est la session du client propriétaire de la
                # mission (et non une session partagée par processus) :
                # un jeton de confirmation n'est ainsi utilisable que par
                # le client qui a reçu l'autorisation.
                actor_id=mission.session_id or self._session_id,
            )
        except Exception as exc:  # noqa: BLE001 — une exception ne doit pas tuer la mission
            logger.warning(
                "Erreur interne lors de l'execution de l'etape %s : %s",
                step.step_id,
                type(exc).__name__,
            )
            return StepOutcome(
                status=StepStatus.FAILED,
                error="Erreur interne du service d'outils.",
                kind=FailureKind.TRANSIENT,
                duration_ms=(self._clock() - started) * 1000.0,
            )

        duration_ms = (self._clock() - started) * 1000.0

        if result.confirmation_required:
            return StepOutcome(
                status=StepStatus.BLOCKED,
                error=result.error_message,
                kind=FailureKind.AUTHORIZATION,
                needs_authorization=True,
                confirmation_token=result.confirmation_token,
                duration_ms=duration_ms,
            )

        if result.success:
            return StepOutcome(
                status=StepStatus.SUCCEEDED,
                result=result.data,
                duration_ms=duration_ms,
            )

        return StepOutcome(
            status=StepStatus.FAILED,
            error=result.error_message or "Échec de l'outil.",
            kind=classify_failure(result.error_message),
            duration_ms=duration_ms,
        )
