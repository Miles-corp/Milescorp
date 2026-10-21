"""Tests de régression du défaut D-B05 (persistance) et D-B01 (chemins).

**D-B05 — persistance des missions.**

Constat de l'audit contradictoire d'Agent B
(`docs/reports/AUDIT_MILES_PHASE5_6_61_AGENT_B.md`) : « `list_missions`
ignore la base ». Vérification sur la base de travail : la méthode
`MissionRunner.list_missions` ne listait que les missions **en mémoire** ;
les missions persistées étaient invisibles dans la liste (CLI et web) après
un redémarrage.

Constat complémentaire, trouvé en examinant D-B05 : le **propriétaire**
(`Mission.owner_user_id`) était sérialisé par le modèle mais **jamais
écrit** par le magasin : au rechargement d'une mission, son propriétaire
était perdu. La séparation entre utilisateurs de l'interface web (qui repose
sur ce propriétaire) ne tenait donc plus pour les missions rechargées.

**D-B01 — chemins légitimes contenant « code ».**

L'audit d'Agent B signale que la politique de sécurité refuse un chemin
légitime dont le nom contient « code » (par exemple un dépôt placé dans
`...\\opencode\\Milescorp`), et demande un test de non-régression nommé
`test_chemin_legitime_contenant_code_accepte`. Le correctif de typage
explicite (branche `fix/miles-policy-path-typing`) declare les paramètres de
type chemin dans le schéma des outils ; ce test **vérifie ce correctif sans
dépendre de l'emplacement du dépôt**.

Les tests sont non destructifs : bases temporaires, outils simulés, aucune
donnée réelle lue ni écrite.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from typing import List

from app.orchestration.models import ExecutionLimits
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore
from app.tools.builtin import build_default_registry
from app.tools.grants import GrantRegistry
from app.tools.policy import ToolPolicy
from app.tools.service import ToolService


def _build_runner(store: MissionStore) -> MissionRunner:
    """Construire un orchestrateur isolé, adossé à un magasin donné."""
    grants = GrantRegistry()
    service = ToolService(
        registry=build_default_registry(),
        granted_permissions={"lecture_systeme"},
        grant_checker=grants,
    )
    return MissionRunner(
        service,
        store=store,
        limits=ExecutionLimits(
            max_steps=4,
            max_attempts_per_step=1,
            max_duration_seconds=30.0,
            max_tool_calls=8,
            max_interactions=2,
        ),
        grant_registry=grants,
        session_id="session-application",
        allowed_tool_ids=["action_datetime", "action_workdir"],
    )


class TestPersistanceDesMissions(unittest.TestCase):
    """D-B05 : la liste des missions inclut la base, le propriétaire survit."""

    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="db05-")
        self.addCleanup(shutil.rmtree, self._dossier, True)
        self.chemin = os.path.join(self._dossier, "missions.db")
        self.store = MissionStore(enabled=True, db_path=self.chemin)
        self.runner = _build_runner(self.store)

    def test_le_proprietaire_est_persiste(self) -> None:
        """1. Le propriétaire d'une mission survit au rechargement."""
        mission = self.runner.create(
            "Analyse de test", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.assertTrue(self.store.save(mission))
        self.assertTrue(self.store.is_available)

        rechargée = self.store.load(mission.mission_id)
        self.assertIsNotNone(rechargée)
        self.assertEqual(rechargée.owner_user_id, "alice")
        self.assertEqual(rechargée.session_id, "s-alice")

    def test_la_liste_inclut_les_missions_persistees(self) -> None:
        """2. Une mission enregistrée puis rechargée apparaît dans la liste."""
        mission = self.runner.create(
            "Analyse persistee", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.store.save(mission)

        # Nouveau runner sur la même base : la mission n'est plus en mémoire.
        autre = _build_runner(MissionStore(enabled=True, db_path=self.chemin))
        liste = autre.list_missions()
        identifiants = [e["mission_id"] for e in liste]
        self.assertIn(mission.mission_id, identifiants)
        entree = next(e for e in liste if e["mission_id"] == mission.mission_id)
        self.assertEqual(entree["objective"], "Analyse persistee")

    def test_la_liste_ne_melange_pas_les_utilisateurs(self) -> None:
        """3. La liste filtrée ne montre que les missions de son utilisateur."""
        alice = self.runner.create(
            "Mission de alice", owner_user_id="alice", owner_session_id="s-alice"
        )
        bob = self.runner.create(
            "Mission de bob", owner_user_id="bob", owner_session_id="s-bob"
        )
        self.store.save(alice)
        self.store.save(bob)

        autre = _build_runner(MissionStore(enabled=True, db_path=self.chemin))
        liste_alice = autre.list_missions(owner_user_id="alice")
        identifiants = [e["mission_id"] for e in liste_alice]
        self.assertIn(alice.mission_id, identifiants)
        self.assertNotIn(bob.mission_id, identifiants)

        liste_bob = autre.list_missions(owner_user_id="bob")
        identifiants_bob = [e["mission_id"] for e in liste_bob]
        self.assertIn(bob.mission_id, identifiants_bob)
        self.assertNotIn(alice.mission_id, identifiants_bob)

    def test_une_mission_n_est_pas_listee_deux_fois(self) -> None:
        """4. Une mission présente en mémoire et en base n'est listée qu'une fois."""
        mission = self.runner.create(
            "Mission en cours", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.store.save(mission)
        liste = self.runner.list_missions(owner_user_id="alice")
        occurrences = [
            e["mission_id"] for e in liste if e["mission_id"] == mission.mission_id
        ]
        self.assertEqual(len(occurrences), 1)

    def test_la_liste_est_triee_du_plus_recent_au_plus_ancien(self) -> None:
        """5. La liste combinee reste triée par date de création décroissante."""
        premiere = self.runner.create(
            "Mission ancienne", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.store.save(premiere)
        seconde = self.runner.create(
            "Mission recente", owner_user_id="alice", owner_session_id="s-alice"
        )
        self.store.save(seconde)
        liste = self.runner.list_missions(owner_user_id="alice")
        dates = [e["created_at"] for e in liste]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_la_liste_respecte_la_limite(self) -> None:
        """6. La limite de taille est respectée."""
        for index in range(5):
            mission = self.runner.create(
                f"Mission {index}", owner_user_id="alice", owner_session_id="s"
            )
            self.store.save(mission)
        self.assertLessEqual(len(self.runner.list_missions(limit=2)), 2)

    def test_une_base_ancienne_sans_proprietaire_reste_lisible(self) -> None:
        """7. Une base créée avant la migration reste lisible.

        Les missions dont le propriétaire est inconnu ne sont pas proposées
        dans une liste filtrée (séparation entre utilisateurs) mais restent
        visibles dans la liste non filtrée.
        """
        store = MissionStore(enabled=True, db_path=self.chemin)
        self.assertTrue(store.is_available)
        # Une mission enregistrée sans propriétaire (héritage d'une base
        # antérieure à la migration).
        mission = self.runner.create("Mission sans proprietaire")
        self.store.save(mission)
        self.assertEqual(
            self.store.load(mission.mission_id).owner_user_id, ""
        )
        liste_filtree = self.runner.list_missions(owner_user_id="alice")
        self.assertNotIn(
            mission.mission_id, [e["mission_id"] for e in liste_filtree]
        )
        liste_non_filtree = self.runner.list_missions()
        self.assertIn(
            mission.mission_id, [e["mission_id"] for e in liste_non_filtree]
        )


class TestCheminsLegitimesContenantCode(unittest.TestCase):
    """D-B01 : un chemin légitime contenant « code » est accepté."""

    def test_chemin_legitime_contenant_code_accepte(self) -> None:
        """Test de non-régression demandé par l'audit d'Agent B (D-B01).

        Un chemin de fichier n'est pas une commande : la politique de
        sécurité ne doit pas le refuser parce qu'il contient « code »,
        « source », « script » ou « python ».
        """
        registre = build_default_registry()
        chemins = {
            param.name
            for tool_id in registre.list_tools()
            for param in registre.get_tool(tool_id).parameters
            if param.is_path
        }
        self.assertIn("path", chemins)

        politique = ToolPolicy({"lecture_systeme"})
        for chemin in (
            r"C:\Users\X\opencode\Milescorp\docs",
            r"C:\dev\source\projet",
            r"C:\Users\X\Documents\code",
            r"C:\Python39\Lib",
            "/home/x/opencode/Milescorp/docs",
        ):
            with self.subTest(chemin=chemin):
                politique.validate_no_code_execution(
                    {"path": chemin}, path_parameters=chemins
                )
                politique.validate_no_shell_access(
                    {"path": chemin}, path_parameters=chemins
                )
                politique.validate_no_secret_access(
                    {"path": chemin}, path_parameters=chemins
                )

    def test_une_valeur_libre_contenant_code_reste_refusee(self) -> None:
        """Le correctif D-B01 n'affaiblit pas le contrôle des valeurs libres."""
        registre = build_default_registry()
        chemins = {
            param.name
            for tool_id in registre.list_tools()
            for param in registre.get_tool(tool_id).parameters
            if param.is_path
        }
        politique = ToolPolicy({"lecture_systeme"})
        with self.assertRaises(PermissionError):
            politique.validate_no_code_execution(
                {"message": "source"}, path_parameters=chemins
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
