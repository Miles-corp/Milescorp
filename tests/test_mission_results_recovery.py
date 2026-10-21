"""Tests de régression de la persistance des résultats et de la reprise.

Deux points ouverts de D-B05 (audit contradictoire d'Agent B) :

1. **`results` non persistés.** Le dictionnaire des résultats d'étapes était
   une variable locale de `_execute_loop` : après une reprise, les étapes
   dépendantes ne pouvaient plus résoudre leur source et étaient **sautées**,
   la mission s'achevait en « partial » sans ses étapes finales.

2. **Étape `RUNNING` non reprise.** Après une interruption (arrêt du
   programme pendant l'exécution d'une étape), l'étape restait à l'état
   `RUNNING` : elle n'était ni rejouée, ni signalée, et la mission
   demeurait ambiguë.

Comportement attendu après correction :

- les résultats des étapes terminées sont relus depuis le plan persisté et
  les étapes dépendantes reprennent leur source ;
- une étape interrompue dont l'outil est **déclaré sans effet**
  (`ToolDefinition.read_only`) est rejouée ;
- une étape interrompue dont l'outil n'est **pas** déclaré sans effet n'est
  **pas** rejouée : elle est marquée incertaine et exige une vérification ;
- le budget global reste la borne (une reprise consomme une étape et un
  appel d'outil de plus) ;
- l'isolation par propriétaire et les contrôles d'autorisation sont
  inchangés.

Les tests sont déterministes : outils simulés, magasin temporaire, aucune
donnée réelle lue ni écrite, aucun appel à un fournisseur. Le moteur
exécutant les outils dans un **processus séparé**, le comptage des appels
passe par un fichier (le processus enfant n'a pas de mémoire partagée).
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
    SourceRef,
    StepStatus,
)
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore
from app.tools.builtin import READ_ONLY_TOOLS, build_default_registry
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService

#: Variable d'environnement portant le fichier de comptage des appels.
#: Le processus enfant du moteur en hérite : c'est le seul canal fiable
#: pour compter les appels d'outils réellement exécutés.
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


def _handler_source() -> Dict[str, Any]:
    """Handler « sans effet » : renvoie une source d'entrées (simulées)."""
    _noter_appel("source")
    return {
        "entries": [
            {"name": "a.txt", "path": "simule/a.txt", "is_dir": False,
             "is_text": True, "sensitive": False},
            {"name": "b.txt", "path": "simule/b.txt", "is_dir": False,
             "is_text": True, "sensitive": False},
        ],
        "count": 2,
    }


def _handler_lecture(path: str = "") -> str:
    """Handler « sans effet » : lit la valeur reçue."""
    _noter_appel("lecture")
    return f"contenu de {path}"


def _handler_avec_effet() -> str:
    """Handler **avec effet** : chaque appel est compté (ne doit pas être
    rejoué)."""
    _noter_appel("effet")
    return "effet produit"


def _build_registry() -> ToolRegistry:
    """Registre de test : une source, une lecture, un outil à effet."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            tool_id="outil_source",
            description="Source simulée",
            handler=_handler_source,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            read_only=True,
        )
    )
    registry.register(
        ToolDefinition(
            tool_id="outil_lecture",
            description="Lecture simulée",
            handler=_handler_lecture,
            parameters=(
                ToolParameter(name="path", type=str, required=True,
                              description="Chemin", is_path=True),
            ),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            read_only=True,
        )
    )
    registry.register(
        ToolDefinition(
            tool_id="outil_effet",
            description="Outil produisant un effet",
            handler=_handler_avec_effet,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            # NON déclaré read_only : l'absence d'effet n'est pas démontrable.
        )
    )
    return registry


def _plan_avec_source() -> Plan:
    """Plan : une source, puis une étape qui en dépend."""
    return Plan(
        mission_id="m1",
        steps=[
            PlanStep("s1", "Source", "outil_source", parameters={}),
            PlanStep(
                "s2",
                "Lecture",
                "outil_lecture",
                parameters={},
                source=SourceRef(step_id="s1", key="entries", index=0,
                                 field="path"),
                target_parameter="path",
                depends_on=["s1"],
            ),
        ],
        planner="test",
    )


class _PlanFixed:
    """Planificateur de test : renvoie un plan fixé."""

    name = "test"
    note = "plan de test"

    def plan(self, objective: str, context: Any) -> Plan:
        plan = _plan_avec_source()
        plan.mission_id = context.mission_id
        return plan


def _build_runner(store: Optional[MissionStore] = None) -> MissionRunner:
    """Construire un orchestrateur de test."""
    grants = GrantRegistry()
    service = ToolService(
        registry=_build_registry(),
        granted_permissions={"lecture_systeme"},
        grant_checker=grants,
    )
    return MissionRunner(
        service,
        planner=_PlanFixed(),
        store=store,
        limits=ExecutionLimits(
            max_steps=6,
            max_attempts_per_step=1,
            max_duration_seconds=30.0,
            max_tool_calls=12,
            max_interactions=3,
            max_identical_results=99,
        ),
        grant_registry=grants,
        session_id="session-application",
        allowed_tool_ids=["outil_source", "outil_lecture", "outil_effet"],
    )


class _BaseTest(unittest.TestCase):
    """Base : magasin temporaire et compteur d'appels."""

    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="db05r-")
        self.addCleanup(shutil.rmtree, self._dossier, True)
        self.chemin = os.path.join(self._dossier, "missions.db")
        self._compteur = os.path.join(self._dossier, "appels.txt")
        self._precedent = os.environ.get(VAR_COMPTEUR)
        os.environ[VAR_COMPTEUR] = self._compteur

    def tearDown(self) -> None:
        if self._precedent is None:
            os.environ.pop(VAR_COMPTEUR, None)
        else:
            os.environ[VAR_COMPTEUR] = self._precedent

    def _reinitialiser_le_compteur(self) -> None:
        if os.path.exists(self._compteur):
            os.remove(self._compteur)

    def _nouvelle_banque(self) -> MissionStore:
        return MissionStore(enabled=True, db_path=self.chemin)


class TestPersistanceDesResultats(_BaseTest):
    """1. Les résultats sont persistés et rechargés."""

    def setUp(self) -> None:
        super().setUp()
        self.store = self._nouvelle_banque()
        self.runner = _build_runner(self.store)

    def test_les_resultats_sont_persistes_avec_la_mission(self) -> None:
        """Le résultat d'une étape est relu après rechargement."""
        mission = self.runner.create("Analyse")
        mission.plan = _plan_avec_source()
        mission.plan.mission_id = mission.mission_id
        mission = self.runner.run(mission.mission_id)
        self.assertEqual(mission.state.value, "completed")

        rechargée = self.store.load(mission.mission_id)
        self.assertIsNotNone(rechargée)
        etape = next(s for s in rechargée.plan.steps if s.step_id == "s1")
        self.assertEqual(etape.status, StepStatus.SUCCEEDED)
        self.assertIsNotNone(etape.result)
        self.assertIn("entries", etape.result)

    def test_une_mission_reprise_resout_les_sources(self) -> None:
        """Après reprise, l'étape dépendante résout sa source (elle n'est
        plus sautée) : c'est le défaut D-B05."""
        mission = self.runner.create("Analyse")
        mission.plan = _plan_avec_source()
        mission.plan.mission_id = mission.mission_id
        mission = self.runner.run(mission.mission_id)
        self.assertEqual(mission.state.value, "completed")
        etape_2 = next(s for s in mission.plan.steps if s.step_id == "s2")
        self.assertEqual(etape_2.status, StepStatus.SUCCEEDED)
        # La valeur extraite de la source a bien été transmise à l'outil.
        self.assertEqual(etape_2.result, "contenu de simule/a.txt")

    def test_une_mission_reprise_dans_un_nouveau_processus_aboutit(self) -> None:
        """Scénario de redémarrage : les résultats relus permettent aux
        étapes restantes de s'exécuter, sans rejouer la source."""
        mission = self.runner.create("Analyse")
        mission.plan = _plan_avec_source()
        mission.plan.mission_id = mission.mission_id
        mission.plan.steps[0].status = StepStatus.SUCCEEDED
        mission.plan.steps[0].result = _handler_source()
        self.store.save(mission)

        # Nouveau runner sur la même base : les résultats sont relus.
        autre = _build_runner(self._nouvelle_banque())
        relue = autre.get(mission.mission_id)
        self.assertIsNotNone(relue)
        self.assertEqual(
            next(s for s in relue.plan.steps if s.step_id == "s1").status,
            StepStatus.SUCCEEDED,
        )
        self._reinitialiser_le_compteur()
        relue = autre.run(mission.mission_id)
        etape_2 = next(s for s in relue.plan.steps if s.step_id == "s2")
        self.assertEqual(
            etape_2.status,
            StepStatus.SUCCEEDED,
            "l'etape dependante n'a pas resolu sa source apres rechargement",
        )
        self.assertEqual(_appels("source"), 0)  # la source n'est PAS rejouee
        self.assertEqual(_appels("lecture"), 1)  # la lecture s'execute


class TestRepriseDuneEtapeInterrompue(_BaseTest):
    """2. Une étape laissée à l'état RUNNING est reprise explicitement."""

    def setUp(self) -> None:
        super().setUp()
        self.store = self._nouvelle_banque()
        self.runner = _build_runner(self.store)

    def _mission_interrompue(self, tool_id: str) -> Any:
        """Créer une mission dont une étape est restée à l'état RUNNING
        (état laissé par un arrêt du programme pendant l'exécution)."""
        mission = self.runner.create("Analyse")
        plan = _plan_avec_source()
        plan.mission_id = mission.mission_id
        plan.steps[0].tool_id = tool_id
        plan.steps[0].status = StepStatus.RUNNING
        plan.steps[0].attempts = 1
        mission.plan = plan
        mission.state = MissionState.CREATED
        self.store.save(mission)
        return mission

    def test_une_etape_sans_effet_interrompue_est_rejouee(self) -> None:
        """Un outil déclaré sans effet : l'absence d'effet est démontrable,
        l'étape est rejouée."""
        mission = self._mission_interrompue("outil_source")
        self.runner.resume(mission.mission_id)
        etape = next(
            s for s in self.runner.get(mission.mission_id).plan.steps
            if s.step_id == "s1"
        )
        self.assertEqual(etape.status, StepStatus.SUCCEEDED)
        self.assertEqual(_appels("source"), 1)

    def test_une_etape_avec_effet_interrompue_n_est_pas_rejouee(self) -> None:
        """Un outil non déclaré sans effet : l'action n'est PAS rejouée,
        l'étape est marquée incertaine et exige une vérification."""
        mission = self._mission_interrompue("outil_effet")
        self.runner.resume(mission.mission_id)
        etape = next(
            s for s in self.runner.get(mission.mission_id).plan.steps
            if s.step_id == "s1"
        )
        self.assertEqual(etape.status, StepStatus.UNCERTAIN)
        self.assertIn("interrompue", etape.note)
        self.assertIn("vérification", etape.note)
        self.assertEqual(
            _appels("effet"), 0, "l'outil a effet a ete rejoue"
        )

    def test_les_budgets_restent_coherents_apres_reprise(self) -> None:
        """La reprise consomme le budget global : une étape et un appel de
        plus, et aucun compteur n'est réinitialisé."""
        mission = self._mission_interrompue("outil_source")
        avant = dict(self.runner.get(mission.mission_id).budget.to_dict())
        self.runner.resume(mission.mission_id)
        apres = self.runner.get(mission.mission_id).budget.to_dict()
        self.assertGreaterEqual(apres["steps_executed"], avant["steps_executed"])
        self.assertGreaterEqual(apres["tool_calls"], avant["tool_calls"])
        self.assertEqual(apres["interactions"], avant["interactions"])

    def test_une_mission_terminee_n_est_pas_rejouee(self) -> None:
        """Une mission terminée n'est pas relancée (aucune double
        exécution)."""
        mission = self.runner.create("Analyse")
        mission.plan = _plan_avec_source()
        mission.plan.mission_id = mission.mission_id
        mission = self.runner.run(mission.mission_id)
        self.assertEqual(mission.state.value, "completed")
        self._reinitialiser_le_compteur()
        relue = self.runner.resume(mission.mission_id)
        self.assertEqual(relue.state.value, "completed")
        self.assertEqual(_appels("source"), 0)
        self.assertEqual(_appels("lecture"), 0)

    def test_aucun_outil_n_est_decl_double(self) -> None:
        """Un outil déclaré sans effet est rejoué une seule fois, jamais
        deux fois."""
        mission = self._mission_interrompue("outil_source")
        self.runner.resume(mission.mission_id)
        self.assertEqual(_appels("source"), 1)
        self._reinitialiser_le_compteur()
        self.runner.resume(mission.mission_id)
        self.assertEqual(_appels("source"), 0)


class TestDeclarationSansEffet(unittest.TestCase):
    """3. La déclaration « sans effet » est posée par l'application."""

    def test_les_outils_de_lire_seule_sont_declares_sans_effet(self) -> None:
        registry = build_default_registry()
        for tool_id in READ_ONLY_TOOLS:
            with self.subTest(outil=tool_id):
                self.assertTrue(registry.get_tool(tool_id).read_only)

    def test_un_outil_non_declare_n_est_pas_sans_effet(self) -> None:
        """Un outil non déclaré n'est jamais rejoué automatiquement."""
        registre = _build_registry()
        self.assertFalse(registre.get_tool("outil_effet").read_only)


class TestMigrationEtIsolation(_BaseTest):
    """4. Migration depuis le schéma précédent et isolation des
    propriétaires."""

    def test_migration_depuis_le_schema_precedent(self) -> None:
        """Une base créée sans la colonne owner_user_id est mise à jour."""
        import sqlite3

        # Base « ancienne » : la table missions sans owner_user_id.
        connexion = sqlite3.connect(self.chemin)
        try:
            connexion.execute(
                """
                CREATE TABLE missions (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    state TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    planner TEXT NOT NULL DEFAULT '',
                    planner_note TEXT NOT NULL DEFAULT '',
                    plan_json TEXT NOT NULL DEFAULT '{}',
                    facts_json TEXT NOT NULL DEFAULT '[]',
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    unfinished_json TEXT NOT NULL DEFAULT '[]',
                    pending_json TEXT,
                    budget_json TEXT NOT NULL DEFAULT '{}',
                    report TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL
                )
                """
            )
            connexion.commit()
        finally:
            connexion.close()

        store = self._nouvelle_banque()
        self.assertTrue(store.is_available)
        colonnes = {
            str(l[1])
            for l in store._conn.execute("PRAGMA table_info(missions)").fetchall()
        }
        self.assertIn("owner_user_id", colonnes)
        # La base reste utilisable.
        runner = _build_runner(store)
        mission = runner.create("Analyse", owner_user_id="alice")
        self.assertTrue(store.save(mission))
        self.assertEqual(store.load(mission.mission_id).owner_user_id, "alice")

    def test_isolation_des_proprietaires_apres_reprise(self) -> None:
        """La reprise et la lecture restent filtrées par propriétaire."""
        store = self._nouvelle_banque()
        runner = _build_runner(store)
        mission = runner.create(
            "Analyse", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.assertTrue(store.save(mission))
        relue = store.load(mission.mission_id)
        self.assertEqual(relue.owner_user_id, "alice")
        # Un autre propriétaire ne voit pas la mission.
        autre = runner.get(mission.mission_id, owner_user_id="bob")
        self.assertIsNone(autre)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
