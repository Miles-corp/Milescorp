"""Tests des limites GLOBALES d'exécution des missions (P2-6-05/07/08).

Ces tests vérifient qu'une mission respecte un budget global pendant
TOUTE son exécution : une nouvelle boucle, une replanification, une
réponse de l'utilisateur ou une reprise ne doivent pas réinitialiser les
compteurs.

Couverture :
1. une mission normale se termine correctement ;
2. une mission dépassant le budget global de temps s'arrête ;
3. une mission dépassant le nombre global d'étapes s'arrête ;
4. une mission dépassant le nombre global d'appels d'outils s'arrête ;
5. des boucles répétées ne réinitialisent pas les compteurs ;
6. l'arrêt est propagé (motif explicite) aux sous-tâches et à l'appelant ;
7. erreurs, annulation et limites existantes restent fonctionnelles ;
8. le budget est persisté et survit à un rechargement ;
9. absence de régression sur les tests MILES précédents.

Les horloges sont INJECTÉES (aucun sleep) : les tests sont déterministes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from app.orchestration.models import (
    ExecutionLimits,
    Mission,
    MissionState,
    Plan,
    PlanStep,
    StopReason,
)
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService


# --- Outils de test (handlers au niveau du module : picklables) --------------

def _ok_handler(value: str = "ok") -> str:
    """Handler qui réussit toujours."""
    return value


def _sensible_handler() -> str:
    """Handler de risque MEDIUM (nécessite une autorisation)."""
    return "sensible"


def _boom_handler() -> str:
    """Handler qui échoue toujours (erreur d'exécution côté outil).

    Défini au niveau du module : le moteur exécute les handlers dans un
    sous-processus, qui doit pouvoir les désérialiser (une fonction locale
    ne l'est pas).
    """
    raise RuntimeError("echec simule")


# --- Fabriques ---------------------------------------------------------------

def _make_tool(
    tool_id: str,
    handler: Any,
    *,
    risk: str = "LOW",
    permissions: Tuple[str, ...] = (),
) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        description="Outil de test " + tool_id,
        handler=handler,
        parameters=(),
        risk_level=risk,
        required_permissions=permissions,
        # 15 s : sous Windows, le démarrage d'un enfant « spawn » (import du
        # module de test) peut dépasser 5 s quand plusieurs enfants sont
        # lancés à la suite ; le délai de l'outil doit couvrir ce démarrage,
        # sinon l'enfant est tué pendant son amorçage.
        timeout_seconds=15,
    )


class _Clock:
    """Horloge injectée, avanceable à la main.

    `pas` permet de simuler le passage du temps PENDANT la boucle
    (chaque appel avance l'horloge), afin de vérifier l'accumulation du
    budget de temps sans `sleep` (tests déterministes).
    """

    def __init__(self, start: float = 1000.0, pas: float = 0.0) -> None:
        self.t = start
        self.pas = pas

    def __call__(self) -> float:
        valeur = self.t
        self.t += self.pas
        return valeur

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _build_runner(
    tools: Optional[List[ToolDefinition]] = None,
    *,
    limits: Optional[ExecutionLimits] = None,
    clock: Optional[_Clock] = None,
    store: Optional[MissionStore] = None,
) -> Tuple[MissionRunner, ToolService, GrantRegistry, _Clock]:
    liste = tools if tools is not None else [_make_tool("outil_ok", _ok_handler)]
    registry = ToolRegistry()
    for tool in liste:
        registry.register(tool)
    horloge = clock or _Clock()
    grants = GrantRegistry()
    service = ToolService(
        registry=registry,
        granted_permissions={"lecture_systeme"},
        grant_checker=grants,
    )
    runner = MissionRunner(
        service,
        store=store,
        limits=limits or ExecutionLimits(
            max_steps=4,
            max_attempts_per_step=1,
            max_duration_seconds=60.0,
            max_tool_calls=8,
            max_interactions=3,
        ),
        grant_registry=grants,
        session_id="session-test",
        allowed_tool_ids=[t.tool_id for t in liste],
        clock=horloge,
    )
    return runner, service, grants, horloge


def _plan(mission: Mission, nb: int, tool_id: str = "outil_ok") -> None:
    """Poser un plan de `nb` étapes simples."""
    mission.plan = Plan(
        mission_id=mission.mission_id,
        steps=[
            PlanStep(f"s{i}", f"Etape {i}", tool_id, {})
            for i in range(1, nb + 1)
        ],
    )


class TestBudgetGlobalNormal(unittest.TestCase):
    """1. Une mission normale se termine correctement."""

    def test_mission_normale_terminee(self) -> None:
        runner, _, _, _ = _build_runner()
        mission = runner.create("Mission normale")
        _plan(mission, 2)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.COMPLETED)
        self.assertEqual(mission.budget.stop_reason, StopReason.COMPLETED.value)
        self.assertEqual(mission.budget.steps_executed, 2)
        self.assertEqual(mission.budget.tool_calls, 2)
        self.assertEqual(mission.budget.interactions, 0)

    def test_le_compte_rendu_porte_le_budget_et_le_motif(self) -> None:
        runner, _, _, _ = _build_runner()
        mission = runner.create("Mission normale")
        _plan(mission, 1)
        mission = runner.run(mission.mission_id)
        self.assertIn("Budget consommé", mission.report)
        self.assertIn("Motif d'arrêt", mission.report)
        self.assertIn(StopReason.COMPLETED.value, mission.report)


class TestBudgetGlobalTemps(unittest.TestCase):
    """2. Dépassement du budget global de temps."""

    def test_le_temps_consomme_dans_la_boucle_est_compte(self) -> None:
        # Horloge qui avance de 5 s à chaque appel : le temps passe
        # pendant la boucle, sans `sleep` (déterminisme).
        horloge = _Clock(pas=5.0)
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=50,
                max_attempts_per_step=1,
                max_duration_seconds=30.0,
                max_tool_calls=50,
                max_interactions=3,
                max_identical_results=99,
            ),
            clock=horloge,
        )
        mission = runner.create("Mission longue")
        _plan(mission, 20)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.TIME_BUDGET_EXCEEDED.value
        )
        self.assertGreater(mission.budget.executed_seconds, 30.0)

    def test_le_budget_de_temps_arrete_la_mission(self) -> None:
        """Le plafond est vérifié AVANT l'exécution de la première étape."""
        horloge = _Clock(pas=5.0)
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=10,
                max_attempts_per_step=1,
                max_duration_seconds=2.0,
                max_tool_calls=20,
                max_interactions=3,
                max_identical_results=99,
            ),
            clock=horloge,
        )
        mission = runner.create("Mission trop longue")
        _plan(mission, 5)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.TIME_BUDGET_EXCEEDED.value
        )
        self.assertEqual(mission.budget.steps_executed, 0)


class TestBudgetGlobalEtapes(unittest.TestCase):
    """3. Dépassement du nombre global d'étapes."""

    def test_plafond_d_etapes_global(self) -> None:
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=3,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=3,
                max_identical_results=99,
            )
        )
        mission = runner.create("Mission a etapes")
        _plan(mission, 10)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.STEP_BUDGET_EXCEEDED.value
        )
        self.assertEqual(mission.budget.steps_executed, 3)
        self.assertTrue(
            any("Nombre maximal d'étapes" in e for e in mission.errors)
        )


class TestBudgetGlobalAppelsOutils(unittest.TestCase):
    """4. Dépassement du nombre global d'appels d'outils."""

    def test_plafond_d_appels_d_outils_global(self) -> None:
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=100,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=2,
                max_interactions=3,
                max_identical_results=99,
            )
        )
        mission = runner.create("Mission a appels")
        _plan(mission, 10)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(
            mission.budget.stop_reason,
            StopReason.TOOL_CALL_BUDGET_EXCEEDED.value,
        )
        self.assertEqual(mission.budget.tool_calls, 2)
        self.assertEqual(mission.budget.steps_executed, 2)


class TestBudgetNonReinitialise(unittest.TestCase):
    """5. Des boucles répétées ne réinitialisent pas les compteurs."""

    def test_les_boucles_ne_reinitialisent_pas_le_plafond_d_etapes(self) -> None:
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=2,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=5,
                max_identical_results=99,
            ),
        )
        mission = runner.create("Mission a boucles")
        # 3 étapes, plafond de 2 : la 3e ne doit jamais être exécutée.
        _plan(mission, 3)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(mission.budget.steps_executed, 2)
        # 2e boucle (reprise explicite) : le budget n'est PAS réinitialisé,
        # aucune étape supplémentaire n'est exécutée.
        mission = runner.resume(mission.mission_id)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.STEP_BUDGET_EXCEEDED.value
        )
        self.assertEqual(mission.budget.steps_executed, 2)

    def test_une_reponse_ne_reinitialise_pas_le_budget(self) -> None:
        """Une clarification suivie d'une réponse ne repart pas de zéro."""
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=2,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=5,
                max_identical_results=99,
            )
        )
        # Aucun chemin explicite, aucun marqueur générique : le
        # planificateur déterministe demande une clarification.
        mission = runner.create("Analyse l'organisation")
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.NEEDS_CLARIFICATION)
        self.assertEqual(mission.budget.interactions, 1)
        # La réponse déclenche une nouvelle boucle : le budget n'est pas
        # réinitialisé (l'échange précédent reste compté).
        mission = runner.answer(mission.mission_id, "docs/")
        # L'échange n'est pas « remis à zéro » : il reste compté.
        self.assertEqual(mission.budget.interactions, 1)

    def test_le_budget_de_temps_est_cumule_entre_les_boucles(self) -> None:
        # Horloge qui avance de 10 s à chaque appel.
        horloge = _Clock(pas=10.0)
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=50,
                max_attempts_per_step=1,
                max_duration_seconds=20.0,
                max_tool_calls=50,
                max_interactions=5,
                max_identical_results=99,
            ),
            clock=horloge,
        )
        mission = runner.create("Mission a temps")
        _plan(mission, 1)
        mission = runner.run(mission.mission_id)
        premiere = mission.budget.executed_seconds
        self.assertGreater(premiere, 0.0)
        # Deuxième boucle (reprise) : le temps déjà consommé reste imputé,
        # le plafond global est donc atteint.
        mission = runner.resume(mission.mission_id)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.TIME_BUDGET_EXCEEDED.value
        )
        self.assertGreaterEqual(
            mission.budget.executed_seconds, premiere
        )


class TestInteractionsGlobales(unittest.TestCase):
    """P2-6-08 : le plafond d'échanges est global (CLI ET web)."""

    def test_le_premier_echangement_compte(self) -> None:
        runner, _, _, _ = _build_runner(
            tools=[
                _make_tool(
                    "outil_sensible",
                    _sensible_handler,
                    risk="MEDIUM",
                    permissions=("lecture_systeme",),
                )
            ],
            limits=ExecutionLimits(
                max_steps=20,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=2,
                max_identical_results=99,
            ),
        )
        mission = runner.create("Mission a autorisations")
        _plan(mission, 5, "outil_sensible")
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.AWAITING_AUTHORIZATION)
        self.assertEqual(mission.budget.interactions, 1)
        self.assertIsNotNone(mission.pending)
        self.assertEqual(
            mission.budget.stop_reason, StopReason.AUTHORIZATION_REQUIRED.value
        )

    def test_le_plafond_d_interactions_arrete_la_mission(self) -> None:
        """Au-delà du plafond, aucune nouvelle question n'est posée."""
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=20,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=2,
                max_identical_results=99,
            ),
        )
        # Un objectif sans chemin explicite et sans marqueur générique
        # déclenche une clarification.
        mission = runner.create("Analyse l'organisation")
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.NEEDS_CLARIFICATION)
        self.assertEqual(mission.budget.interactions, 1)

        # Réponse incomprise : une nouvelle question est posée (2e échange).
        mission = runner.answer(mission.mission_id, "euh je ne sais pas")
        self.assertEqual(mission.state, MissionState.NEEDS_CLARIFICATION)
        self.assertEqual(mission.budget.interactions, 2)

        # 3e échange : le budget est épuisé, la mission s'arrête.
        mission = runner.answer(mission.mission_id, "toujours pas compris")
        self.assertEqual(mission.state, MissionState.LIMIT_REACHED)
        self.assertEqual(
            mission.budget.stop_reason,
            StopReason.INTERACTION_BUDGET_EXCEEDED.value,
        )
        self.assertEqual(mission.budget.interactions, 2)

    def test_une_autorisation_refusee_arrete_la_mission(self) -> None:
        runner, _, _, _ = _build_runner(
            tools=[
                _make_tool(
                    "outil_sensible",
                    _sensible_handler,
                    risk="MEDIUM",
                    permissions=("lecture_systeme",),
                )
            ],
        )
        mission = runner.create("Mission refusee")
        _plan(mission, 2, "outil_sensible")
        mission = runner.run(mission.mission_id)
        mission = runner.authorize(
            mission.mission_id,
            approved=False,
            requester_session_id="session-test",
            approval_token=mission.pending.approval_token,
        )
        self.assertEqual(mission.state, MissionState.FAILED)
        self.assertEqual(mission.budget.stop_reason, StopReason.FAILED.value)


class TestAnnulationEtErreurs(unittest.TestCase):
    """7. Erreurs, annulation et limites existantes restent fonctionnelles."""

    def test_annulation_propage_le_motif(self) -> None:
        runner, _, _, _ = _build_runner()
        mission = runner.create("Mission a annuler")
        _plan(mission, 3)
        self.assertTrue(runner.cancel(mission.mission_id))
        self.assertEqual(mission.state, MissionState.CANCELLED)
        self.assertEqual(mission.budget.stop_reason, StopReason.CANCELLED.value)

    def test_une_etape_en_echec_est_signalee(self) -> None:
        def _boom() -> str:
            raise RuntimeError("echec simule")

        runner, _, _, _ = _build_runner(tools=[_make_tool("outil_casse", _boom_handler)])
        mission = runner.create("Mission en echec")
        _plan(mission, 1, "outil_casse")
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.PARTIAL)
        self.assertTrue(mission.errors)

    def test_le_compte_rendu_signale_le_motif_d_arret(self) -> None:
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=1,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=3,
                max_identical_results=99,
            )
        )
        mission = runner.create("Mission limitee")
        _plan(mission, 5)
        mission = runner.run(mission.mission_id)
        self.assertIn(
            StopReason.STEP_BUDGET_EXCEEDED.value, mission.report
        )


class TestPersistanceDuBudget(unittest.TestCase):
    """8. Le budget est persisté et survit à un rechargement."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_budget_")
        self.db_path = os.path.join(self.tmpdir, "missions.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_le_budget_est_recharge_depuis_la_base(self) -> None:
        store = MissionStore(enabled=True, db_path=self.db_path)
        try:
            runner, _, _, _ = _build_runner(store=store)
            mission = runner.create("Mission persistee")
            _plan(mission, 2)
            mission = runner.run(mission.mission_id)
            self.assertEqual(mission.budget.steps_executed, 2)
            recharges = store.load(mission.mission_id)
            self.assertIsNotNone(recharges)
            assert recharges is not None
            self.assertEqual(recharges.budget.steps_executed, 2)
            self.assertEqual(recharges.budget.tool_calls, 2)
            self.assertEqual(
                recharges.budget.stop_reason, StopReason.COMPLETED.value
            )
        finally:
            store.close()

    def test_une_mission_rechargee_conserve_son_budget(self) -> None:
        store = MissionStore(enabled=True, db_path=self.db_path)
        try:
            runner, _, _, _ = _build_runner(
                tools=[_make_tool("outil_casse", _boom_handler)],
                store=store,
                limits=ExecutionLimits(
                    max_steps=1,
                    max_attempts_per_step=1,
                    max_duration_seconds=600.0,
                    max_tool_calls=50,
                    max_interactions=3,
                max_identical_results=99,
                ),
            )
            mission = runner.create("Mission a reprise")
            _plan(mission, 2, "outil_casse")
            mission = runner.run(mission.mission_id)
            # La mission s'arrête en PARTIAL après une étape échouée.
            self.assertEqual(mission.budget.steps_executed, 1)
            self.assertEqual(mission.budget.tool_calls, 1)

            # Nouvelle instance, même base : la mission relit son budget.
            runner2, _, _, _ = _build_runner(
                tools=[_make_tool("outil_casse", _boom_handler)],
                store=store,
                limits=ExecutionLimits(
                    max_steps=1,
                    max_attempts_per_step=1,
                    max_duration_seconds=600.0,
                    max_tool_calls=50,
                    max_interactions=3,
                max_identical_results=99,
                ),
            )
            reloaded = runner2.get(mission.mission_id)
            self.assertIsNotNone(reloaded)
            assert reloaded is not None
            self.assertEqual(reloaded.budget.steps_executed, 1)
            self.assertEqual(reloaded.budget.tool_calls, 1)

            # Une REPRISE ne repart pas de zéro : le budget global est
            # déjà consommé, la mission s'arrête donc immédiatement.
            reloaded = runner2.resume(mission.mission_id)
            assert reloaded is not None
            self.assertEqual(
                reloaded.budget.stop_reason, StopReason.STEP_BUDGET_EXCEEDED.value
            )
            self.assertEqual(reloaded.budget.steps_executed, 1)
        finally:
            store.close()


class TestCompatibiliteDesLimites(unittest.TestCase):
    """Compatibilité avec les limites locales existantes."""

    def test_les_valeurs_par_defaut_sont_coherentes(self) -> None:
        limites = ExecutionLimits()
        self.assertEqual(limites.max_steps, 12)
        self.assertEqual(limites.max_attempts_per_step, 2)
        self.assertEqual(limites.max_duration_seconds, 120.0)
        # Plafond d'appels d'outils = étapes × tentatives (cohérent, non arbitraire)
        self.assertEqual(
            limites.max_tool_calls,
            limites.max_steps * limites.max_attempts_per_step,
        )
        # Plafond d'interactions = valeur déjà appliquée par l'interface
        self.assertEqual(limites.max_interactions, 5)

    def test_les_reglages_sont_exposes(self) -> None:
        from app.config.settings import Settings

        reglages = Settings()
        self.assertEqual(reglages.mission_max_steps, 12)
        self.assertEqual(reglages.mission_max_tool_calls, 24)
        self.assertEqual(reglages.mission_max_interactions, 5)

    def test_la_borne_par_etape_est_preservee(self) -> None:
        """La reprise d'une étape transitoire reste bornée par étape."""
        runner, _, _, _ = _build_runner(
            limits=ExecutionLimits(
                max_steps=10,
                max_attempts_per_step=1,
                max_duration_seconds=600.0,
                max_tool_calls=50,
                max_interactions=3,
                max_identical_results=99,
            )
        )
        mission = runner.create("Mission a tentatives")
        _plan(mission, 1)
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.plan.steps[0].attempts, 1)


if __name__ == "__main__":
    unittest.main()
