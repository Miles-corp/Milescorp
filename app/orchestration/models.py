"""Modèle de données de l'orchestrateur de missions MILES.

Ce module définit les structures manipulées par l'orchestrateur :

- :class:`Mission` : objectif, identifiant, état, résultat et compte rendu ;
- :class:`Plan` : liste ordonnée d'étapes ;
- :class:`PlanStep` : une étape (objectif, outil, paramètres, statut) ;
- :class:`ExecutionLimits` : bornes d'exécution (appliquées par le code) ;
- :class:`PendingRequest` : demande de clarification ou d'autorisation.

Aucune décision de sécurité n'est prise ici : ce module ne décrit que des
données. Les autorisations restent vérifiées par le moteur d'outils.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.utilities.redaction import sanitize_text


class MissionState(str, Enum):
    """États possibles d'une mission."""

    CREATED = "created"
    NEEDS_CLARIFICATION = "needs_clarification"
    AWAITING_AUTHORIZATION = "awaiting_authorization"
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"

    @property
    def is_terminal(self) -> bool:
        """Indiquer si l'état est final (la mission ne progresse plus)."""
        return self in (
            MissionState.COMPLETED,
            MissionState.PARTIAL,
            MissionState.FAILED,
            MissionState.CANCELLED,
            MissionState.LIMIT_REACHED,
        )


class StepStatus(str, Enum):
    """Statuts possibles d'une étape du plan."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"

    @property
    def is_finished(self) -> bool:
        """Indiquer si l'étape ne sera plus rejouée telle quelle."""
        return self in (
            StepStatus.SUCCEEDED,
            StepStatus.FAILED,
            StepStatus.SKIPPED,
            StepStatus.UNCERTAIN,
            StepStatus.CANCELLED,
        )


@dataclass(frozen=True)
class SourceRef:
    """Référence au résultat d'une étape précédente.

    Décrit comment extraire une valeur du résultat d'une autre étape afin
    de l'injecter dans le paramètre d'une étape. Le mécanisme est
    explicite : aucune expression libre, aucun accès hors du résultat de
    l'étape citée.

    Attributs :
        step_id : identifiant de l'étape source.
        key : clé du résultat (par exemple ``entries``).
        index : position dans la liste (après filtrage).
        field : champ retenu dans l'entrée (par exemple ``path``).
        only_text : ne retenir que les entrées textuelles.
        exclude_sensitive : exclure les entrées sensibles.
        exclude_dirs : exclure les répertoires.
        only_dirs : ne retenir que les répertoires.
    """

    step_id: str
    key: str = "entries"
    index: int = 0
    field: str = "path"
    only_text: bool = True
    exclude_sensitive: bool = True
    exclude_dirs: bool = True
    only_dirs: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "key": self.key,
            "index": self.index,
            "field": self.field,
            "only_text": self.only_text,
            "exclude_sensitive": self.exclude_sensitive,
            "exclude_dirs": self.exclude_dirs,
            "only_dirs": self.only_dirs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRef":
        return cls(
            step_id=str(data.get("step_id", "")),
            key=str(data.get("key", "entries")),
            index=int(data.get("index", 0)),
            field=str(data.get("field", "path")),
            only_text=bool(data.get("only_text", True)),
            exclude_sensitive=bool(data.get("exclude_sensitive", True)),
            exclude_dirs=bool(data.get("exclude_dirs", True)),
            only_dirs=bool(data.get("only_dirs", False)),
        )


@dataclass
class PlanStep:
    """Une étape ordonnée d'un plan de mission.

    Attributs :
        step_id : identifiant de l'étape (unique dans le plan).
        objective : objectif de l'étape, en langage naturel.
        tool_id : outil à exécuter (doit être enregistré et autorisé).
        parameters : paramètres de l'appel d'outil.
        status : statut courant de l'étape.
        attempts : nombre de tentatives déjà effectuées.
        result : résultat observé de l'étape (None si non exécutée).
        error : message d'erreur si l'étape a échoué.
        note : information factuelle sur le statut (ex. « rien à lire »).
        source : référence au résultat d'une étape précédente.
        target_parameter : paramètre recevant la valeur extraite.
        depends_on : identifiants d'étapes dont cette étape dépend.
    """

    step_id: str
    objective: str
    tool_id: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    result: Any = None
    error: str = ""
    note: str = ""
    source: Optional[SourceRef] = None
    target_parameter: str = ""
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "objective": self.objective,
            "tool_id": self.tool_id,
            "parameters": self.parameters,
            "status": self.status.value,
            "attempts": self.attempts,
            "result": self.result,
            "error": self.error,
            "note": self.note,
            "source": self.source.to_dict() if self.source else None,
            "target_parameter": self.target_parameter,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        source = data.get("source")
        return cls(
            step_id=str(data.get("step_id", "")),
            objective=str(data.get("objective", "")),
            tool_id=str(data.get("tool_id", "")),
            parameters=dict(data.get("parameters") or {}),
            status=StepStatus(data.get("status", StepStatus.PENDING.value)),
            attempts=int(data.get("attempts", 0)),
            result=data.get("result"),
            error=str(data.get("error", "")),
            note=str(data.get("note", "")),
            source=SourceRef.from_dict(source) if isinstance(source, dict) else None,
            target_parameter=str(data.get("target_parameter", "")),
            depends_on=[str(d) for d in (data.get("depends_on") or [])],
        )


@dataclass
class Plan:
    """Plan ordonné d'une mission.

    Attributs :
        mission_id : identifiant de la mission.
        steps : étapes ordonnées.
        planner : nom du planificateur ayant produit le plan.
        note : information factuelle sur la production du plan.
    """

    mission_id: str
    steps: List[PlanStep] = field(default_factory=list)
    planner: str = "deterministe"
    note: str = ""

    def step(self, step_id: str) -> Optional[PlanStep]:
        """Retourner une étape par identifiant."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def next_pending(self) -> Optional[PlanStep]:
        """Retourner la première étape en attente, dans l'ordre du plan."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "planner": self.planner,
            "note": self.note,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(
            mission_id=str(data.get("mission_id", "")),
            steps=[
                PlanStep.from_dict(s) for s in (data.get("steps") or [])
            ],
            planner=str(data.get("planner", "deterministe")),
            note=str(data.get("note", "")),
        )


@dataclass(frozen=True)
class ExecutionLimits:
    """Bornes d'exécution appliquées par le code.

    Ces limites ne sont pas des recommandations : elles sont vérifiées par
    l'orchestrateur à chaque itération de la boucle.

    Attributs :
        max_steps : nombre maximal d'étapes exécutées par mission.
        max_attempts_per_step : nombre maximal de tentatives par étape.
        max_duration_seconds : durée maximale d'une mission.
        max_identical_results : nombre maximal de résultats identiques
            consécutifs (détection de boucle).
        max_report_bytes : taille maximale du compte rendu.
    """

    max_steps: int = 12
    max_attempts_per_step: int = 2
    max_duration_seconds: float = 120.0
    max_identical_results: int = 2
    max_report_bytes: int = 20000
    approval_ttl_seconds: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_steps": self.max_steps,
            "max_attempts_per_step": self.max_attempts_per_step,
            "max_duration_seconds": self.max_duration_seconds,
            "max_identical_results": self.max_identical_results,
            "max_report_bytes": self.max_report_bytes,
            "approval_ttl_seconds": self.approval_ttl_seconds,
        }


@dataclass
class PendingRequest:
    """Demande en attente adressée à l'utilisateur.

    Deux natures possibles :
    - ``clarification`` : une information manque pour poursuivre ;
    - ``authorization`` : l'exécution exige une autorisation humaine.

    Attributs :
        kind : nature de la demande.
        question : question posée à l'utilisateur.
        tool_ids : outils concernés par une demande d'autorisation.
        allowed_roots : racines de chemin concernées.
        details : informations complémentaires.
        created_at : instant de création.
        approval_token : jeton d'approbation, lié à cette demande précise
            (mission, périmètre, utilisateur). Il est imprévisible,
            expire et ne peut être utilisé qu'une fois.
        requested_by_user : utilisateur authentifié destinataire de la
            demande (vide si la mission n'est pas multi-utilisateur).
        expires_at : instant d'expiration de la demande d'approbation.
    """

    kind: str = "clarification"
    question: str = ""
    tool_ids: List[str] = field(default_factory=list)
    allowed_roots: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    approval_token: str = ""
    requested_by_user: str = ""
    expires_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "question": self.question,
            "tool_ids": list(self.tool_ids),
            "allowed_roots": list(self.allowed_roots),
            "details": dict(self.details),
            "created_at": self.created_at,
            "approval_token": self.approval_token,
            "requested_by_user": self.requested_by_user,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingRequest":
        return cls(
            kind=str(data.get("kind", "clarification")),
            question=str(data.get("question", "")),
            tool_ids=[str(t) for t in (data.get("tool_ids") or [])],
            allowed_roots=[str(r) for r in (data.get("allowed_roots") or [])],
            details=dict(data.get("details") or {}),
            created_at=float(data.get("created_at", 0.0)),
            approval_token=str(data.get("approval_token", "")),
            requested_by_user=str(data.get("requested_by_user", "")),
            expires_at=float(data.get("expires_at", 0.0)),
        )


@dataclass
class Mission:
    """Une mission d'observation/confiance confiée à l'orchestrateur.

    Attributs :
        mission_id : identifiant unique de la mission.
        objective : objectif en langage naturel.
        state : état courant.
        plan : plan produit pour la mission (None tant qu'il n'est pas prêt).
        facts : faits observés, chacun rattaché à une étape.
        errors : erreurs rencontrées.
        unfinished : étapes non terminées.
        pending : demande en attente, le cas échéant.
        planner : nom du planificateur utilisé.
        planner_note : justification factuelle du choix du planificateur.
        session_id : session ayant lancé la mission (identité technique du
            client : console ou session web authentifiée).
        owner_user_id : utilisateur authentifié propriétaire de la mission
            (vide pour une mission locale hors interface web).
        report : compte rendu final.
        target_path : chemin cible déterminé pour la mission (si connu).
        created_at / updated_at / started_at / finished_at : horodatages.
    """

    mission_id: str
    objective: str
    state: MissionState = MissionState.CREATED
    plan: Optional[Plan] = None
    facts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    unfinished: List[str] = field(default_factory=list)
    pending: Optional[PendingRequest] = None
    planner: str = ""
    planner_note: str = ""
    session_id: str = ""
    owner_user_id: str = ""
    report: str = ""
    target_path: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @staticmethod
    def new_id() -> str:
        """Générer un identifiant de mission."""
        return uuid.uuid4().hex[:12]

    def touch(self) -> None:
        """Mettre à jour l'horodatage de modification."""
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Sérialiser la mission (objet JSON compatible)."""
        return {
            "mission_id": self.mission_id,
            "objective": sanitize_text(self.objective),
            "state": self.state.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "facts": [sanitize_text(f) for f in self.facts],
            "errors": [sanitize_text(e) for e in self.errors],
            "unfinished": [sanitize_text(u) for u in self.unfinished],
            "pending": self.pending.to_dict() if self.pending else None,
            "planner": self.planner,
            "planner_note": sanitize_text(self.planner_note),
            "session_id": self.session_id,
            "owner_user_id": self.owner_user_id,
            "report": sanitize_text(self.report),
            "target_path": self.target_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Mission":
        """Reconstruire une mission depuis sa sérialisation."""
        plan = data.get("plan")
        pending = data.get("pending")
        return cls(
            mission_id=str(data.get("mission_id", "")),
            objective=str(data.get("objective", "")),
            state=MissionState(data.get("state", MissionState.CREATED.value)),
            plan=Plan.from_dict(plan) if isinstance(plan, dict) else None,
            facts=[str(f) for f in (data.get("facts") or [])],
            errors=[str(e) for e in (data.get("errors") or [])],
            unfinished=[str(u) for u in (data.get("unfinished") or [])],
            pending=PendingRequest.from_dict(pending) if isinstance(pending, dict) else None,
            planner=str(data.get("planner", "")),
            planner_note=str(data.get("planner_note", "")),
            session_id=str(data.get("session_id", "")),
            owner_user_id=str(data.get("owner_user_id", "")),
            report=str(data.get("report", "")),
            target_path=str(data.get("target_path", "")),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )
