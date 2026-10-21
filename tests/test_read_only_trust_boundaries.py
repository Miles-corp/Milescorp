"""Tests des frontières de confiance autour de la propriété `read_only`.

La reprise automatique d'une étape interrompue (après l'arrêt du
programme) n'est autorisée que pour les outils dont l'**application** a
déclaré qu'ils sont sans effet de bord (`ToolDefinition.read_only`).

Ces tests vérifient les frontières réelles de l'architecture :

1. le **modèle** (source du plan) ne peut pas déclarer lui-même qu'un outil
   est sans effet : `PlanStep` n'a pas de telle propriété et le plan ne
   peut rien changer au schéma des outils ;
2. un plan ne peut pas modifier les propriétés de sécurité enregistrées d'un
   outil : la définition d'outil est **immuable** et le registre appartient à
   l'application ;
3. une propriété **absente** ou **invalide** (mauvais type) entraîne un
   comportement **prudent** : aucune reprise automatique d'une opération
   susceptible d'avoir un effet ;
4. la propriété est lue dans la **définition approuvée par
   l'application** (le registre), jamais dans la mission ni dans le plan ;
5. une étape interrompue dont l'outil est **inconnu** ou **non déclaré**
   n'est **jamais** rejouée automatiquement ;
6. les propriétés **inconnues** et les **valeurs de type incorrect** sont
   traités de façon prudente.

Les tests sont déterministes : outils simulés, magasin temporaire, compteur
d'appels par fichier (le moteur exécute les outils dans un processus
séparé), aucun fournisseur, aucune donnée réelle.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional

from app.orchestration.models import (
    ExecutionLimits,
    MissionState,
    Plan,
    PlanStep,
    StepStatus,
)
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService

#: Variable d'environnement portant le fichier de comptage des appels.
VAR_COMPTEUR = "MILES_TEST_COMPTEUR"


def _noter_appel(nom: str) -> None:
    """Noter un appel d'outil (exécuté dans le processus enfant)."""
    chemin = os.environ.get(VAR_COMPTEUR, "")
    if not chemin:
        return
    with open(chemin, "a", encoding="utf-8") as fh:
        fh.write(nom + "\n")


def _appels(nom: str) -> int:
    """Compter les appels d'un outil."""
    chemin = os.environ.get(VAR_COMPTEUR, "")
    if not chemin or not os.path.exists(chemin):
        return 0
    with open(chemin, encoding="utf-8") as fh:
        return sum(1 for ligne in fh if ligne.strip() == nom)


def _handler_outil() -> str:
    """Handler de test : compte ses appels."""
    _noter_appel("outil")
    return "resultat"


class _PlanSimple:
    """Planificateur de test : un plan d'une seule étape."""

    name = "test"
    note = "plan de test"

    def __init__(self, tool_id: str = "outil_test") -> None:
        self._tool_id = tool_id

    def plan(self, objective: str, context: Any) -> Plan:
        return Plan(
            mission_id=context.mission_id,
            steps=[PlanStep("s1", "Etape", self._tool_id, parameters={})],
            planner="test",
        )


class _BaseFrontiere(unittest.TestCase):
    """Base : magasin temporaire, compteur d'appels, outils simulés."""

    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="trust-")
        self.addCleanup(shutil.rmtree, self._dossier, True)
        self.chemin = os.path.join(self._dossier, "missions.db")
        self._compteur = os.path.join(self._dossier, "appels.txt")
        self._precedent = os.environ.get(VAR_COMPTEUR)
        os.environ[VAR_COMPTEUR] = self._compteur
        self.store = MissionStore(enabled=True, db_path=self.chemin)

    def tearDown(self) -> None:
        if self._precedent is None:
            os.environ.pop(VAR_COMPTEUR, None)
        else:
            os.environ[VAR_COMPTEUR] = self._precedent

    def _outil(self, tool_id: str = "outil_test", **kwargs: Any) -> ToolDefinition:
        """Construire un outil de test."""
        return ToolDefinition(
            tool_id=tool_id,
            description="Outil de test",
            handler=_handler_outil,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            **kwargs,
        )

    def _runner(
        self, outil: ToolDefinition, tool_id: Optional[str] = None
    ) -> MissionRunner:
        """Construire un orchestrateur n'exposant qu'un outil."""
        registre = ToolRegistry()
        registre.register(outil)
        grants = GrantRegistry()
        service = ToolService(
            registry=registre,
            granted_permissions={"lecture_systeme"},
            grant_checker=grants,
        )
        return MissionRunner(
            service,
            planner=_PlanSimple(tool_id or outil.tool_id),
            store=self.store,
            limits=ExecutionLimits(
                max_steps=4,
                max_attempts_per_step=1,
                max_duration_seconds=30.0,
                max_tool_calls=8,
                max_interactions=2,
            ),
            grant_registry=grants,
            session_id="session-application",
            allowed_tool_ids=[outil.tool_id],
        )

    def _mission_interrompue(self, runner: MissionRunner, tool_id: str) -> Any:
        """Créer une mission dont l'étape est restée à l'état RUNNING
        (état laissé par un arrêt du programme)."""
        mission = runner.create("Analyse")
        plan = Plan(
            mission_id=mission.mission_id,
            steps=[PlanStep("s1", "Etape", tool_id, parameters={})],
            planner="test",
        )
        plan.steps[0].status = StepStatus.RUNNING
        plan.steps[0].attempts = 1
        mission.plan = plan
        mission.state = MissionState.CREATED
        self.store.save(mission)
        return mission

    def _statut(self, runner: MissionRunner, mission_id: str) -> StepStatus:
        mission = runner.get(mission_id)
        return mission.plan.steps[0].status


class TestLeModeleNeDeclarePasLaPropriete(_BaseFrontiere):
    """1. Le modèle ne peut pas déclarer lui-même un outil sans effet."""

    def test_le_plan_ne_comporte_aucune_propriete_read_only(self) -> None:
        """`PlanStep` n'a pas de propriété `read_only` : une déclaration
        dans le plan est simplement ignorée."""
        etape = PlanStep.from_dict(
            {
                "step_id": "s1",
                "objective": "x",
                "tool_id": "outil",
                "parameters": {},
                "read_only": True,
                "side_effect_free": True,
            }
        )
        self.assertFalse(hasattr(etape, "read_only"))
        self.assertFalse(hasattr(etape, "side_effect_free"))

    def test_une_declaration_du_modele_est_ignoree_a_la_reprise(self) -> None:
        """Un plan qui déclare `read_only: true` pour un outil non déclaré
        sans effet : l'étape interrompue n'est PAS rejouée."""
        outil = self._outil()  # PAS déclaré read_only
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        # Le plan « du modèle » prétend que l'outil est sans effet.
        mission.plan.steps[0].result = None
        self.store.save(mission)
        # La déclaration du plan est injectée dans la mission persistée.
        mission_rechargee = self.store.load(mission.mission_id)
        payload = mission_rechargee.plan.steps[0].to_dict()
        payload["read_only"] = True
        self.assertNotIn("read_only", mission_rechargee.plan.steps[0].to_dict())

        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id),
            StepStatus.UNCERTAIN,
            "une declaration du modele a declenche une reprise automatique",
        )
        self.assertEqual(_appels("outil"), 0)


class TestUnPlanNeModifiePasLesProprietes(_BaseFrontiere):
    """2. Un plan ne peut pas modifier les propriétés enregistrées."""

    def test_la_definition_d_un_outil_est_immuable(self) -> None:
        """La définition d'outil est immuable : une tentative de
        modification est refusée."""
        outil = self._outil(read_only=True)
        with self.assertRaises(Exception):
            outil.read_only = False  # type: ignore[misc]
        self.assertTrue(outil.read_only)

    def test_un_parametre_read_only_non_declare_est_refuse(self) -> None:
        """Un plan ne peut pas non plus passer `read_only` en *paramètre*
        d'un outil : le paramètre n'est pas déclaré."""
        from app.orchestration.planner import (
            PlanContext,
            PlanRejected,
            validate_plan_payload,
        )

        registre = ToolRegistry()
        registre.register(
            ToolDefinition(
                tool_id="outil_test",
                description="Outil de test",
                handler=_handler_outil,
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=10,
            )
        )
        contexte = PlanContext(
            registry=registre,
            allowed_tool_ids=["outil_test"],
            limits=ExecutionLimits(),
            mission_id="m1",
        )
        with self.assertRaises(PlanRejected):
            validate_plan_payload(
                {
                    "steps": [
                        {
                            "objective": "x",
                            "tool": "outil_test",
                            "parameters": {"read_only": True},
                        }
                    ]
                },
                contexte,
                "m1",
            )


class TestProprieteAbsenteOuInvalide(_BaseFrontiere):
    """3. Une propriété absente ou invalide est prudente."""

    def test_une_propriete_absente_ne_declenche_pas_de_rejeu(self) -> None:
        """Un outil sans la propriété n'est jamais rejoué."""
        outil = self._outil()  # pas de read_only
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.UNCERTAIN
        )
        self.assertEqual(_appels("outil"), 0)

    def test_une_propriete_a_none_ne_declenche_pas_de_rejeu(self) -> None:
        """`read_only = None` : prudent (pas de reprise)."""
        outil = self._outil()
        object.__setattr__(outil, "read_only", None)
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.UNCERTAIN
        )
        self.assertEqual(_appels("outil"), 0)


class TestLesProprietesViennentDeLApplication(_BaseFrontiere):
    """4. La propriété est lue dans la définition approuvée."""

    def test_la_propriete_est_lue_dans_le_registre(self) -> None:
        """La décision de reprise s'appuie sur le registre (l'application),
        pas sur la mission."""
        outil = self._outil(read_only=True)
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.SUCCEEDED
        )
        self.assertEqual(_appels("outil"), 1)

    def test_la_mission_ne_peut_pas_influer_sur_la_decision(self) -> None:
        """Une mission persistée ne peut pas rendre un outil sans effet."""
        outil = self._outil()  # non déclaré sans effet
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        reloaded = self.store.load(mission.mission_id)
        self.assertFalse(
            getattr(reloaded.plan.steps[0], "read_only", False),
            "la mission porte une propriete de securite",
        )
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.UNCERTAIN
        )


class TestOutilInconnuOuNonDeclare(_BaseFrontiere):
    """5. Un outil non fiable ou non identifié n'est jamais rejoué."""

    def test_un_outil_non_identifie_n_est_jamais_rejoue(self) -> None:
        """Une étape interrompue qui référence un outil inconnu : aucune
        reprise automatique."""
        outil = self._outil(read_only=True)
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, "outil_inconnu")
        runner.resume(mission.mission_id)
        etape = self.runner_get_step(runner, mission.mission_id)
        self.assertNotEqual(etape.status, StepStatus.SUCCEEDED)
        self.assertEqual(_appels("outil"), 0)

    def test_un_outil_non_declare_par_l_application_n_est_jamais_rejoue(
        self,
    ) -> None:
        """Un outil enregistré mais non déclaré sans effet : aucune reprise
        automatique."""
        outil = self._outil()  # pas de read_only
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.UNCERTAIN
        )
        self.assertEqual(_appels("outil"), 0)

    def runner_get_step(self, runner: MissionRunner, mission_id: str) -> PlanStep:
        """Retourner la première étape d'une mission."""
        mission = runner.get(mission_id)
        return mission.plan.steps[0]


class TestProprietesInconnues(_BaseFrontiere):
    """6. Les propriétés inconnues sont ignorées."""

    def test_une_propriete_inconnue_est_ignoree(self) -> None:
        """Une propriété supplémentaire (ex. `side_effect_free`) n'a aucun
        effet : seule `read_only` compte."""
        outil = self._outil()
        object.__setattr__(outil, "side_effect_free", True)
        runner = self._runner(outil)
        mission = self._mission_interrompue(runner, outil.tool_id)
        runner.resume(mission.mission_id)
        self.assertEqual(
            self._statut(runner, mission.mission_id), StepStatus.UNCERTAIN
        )
        self.assertEqual(_appels("outil"), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
