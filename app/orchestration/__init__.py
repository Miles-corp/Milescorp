"""Orchestration de missions MILES.

Ce package implémente la première capacité d'autonomie de MILES : recevoir
un objectif en langage naturel, préparer un plan, exécuter plusieurs
étapes avec les outils autorisés, observer les résultats, gérer les erreurs
et produire un compte rendu fiable.

Composants :

- :mod:`app.orchestration.models` : mission, plan, étapes, bornes ;
- :mod:`app.orchestration.planner` : plan déterministe et plan IA validé ;
- :mod:`app.orchestration.executor` : exécution contrôlée via ToolService ;
- :mod:`app.orchestration.observer` : analyse des résultats ;
- :mod:`app.orchestration.runner` : coordination du cycle complet ;
- :mod:`app.orchestration.store` : persistance des missions ;
- :mod:`app.orchestration.report` : compte rendu structuré.

Le moteur d'outils n'est jamais réimplémenté : toute exécution passe par
:class:`app.tools.service.ToolService`.
"""

from app.orchestration.executor import Executor, StepOutcome
from app.orchestration.models import (
    ExecutionLimits,
    Mission,
    MissionState,
    PendingRequest,
    Plan,
    PlanStep,
    SourceRef,
    StepStatus,
)
from app.orchestration.observer import Observation, Observer
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
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore

__all__ = [
    "ClarificationRequired",
    "DeterministicPlanner",
    "ExecutionLimits",
    "Executor",
    "Mission",
    "MissionRunner",
    "MissionState",
    "MissionStore",
    "Observation",
    "Observer",
    "PendingRequest",
    "Plan",
    "PlanContext",
    "PlanRejected",
    "PlanStep",
    "Planner",
    "ProviderPlanner",
    "ReportBuilder",
    "SourceRef",
    "StepOutcome",
    "StepStatus",
    "extract_target_path",
]
