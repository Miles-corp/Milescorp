"""Tests du défaut D2 : chemins Windows et extraction de la cible d'une mission.

Défaut D2 : ``extract_target_path`` perdait la lettre de lecteur d'un chemin
Windows absolu (``C:/Windows`` devenait ``/Windows``), parce que la classe de
caractères du jeton de chemin excluait ``:``. Le chemin extrait ne désignait
donc plus le répertoire demandé : la mission analysait un autre répertoire, et
la demande d'autorisation citait un chemin erroné.

Couverture :

1. chemins absolus Windows (lettre de lecteur conservée) ;
2. chemins Windows contenant des espaces ;
3. chemins relatifs (y compris relatifs au projet) ;
4. chemins POSIX (absolus et relatifs) ;
5. non-régression : le comportement antérieur est conservé ;
6. le confinement des chemins n'est pas affaibli : chemins hors périmètre,
   traversées de répertoires et entrées malformées restent refusés ;
7. de bout en bout : la mission analyse le répertoire demandé.

Aucun test n'écrit hors d'un répertoire temporaire créé et supprimé par le
test lui-même, et aucun appel à un fournisseur distant n'est effectué.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from app.orchestration.models import ExecutionLimits, MissionState
from app.orchestration.planner import (
    ClarificationRequired,
    DeterministicPlanner,
    PlanContext,
    PlanRejected,
    extract_target_path,
)
from app.orchestration.runner import MissionRunner
from app.security.paths import default_allowed_roots, project_root
from app.tools.builtin import build_default_registry
from app.tools.grants import GrantRegistry
from app.tools.service import ToolService


def _build_runner() -> tuple[MissionRunner, GrantRegistry]:
    """Construire un orchestrateur isolé (lecture seule, racines par défaut)."""
    registry = build_default_registry()
    grants = GrantRegistry()
    service = ToolService(
        registry=registry,
        granted_permissions={"lecture_systeme"},
        grant_checker=grants,
    )
    runner = MissionRunner(
        service,
        limits=ExecutionLimits(
            max_steps=6, max_attempts_per_step=2, max_duration_seconds=30.0
        ),
        grant_registry=grants,
        session_id="session-test-d2",
    )
    return runner, grants


def _plan_context() -> PlanContext:
    """Contexte de planification en lecture seule."""
    return PlanContext(
        registry=build_default_registry(),
        allowed_tool_ids=["action_workdir", "action_list_files", "action_read_file"],
    )


# ---------------------------------------------------------------------------
# 1, 2, 3, 4. Extraction : la cible déduite est celle qui a été écrite
# ---------------------------------------------------------------------------

class TestExtractionDeChemins(unittest.TestCase):
    """1-4. Chemins Windows, relatifs et POSIX."""

    def test_chemin_absolu_windows_conserve_la_lettre_de_lecteur(self) -> None:
        """1. La lettre de lecteur fait partie du chemin (défaut D2)."""
        self.assertEqual(
            extract_target_path("Analyse C:/Windows en lecture"), "C:/Windows"
        )
        self.assertEqual(
            extract_target_path(r"Analyse C:\Windows en lecture"), r"C:\Windows"
        )
        self.assertEqual(
            extract_target_path(r"Analyse D:\donnees\rapports"),
            r"D:\donnees\rapports",
        )
        self.assertEqual(
            extract_target_path(
                "Analyse C:/Users/StanC/Desktop/Milescorp/docs"
            ),
            "C:/Users/StanC/Desktop/Milescorp/docs",
        )

    def test_chemin_windows_avec_espaces_est_conserve(self) -> None:
        """2. Les espaces internes d'un chemin Windows sont conservés."""
        self.assertEqual(
            extract_target_path(r"Analyse C:\Program Files\MonDossier"),
            r"C:\Program Files\MonDossier",
        )
        self.assertEqual(
            extract_target_path(r"Analyse C:\Users\Jean\Mes Documents"),
            r"C:\Users\Jean\Mes Documents",
        )

    def test_chemin_relatif_est_conserve(self) -> None:
        """3. Les chemins relatifs ne changent pas."""
        self.assertEqual(
            extract_target_path("Analyse docs/coordination"), "docs/coordination"
        )
        self.assertEqual(extract_target_path("Analyse ./docs"), "./docs")
        self.assertEqual(extract_target_path("Analyse ../docs"), "../docs")
        self.assertEqual(
            extract_target_path(r"Analyse docs\coordination"), r"docs\coordination"
        )

    def test_chemin_posix_est_conserve(self) -> None:
        """4. Les chemins POSIX ne changent pas."""
        self.assertEqual(
            extract_target_path("Analyse /home/user/projet"), "/home/user/projet"
        )
        self.assertEqual(extract_target_path("Analyse /etc"), "/etc")

    def test_non_regression_des_comportements_existants(self) -> None:
        """5. Les comportements antérieurs sont conservés."""
        self.assertEqual(extract_target_path("Analyse docs/ en lecture"), "docs")
        self.assertEqual(extract_target_path("Analyse ce projet"), ".")
        self.assertIsNone(extract_target_path("Fais quelque chose"))
        self.assertEqual(extract_target_path("Analyse le dossier docs"), "docs")
        self.assertIsNone(extract_target_path("Analyse mon-fichier.txt"))

    def test_espaces_ne_avalent_pas_la_phrase(self) -> None:
        """Un mot de la phrase qui suit n'est pas assimilé au chemin."""
        self.assertEqual(
            extract_target_path("Analyse docs/ identifie son organisation"), "docs"
        )
        self.assertEqual(
            extract_target_path("Analyse C:/Windows en lecture seule"), "C:/Windows"
        )

    def test_ambiguite_exige_une_clarification(self) -> None:
        """Deux cibles distinctes ne sont pas arbitrées : clarification."""
        self.assertIsNone(
            extract_target_path("Compare docs/ et app/ sans rien modifier")
        )

    def test_lecteur_seule_ne_designe_aucun_dossier(self) -> None:
        """« C: » seul ne désigne pas un dossier."""
        self.assertIsNone(extract_target_path("Analyse C:"))
        self.assertIsNone(extract_target_path("Analyse C:\\"))

    def test_marqueur_ne_capture_qu_un_prefixe_de_chemin(self) -> None:
        """« dossier C:/Windows » désigne le chemin, pas le préfixe « C »."""
        self.assertEqual(
            extract_target_path("Analyse le dossier C:/Windows"), "C:/Windows"
        )
        self.assertEqual(
            extract_target_path("Analyse le dossier docs/coordination"),
            "docs/coordination",
        )

    def test_entrees_malformees_ne_donnent_aucun_chemin(self) -> None:
        """Les entrées sans séparateur ne sont jamais des chemins."""
        for objectif in (
            "Analyse C",
            "Analyse :",
            "Analyse /",
            "Analyse le fichier rapport.txt",
        ):
            with self.subTest(objectif=objectif):
                self.assertIsNone(extract_target_path(objectif))

    def test_chemin_entre_guillemets_est_cible(self) -> None:
        """Un chemin entre guillemets est pris tel quel (espaces compris)."""
        cible = r"C:\Users\Jean\Mes Documents"
        self.assertEqual(
            extract_target_path(f'Analyse "{cible}" en lecture seule'), cible
        )
        self.assertEqual(
            extract_target_path(f"Analyse « {cible} » en lecture seule"), cible
        )


# ---------------------------------------------------------------------------
# 6. Le confinement n'est pas affaibli
# ---------------------------------------------------------------------------

class TestConfinementDesChemins(unittest.TestCase):
    """6. Les protections contre les chemins interdits restent actives."""

    def setUp(self) -> None:
        self. racine = str(project_root())

    def _chemin_hors_perimetre(self) -> str:
        """Un chemin absolu hors des racines autorisées, valide pour la plateforme."""
        if os.name == "nt":
            return os.path.join(os.path.abspath(os.sep), "Windows", "System32")
        return "/Windows/System32"

    def test_chemin_windows_hors_perimetre_refuse(self) -> None:
        """6a. Un chemin Windows hors périmètre est refusé par le planificateur."""
        planner = DeterministicPlanner()
        cible = self._chemin_hors_perimetre()
        with self.assertRaises(PlanRejected) as ctx:
            planner.plan(f"Analyse {cible} en lecture", _plan_context())
        self.assertIn("hors", str(ctx.exception).lower())

    def test_chemin_windows_avec_espaces_hors_perimetre_refuse(self) -> None:
        """6b. Un chemin Windows avec espaces hors périmètre est refusé."""
        planner = DeterministicPlanner()
        cible = self._chemin_hors_perimetre() + " Program Files"
        with self.assertRaises(PlanRejected):
            planner.plan(f"Analyse {cible} en lecture", _plan_context())

    def test_traversee_de_repertoires_refusee(self) -> None:
        """6c. « ../ » sort du répertoire autorisé : refus."""
        planner = DeterministicPlanner()
        with self.assertRaises(PlanRejected):
            planner.plan("Analyse ../ en lecture", _plan_context())
        with self.assertRaises(PlanRejected):
            planner.plan("Analyse ../../etc en lecture", _plan_context())

    def test_les_racines_autorisees_ne_sont_pas_elargies(self) -> None:
        """6d. Les racines autorisées sont celles du projet et de ses données."""
        racines = {str(r) for r in default_allowed_roots()}
        self.assertEqual(
            racines,
            {str(project_root()), str(project_root() / "data")},
        )

    def test_entree_malformee_refusee(self) -> None:
        """6e. Une entrée malformée ne produit aucun plan exploitable."""
        planner = DeterministicPlanner()
        with self.assertRaises((PlanRejected, ClarificationRequired)):
            planner.plan("Analyse C: en lecture", _plan_context())

    def test_mission_avec_chemin_hors_perimetre_echoue(self) -> None:
        """6f. La mission elle-même refuse un chemin hors périmètre."""
        runner, _ = _build_runner()
        mission = runner.create(
            f"Analyse {self._chemin_hors_perimetre()} en lecture"
        )
        mission = runner.run(mission.mission_id)
        self.assertIn(
            mission.state, (MissionState.FAILED, MissionState.NEEDS_CLARIFICATION)
        )
        if mission.state == MissionState.FAILED:
            self.assertTrue(any("hors" in e.lower() for e in mission.errors))


# ---------------------------------------------------------------------------
# 7. De bout en bout : la mission analyse le répertoire demandé
# ---------------------------------------------------------------------------

class TestMissionAvecCheminWindows(unittest.TestCase):
    """7. La cible demandée est bien celle qui est analysée."""

    def setUp(self) -> None:
        self._racine_temp = tempfile.mkdtemp(
            prefix="d2-", dir=str(project_root())
        )
        self.addCleanup(shutil.rmtree, self._racine_temp, True)

    def test_chemin_absolu_du_projet_est_cible(self) -> None:
        """7a. Le chemin absolu du projet (avec sa lettre de lecteur) est ciblé."""
        cible = str(project_root())
        self.assertEqual(
            extract_target_path(f"Analyse {cible} en lecture"), cible
        )

    def test_dossier_avec_espace_analyse(self) -> None:
        """7b. Un dossier dont le nom contient un espace est bien analysé.

        Deux écritures sont acceptées : entre guillemets (forme non
        ambiguë) et avec un nom capitalisé (forme usuelle de Windows).
        """
        dossier = os.path.join(self._racine_temp, "Dossier Avec Espace")
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, "note.txt"), "w", encoding="utf-8") as fh:
            fh.write("contenu de test\n")

        for objectif in (
            f'Analyse "{dossier}" en lecture seule',
            f"Analyse {dossier} en lecture seule",
        ):
            with self.subTest(objectif=objectif):
                self.assertEqual(extract_target_path(objectif), dossier)

                planner = DeterministicPlanner()
                plan = planner.plan(objectif, _plan_context())
                etapes = [s for s in plan.steps if s.tool_id == "action_list_files"]
                self.assertTrue(etapes)
                self.assertEqual(etapes[0].parameters["path"], str(dossier))

    def test_mission_conserve_la_cible_demandee(self) -> None:
        """7c. La mission retient le chemin demandé, lettre de lecteur comprise."""
        runner, _ = _build_runner()
        cible = str(project_root())
        mission = runner.create(f"Analyse {cible} en lecture seule")
        self.assertEqual(mission.target_path, cible)

    def test_mission_avec_chemin_windows_externe_echoue(self) -> None:
        """7d. Un chemin Windows externe n'est jamais analysé."""
        runner, _ = _build_runner()
        mission = runner.create("Analyse C:/Windows/System32 en lecture")
        mission = runner.run(mission.mission_id)
        self.assertIn(
            mission.state, (MissionState.FAILED, MissionState.NEEDS_CLARIFICATION)
        )
        if mission.state == MissionState.FAILED:
            self.assertTrue(any("hors" in e.lower() for e in mission.errors))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
