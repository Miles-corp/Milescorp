"""Orchestrateur de missions MILES.

Le :class:`MissionRunner` coordonne le cycle complet d'une mission :

``planifier → exécuter → observer → ajuster → terminer``

Garanties fundamentals :

- **bornes appliquées par le code** : nombre maximal d'étapes, nombre
  maximal de tentatives par étape, durée maximale, détection des
  résultats identiques (boucles) ;
- **aucune action non autorisée** : toute exécution passe par
  :class:`app.tools.service.ToolService`, et une action sensible exige une
  autorisation humaine liée à la session et à la mission ;
- **aucune invention** : une étape n'est déclarée réussie que si l'outil a
  réellement retourné un résultat ; un résultat absent produit un saut
  explicite, jamais une valeur/devinette ;
- **aucune simulation d'IA** : si le fournisseur est absent ou invalide,
  le repli déterministe est utilisé et la mission conserve la trace du
  repli.
"""

from __future__ import annotations

import hmac
import logging
import secrets
import threading
import time
from typing import Any, Dict, List, Optional

from app.orchestration.executor import Executor, FailureKind
from app.orchestration.models import (
    ExecutionLimits,
    Mission,
    MissionState,
    PendingRequest,
    Plan,
    PlanStep,
    StepStatus,
)
from app.orchestration.observer import Observer
from app.orchestration.planner import (
    ClarificationRequired,
    DeterministicPlanner,
    PlanContext,
    PlanRejected,
    Planner,
    ProviderPlanner,
    extract_target_path,
)
from app.orchestration.report import ReportBuilder
from app.orchestration.store import MissionStore
from app.tools.grants import GrantRegistry
from app.tools.service import ToolService

logger = logging.getLogger("miles.orchestration")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


class MissionAuthorizationError(Exception):
    """Une autorisation de mission a été refusée.

    Levée lorsqu'un demandeur n'est pas autorisé à agir sur la mission,
    lorsqu'il ne présente pas le jeton d'approbation attendu, ou lorsque la
    demande est expirée ou déjà utilisée.
    """


class MissionRunner:
    """Coordination et exécution des missions.

    Attributs :
        tool_service : service d'outils partagé (unique point d'exécution).
        planner : planificateur utilisé.
        store : persistance des missions (facultative).
        limits : bornes d'exécution.
        observer : analyse des résultats.
        executor : exécution des étapes.
        grant_registry : registre d'autorisations liées à la session.
        session_id : identité de session courante.
    """

    def __init__(
        self,
        tool_service: ToolService,
        *,
        planner: Optional[Planner] = None,
        provider: Any = None,
        store: Optional[MissionStore] = None,
        limits: Optional[ExecutionLimits] = None,
        observer: Optional[Observer] = None,
        executor: Optional[Executor] = None,
        grant_registry: Optional[GrantRegistry] = None,
        session_id: str = "",
        allowed_tool_ids: Optional[List[str]] = None,
        clock=time.time,
    ) -> None:
        self.tool_service = tool_service
        self.store = store
        self.limits = limits or ExecutionLimits()
        self.observer = observer or Observer()
        self.grant_registry = grant_registry
        self.session_id = session_id
        self._clock = clock
        self._lock = threading.RLock()
        self._missions: Dict[str, Mission] = {}
        self._cancelled: set[str] = set()

        if allowed_tool_ids is None:
            from app.tools.builtin import READ_ONLY_TOOLS

            allowed_tool_ids = list(READ_ONLY_TOOLS)
        self.allowed_tool_ids = list(allowed_tool_ids)

        if planner is not None:
            self.planner = planner
        elif provider is not None:
            self.planner = ProviderPlanner(
                provider, fallback=DeterministicPlanner()
            )
        else:
            self.planner = DeterministicPlanner()

        self.executor = executor or Executor(
            tool_service,
            session_id=session_id,
            allowed_tool_ids=self.allowed_tool_ids,
            clock=clock,
        )
        self._report_builder = ReportBuilder(self.limits)

        # Le moteur d'outils doit connaître le registre d'autorisations :
        # c'est lui qui décide in fine d'accorder ou non une action sensible.
        if grant_registry is not None:
            try:
                tool_service.engine.set_grant_checker(grant_registry)
            except AttributeError:  # pragma: no cover - moteur sans hook
                logger.warning(
                    "Le moteur d'outils n'accepte pas de verificateur "
                    "d'autorisations."
                )

    # --- Cycle de vie des missions ---

    def create(
        self,
        objective: str,
        *,
        owner_user_id: str = "",
        owner_session_id: str = "",
    ) -> Mission:
        """Créer une mission à partir d'un objectif en langage naturel.

        Args:
            objective : objectif en langage naturel.
            owner_user_id : utilisateur authentifié propriétaire de la
                mission (vide pour une mission locale).
            owner_session_id : session du client propriétaire : c'est elle
                qui est liée aux jetons de confirmation des outils et aux
                autorisations.
        """
        cleaned = (objective or "").strip()
        if not cleaned:
            raise ValueError("L'objectif d'une mission ne peut pas être vide.")
        mission = Mission(
            mission_id=Mission.new_id(),
            objective=cleaned,
            session_id=owner_session_id or self.session_id,
            owner_user_id=owner_user_id,
            target_path=extract_target_path(cleaned) or "",
        )
        with self._lock:
            self._missions[mission.mission_id] = mission
        self._save(mission)
        self._record_event(mission, "created", "Mission creee.")
        return mission

    def get(
        self, mission_id: str, *, owner_user_id: Optional[str] = None
    ) -> Optional[Mission]:
        """Retourner une mission connue (en mémoire ou en persistance).

        Args:
            mission_id : identifiant de la mission.
            owner_user_id : si fourni, la mission n'est retournée que si
                elle appartient à cet utilisateur (isolation entre
                utilisateurs de l'interface web).
        """
        with self._lock:
            mission = self._missions.get(mission_id)
        if mission is None and self.store is not None:
            mission = self.store.load(mission_id)
            if mission is not None:
                with self._lock:
                    self._missions[mission_id] = mission
        if mission is None:
            return None
        if owner_user_id is not None and mission.owner_user_id != owner_user_id:
            return None
        return mission

    def list_missions(
        self, limit: int = 20, *, owner_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lister les missions connues.

        Si ``owner_user_id`` est fourni, seules les missions de cet
        utilisateur sont retournées.
        """
        with self._lock:
            missions = list(self._missions.values())
        missions.sort(key=lambda m: m.created_at, reverse=True)
        return [
            {
                "mission_id": m.mission_id,
                "objective": m.objective,
                "state": m.state.value,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
            }
            for m in missions
            if owner_user_id is None or m.owner_user_id == owner_user_id
        ][:limit]

    def find_running(self, objective: str) -> Optional[Mission]:
        """Retourner une mission en cours portant le même objectif.

        Utilisé pour éviter qu'un double clic ou une requête répétée ne
        lance deux fois la même mission.
        """
        cleaned = (objective or "").strip()
        with self._lock:
            for mission in self._missions.values():
                if (
                    mission.objective == cleaned
                    and mission.state
                    in (
                        MissionState.CREATED,
                        MissionState.PLANNED,
                        MissionState.RUNNING,
                        MissionState.AWAITING_AUTHORIZATION,
                        MissionState.NEEDS_CLARIFICATION,
                    )
                ):
                    return mission
        return None

    def cancel(self, mission_id: str) -> bool:
        """Demander l'arrêt d'une mission.

        Retourne True si la mission était connue et a été arrêtée.
        """
        with self._lock:
            self._cancelled.add(mission_id)
            mission = self._missions.get(mission_id)
        if mission is None:
            mission = self.get(mission_id)
        if mission is None:
            return False
        if mission.state.is_terminal:
            return False
        mission.state = MissionState.CANCELLED
        mission.finished_at = self._clock()
        mission.touch()
        self._save(mission)
        self._record_event(mission, "cancelled", "Mission annulee par l'utilisateur.")
        return True

    def answer(
        self,
        mission_id: str,
        answer: str,
        *,
        requester_user_id: Optional[str] = None,
        requester_session_id: Optional[str] = None,
    ) -> Optional[Mission]:
        """Traiter une réponse de l'utilisateur à une demande en attente.

        - demande de clarification : la réponse complète l'objectif et la
          mission est replanifiée ;
        - demande d'autorisation : une réponse positive autorise le
          périmètre proposé, une autre réponse refuse et arrête la mission.

        Raises:
            MissionAuthorizationError: si le demandeur n'est pas le
                propriétaire de la mission.
        """
        mission = self.get(mission_id)
        if mission is None:
            return None
        if (
            mission.owner_user_id
            and requester_user_id is not None
            and str(requester_user_id) != mission.owner_user_id
        ):
            raise MissionAuthorizationError(
                "Cette mission appartient a un autre utilisateur."
            )
        if mission.pending is None:
            return mission
        text = (answer or "").strip()
        if mission.pending.kind == "authorization":
            approved = text.lower() in ("o", "oui", "y", "yes", "ok", "autorise")
            return self.authorize(
                mission_id,
                approved=approved,
                requester_user_id=requester_user_id,
                requester_session_id=requester_session_id,
                approval_token=mission.pending.approval_token,
            )

        # Clarification : on cherche un chemin dans la réponse.
        candidate = extract_target_path(text)
        if candidate:
            mission.target_path = candidate
        else:
            mission.pending = PendingRequest(
                kind="clarification",
                question=(
                    "Réponse non comprise : indiquez un chemin de dossier "
                    "relatif à la racine du projet (ex. « app/ »)."
                ),
                created_at=self._clock(),
            )
            self._save(mission)
            return mission

        mission.pending = None
        mission.state = MissionState.CREATED
        mission.plan = None
        self._save(mission)
        return self.run(mission_id)

    def authorize(
        self,
        mission_id: str,
        *,
        approved: bool,
        tool_ids: Optional[List[str]] = None,
        allowed_roots: Optional[List[str]] = None,
        requester_user_id: Optional[str] = None,
        requester_session_id: Optional[str] = None,
        approval_token: Optional[str] = None,
    ) -> Optional[Mission]:
        """Accorder (ou refuser) l'autorisation demandée par une mission.

        L'autorisation accordée est un **grant** lié à la session du client
        demandeur et à la mission : elle expire, son nombre d'usages est
        borné et elle ne peut pas être rejouée ailleurs.

        Le demandeur doit :
        - être le propriétaire de la mission (comparaison de l'identifiant
          utilisateur) ;
        - présenter le jeton d'approbation de la demande en attente, lié à
          cette mission et à ce périmètre précis.

        Raises:
            MissionAuthorizationError: si le demandeur n'est pas autorisé
                ou si le jeton est absent, invalide, expiré ou déjà utilisé.
        """
        mission = self.get(mission_id)
        if mission is None:
            raise MissionAuthorizationError("Mission inconnue.")
        if mission.pending is None or mission.pending.kind != "authorization":
            raise MissionAuthorizationError(
                "Aucune autorisation en attente pour cette mission."
            )
        if (
            mission.owner_user_id
            and str(requester_user_id or "") != mission.owner_user_id
        ):
            raise MissionAuthorizationError(
                "Cette mission appartient a un autre utilisateur."
            )
        pending = mission.pending
        if pending.expires_at and self._clock() > pending.expires_at:
            raise MissionAuthorizationError(
                "La demande d'autorisation est expiree."
            )
        if not pending.approval_token or not approval_token:
            raise MissionAuthorizationError(
                "Jeton d'autorisation manquant."
            )
        if not hmac.compare_digest(pending.approval_token, approval_token):
            raise MissionAuthorizationError(
                "Jeton d'autorisation invalide."
            )

        if not approved:
            mission.pending = None
            mission.state = MissionState.FAILED
            mission.errors.append(
                "Autorisation refusée par l'utilisateur : mission arrêtée."
            )
            mission.finished_at = self._clock()
            mission.report = self._report_builder.build(mission, self._analyze)
            self._save(mission)
            return mission

        tools = tool_ids if tool_ids is not None else list(pending.tool_ids)
        roots = (
            allowed_roots
            if allowed_roots is not None
            else list(pending.allowed_roots)
        )
        if self.grant_registry is not None:
            self.grant_registry.issue(
                session_id=requester_session_id or mission.session_id,
                mission_id=mission.mission_id,
                tool_ids=tools,
                allowed_roots=roots,
                scope="lecture_seule",
            )
        self._record_event(
            mission,
            "authorized",
            "Autorisation accordee pour : " + ", ".join(tools),
        )
        mission.pending = None
        mission.state = MissionState.CREATED
        self._save(mission)
        return self.run(mission_id)

    def resume(self, mission_id: str) -> Optional[Mission]:
        """Reprendre une mission interrompue.

        Les étapes dont le résultat est incertain ne sont **pas** rejouées
        automatiquement : elles sont signalées comme nécessitant une
        revalidation explicite. Les autorisations sont revalidées (un
        grant expiré ou émis pour une autre session est refusé).
        """
        mission = self.get(mission_id)
        if mission is None:
            return None
        if mission.state == MissionState.COMPLETED:
            return mission
        if mission.plan is None:
            return self.run(mission_id)

        for step in mission.plan.steps:
            if step.status in (StepStatus.FAILED, StepStatus.UNCERTAIN):
                step.status = StepStatus.UNCERTAIN
                step.note = (
                    "résultat incertain : étape non rejouée automatiquement"
                )
        # Une mission annulée peut être relancée : l'annulation précédente
        # ne doit pas empêcher la reprise explicite.
        with self._lock:
            self._cancelled.discard(mission_id)
        mission.pending = None
        mission.state = MissionState.CREATED
        self._save(mission)
        return self.run(mission_id)

    # --- Boucle d'exécution ---

    def run(self, mission_id: str) -> Optional[Mission]:
        """Exécuter (ou poursuivre) une mission.

        La boucle est bornée par : le nombre maximal d'étapes, le nombre
        maximal de tentatives par étape, la durée maximale et la détection
        de résultats identiques.
        """
        mission = self.get(mission_id)
        if mission is None:
            return None
        if mission.state in (
            MissionState.NEEDS_CLARIFICATION,
            MissionState.AWAITING_AUTHORIZATION,
        ):
            return mission
        if mission.state.is_terminal:
            return mission

        if mission.plan is None:
            plan = self._build_plan(mission)
            if plan is None:
                return mission

        return self._execute_loop(mission)

    def _build_plan(self, mission: Mission) -> Optional[Plan]:
        """Construire le plan de la mission, en gérant clarifications et refus."""
        context = PlanContext(
            registry=self.tool_service.registry,
            allowed_tool_ids=list(self.allowed_tool_ids),
            limits=self.limits,
            target_path=mission.target_path,
            mission_id=mission.mission_id,
        )
        try:
            plan = self.planner.plan(mission.objective, context)
        except ClarificationRequired as exc:
            mission.state = MissionState.NEEDS_CLARIFICATION
            mission.pending = PendingRequest(
                kind="clarification",
                question=exc.question,
                created_at=self._clock(),
            )
            mission.touch()
            self._save(mission)
            self._record_event(
                mission, "clarification", "Information manquante demandee."
            )
            return None
        except PlanRejected as exc:
            mission.state = MissionState.FAILED
            mission.errors.append(str(exc.reason if hasattr(exc, "reason") else exc))
            mission.finished_at = self._clock()
            mission.report = self._report_builder.build(mission, self._analyze)
            mission.touch()
            self._save(mission)
            return None

        plan.mission_id = mission.mission_id
        mission.plan = plan
        mission.planner = plan.planner
        mission.planner_note = plan.note
        mission.state = MissionState.PLANNED
        mission.touch()
        self._save(mission)
        return plan

    def _execute_loop(self, mission: Mission) -> Mission:
        """Boucle bornée d'exécution des étapes."""
        limits = self.limits
        deadline = self._clock() + limits.max_duration_seconds
        results: Dict[str, Any] = {}
        executed = 0
        identical = 0
        last_signature = ""
        mission.state = MissionState.RUNNING
        if mission.started_at is None:
            mission.started_at = self._clock()

        while True:
            if mission.mission_id in self._cancelled:
                mission.state = MissionState.CANCELLED
                break

            if self._clock() > deadline:
                mission.state = MissionState.LIMIT_REACHED
                mission.errors.append(
                    f"Durée maximale de mission atteinte "
                    f"({limits.max_duration_seconds} s)."
                )
                break

            step = mission.plan.next_pending() if mission.plan else None
            if step is None:
                break

            if executed >= limits.max_steps:
                mission.state = MissionState.LIMIT_REACHED
                mission.errors.append(
                    f"Nombre maximal d'étapes atteint ({limits.max_steps})."
                )
                break

            if not self._ensure_authorization(mission, step):
                break

            executed += 1
            step.status = StepStatus.RUNNING
            step.attempts += 1
            outcome = self.executor.execute(step, mission, results)
            observation = self.observer.observe(step, outcome)
            mission.facts.extend(observation.facts)

            if outcome.status == StepStatus.SUCCEEDED:
                step.status = StepStatus.SUCCEEDED
                step.result = outcome.result
                step.error = ""
                results[step.step_id] = outcome.result
                identical, last_signature = self._track_signature(
                    observation.signature, last_signature, identical
                )
            elif outcome.status == StepStatus.SKIPPED:
                step.status = StepStatus.SKIPPED
                step.note = outcome.skipped_reason
                identical = 0
            elif outcome.status == StepStatus.BLOCKED:
                step.status = StepStatus.BLOCKED
                step.error = outcome.error
                mission.pending = self._authorization_request(mission, step)
                mission.state = MissionState.AWAITING_AUTHORIZATION
                self._record_event(
                    mission, "authorization_required", "Autorisation humaine requise."
                )
                identical = 0
                break
            else:
                step.status = StepStatus.FAILED
                step.error = outcome.error
                mission.errors.append(
                    f"Étape {step.step_id} ({step.tool_id}) : {outcome.error}"
                )
                identical = 0
                if (
                    outcome.kind == FailureKind.TRANSIENT
                    and step.attempts < limits.max_attempts_per_step
                ):
                    # Reprise limitée : l'étape repasse en attente et sera
                    # rejouée au prochain tour de boucle.
                    step.status = StepStatus.PENDING
                    step.note = (
                        f"nouvelle tentative ({step.attempts + 1}/"
                        f"{limits.max_attempts_per_step})"
                    )
                    continue
                self._skip_dependents(mission, step.step_id)

            if identical >= limits.max_identical_results:
                mission.state = MissionState.LIMIT_REACHED
                mission.errors.append(
                    "Résultats identiques répétés : boucle détectée, "
                    "mission arrêtée."
                )
                break

            mission.touch()
            self._save(mission)

        if mission.state == MissionState.RUNNING:
            self._collect_unfinished(mission)
            mission.state = (
                MissionState.COMPLETED
                if not mission.errors and not mission.unfinished
                else MissionState.PARTIAL
            )

        if mission.state == MissionState.CANCELLED:
            self._collect_unfinished(mission)

        mission.finished_at = self._clock()
        mission.report = self._report_builder.build(mission, self._analyze)
        mission.touch()
        self._save(mission)
        self._record_event(mission, "finished", f"Etat final : {mission.state.value}.")
        return mission

    @staticmethod
    def _track_signature(
        signature: str, last_signature: str, identical: int
    ) -> tuple[int, str]:
        """Mettre à jour le compteur de résultats identiques consécutifs."""
        if not signature:
            return 0, last_signature
        if signature == last_signature:
            return identical + 1, last_signature
        return 0, signature

    def _skip_dependents(self, mission: Mission, step_id: str) -> None:
        """Marquer comme sautées les étapes qui dépendent d'une étape échouée."""
        if mission.plan is None:
            return
        for step in mission.plan.steps:
            if step.status == StepStatus.PENDING and (
                step.source is not None and step.source.step_id == step_id
                or step_id in step.depends_on
            ):
                step.status = StepStatus.SKIPPED
                step.note = f"étape amont {step_id} non aboutie"

    def _collect_unfinished(self, mission: Mission) -> None:
        """Recenser les étapes non terminées."""
        mission.unfinished = []
        if mission.plan is None:
            return
        for step in mission.plan.steps:
            if step.status in (
                StepStatus.SUCCEEDED,
                StepStatus.CANCELLED,
            ):
                continue
            label = {
                StepStatus.PENDING: "non exécutée",
                StepStatus.RUNNING: "interrompue",
                StepStatus.FAILED: "en échec",
                StepStatus.SKIPPED: "sautée",
                StepStatus.BLOCKED: "bloquée (autorisation requise)",
                StepStatus.UNCERTAIN: "résultat incertain",
            }.get(step.status, step.status.value)
            detail = step.error or step.note
            suffix = f" — {detail}" if detail else ""
            mission.unfinished.append(
                f"{step.step_id} ({step.tool_id}) : {label}{suffix}"
            )

    def _ensure_authorization(self, mission: Mission, step: PlanStep) -> bool:
        """Vérifier qu'une action sensible est couverte par une autorisation.

        Retourne False si une autorisation doit être demandée à l'utilisateur
        (la mission est alors mise en attente).
        """
        if self.grant_registry is None:
            # Aucune infrastructure d'autorisation : les actions sensibles
            # ne peuvent pas être exécutées silencieusement.
            tool = self.tool_service.registry.get_tool(step.tool_id)
            if tool is not None and tool.risk_level in ("MEDIUM", "HIGH"):
                mission.pending = self._authorization_request(mission, step)
                mission.state = MissionState.AWAITING_AUTHORIZATION
                return False
            return True

        tool = self.tool_service.registry.get_tool(step.tool_id)
        if tool is None:
            return True
        if tool.risk_level not in ("MEDIUM", "HIGH"):
            return True

        parameters = dict(step.parameters)
        if "path" not in parameters and mission.target_path:
            parameters["path"] = mission.target_path
        grant_id = self.grant_registry.authorize(
            step.tool_id, parameters, mission.mission_id, self.session_id
        )
        if grant_id:
            return True

        mission.pending = self._authorization_request(mission, step)
        mission.state = MissionState.AWAITING_AUTHORIZATION
        return False

    def _authorization_request(
        self, mission: Mission, step: PlanStep
    ) -> PendingRequest:
        """Construire la demande d'autorisation correspondant à une étape."""
        tool_ids = []
        roots = []
        if mission.plan is not None:
            for planned in mission.plan.steps:
                tool = self.tool_service.registry.get_tool(planned.tool_id)
                if tool is None or tool.risk_level not in ("MEDIUM", "HIGH"):
                    continue
                if planned.tool_id not in tool_ids:
                    tool_ids.append(planned.tool_id)
                path = planned.parameters.get("path")
                if isinstance(path, str) and path and path not in roots:
                    roots.append(path)
        if not tool_ids:
            tool_ids = [step.tool_id]
        if not roots and mission.target_path:
            roots = [mission.target_path]
        return PendingRequest(
            kind="authorization",
            question=(
                "Autoriser l'accès en lecture"
                + (f" dans {', '.join(roots)}" if roots else "")
                + f" pour les outils : {', '.join(tool_ids)} ?"
            ),
            tool_ids=tool_ids,
            allowed_roots=roots,
            details={"step_id": step.step_id},
            created_at=self._clock(),
            # Jeton d'approbation : lié à CETTE demande (mission,
            # périmètre, utilisateur). Imprévisible, à usage unique, il
            # expire et n'est jamais déduit d'un identifiant de mission.
            approval_token=secrets.token_hex(32),
            requested_by_user=mission.owner_user_id,
            expires_at=self._clock() + self.limits.approval_ttl_seconds,
        )

    def _analyze(self, mission: Mission) -> str:
        """Produire une analyse qualitative à partir des faits observés.

        L'analyse est produite par le fournisseur IA si un fournisseur est
        configuré. Elle est renvoyée brute mais **étiquetée comme non
        vérifiée** par le générateur de rapport : elle ne remplace jamais
        un fait observé et n'a aucun effet sur les autorisations.
        """
        provider = getattr(self.planner, "_provider", None)
        if provider is None:
            return ""
        if not mission.facts:
            return ""
        try:
            if not provider.is_available():
                return ""
        except Exception:  # noqa: BLE001
            return ""
        facts = "\n".join(f"- {fact}" for fact in mission.facts)
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu analyses les faits observés par une mission MILES. "
                    "Réponds en français, de façon concise et factuelle. "
                    "N'invente aucun fait absent de la liste fournie et "
                    "n'exécute aucune commande."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Objectif : {mission.objective}\n"
                    f"Faits observés :\n{facts}"
                ),
            },
        ]
        try:
            return str(provider.chat(messages) or "").strip()
        except Exception:  # noqa: BLE001 — analyse facultative
            return ""

    def _save(self, mission: Mission) -> None:
        """Enregistrer la mission en persistance (best effort)."""
        if self.store is None:
            return
        try:
            self.store.save(mission)
        except Exception:  # noqa: BLE001 — la persistance ne doit rien casser
            logger.warning("Enregistrement de la mission impossible.")

    def _record_event(self, mission: Mission, kind: str, detail: str = "") -> None:
        """Consigner un événement de mission (traçabilité).

        La table ``mission_events`` de la persistance est ainsi réellement
        alimentée : chaque transition notable d'une mission est tracée.
        """
        if self.store is None:
            return
        try:
            self.store.record_event(mission.mission_id, kind, detail)
        except Exception:  # noqa: BLE001 — la traçabilité ne doit rien casser
            logger.warning("Enregistrement d'un evenement de mission impossible.")
