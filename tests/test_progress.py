"""Tests des messages d'attente honnêtes (Q2) — aucun réseau, module pur.

Invariants :
- chaque phrase correspond à un ÉTAT RÉEL de mission (aucune invention) ;
- un état d'échec ne produit JAMAIS un message de succès ;
- aucune étape n'est annoncée terminée si elle ne l'est pas ;
- variété des formulations (deux variantes distinctes pour un événement) ;
- aucun secret dans les messages (titres expurgés).
"""

from __future__ import annotations

import unittest

from app.orchestration.models import (
    Mission,
    MissionState,
    PendingRequest,
    Plan,
    PlanStep,
    StepStatus,
)
from app.orchestration.progress import PHRASES, evenement, message_attente


def _mission(
    state: MissionState = MissionState.RUNNING,
    statuts: tuple = (),
    pending: PendingRequest | None = None,
    errors: tuple = (),
    unfinished: tuple = (),
) -> Mission:
    steps = [
        PlanStep(step_id=f"s{i}", objective=f"Etape {i}", tool_id="outil_test", status=st)
        for i, st in enumerate(statuts)
    ]
    plan = Plan(mission_id="m1", steps=steps, planner="test") if steps else None
    return Mission(
        mission_id="m1",
        objective="mission de test",
        state=state,
        plan=plan,
        pending=pending,
        errors=list(errors),
        unfinished=list(unfinished),
    )


class TestEvenementsReels(unittest.TestCase):
    def test_etape_en_cours_decompte_depuis_le_plan(self) -> None:
        m = _mission(
            MissionState.RUNNING,
            (StepStatus.SUCCEEDED, StepStatus.RUNNING, StepStatus.PENDING),
        )
        ev = evenement(m)
        self.assertEqual(ev["type"], "etape_en_cours")
        self.assertEqual((ev["index"], ev["total"]), (2, 3))

    def test_aucune_etape_annoncee_terminee_si_echec(self) -> None:
        # Étape 1 échouée, étape 2 en cours : le décompte ne doit compter
        # que l'étape SUCCEEDED, jamais celle qui a échoué.
        m = _mission(
            MissionState.RUNNING,
            (StepStatus.FAILED, StepStatus.RUNNING, StepStatus.PENDING),
        )
        ev = evenement(m)
        self.assertEqual(ev["type"], "etape_en_cours")
        self.assertEqual(ev["index"], 2)  # la FAILED n'est pas « en cours »
        msg = message_attente(m, 0)
        self.assertIn("2/3", msg)

    def test_etat_echec_ne_produit_jamais_de_succes(self) -> None:
        m = _mission(MissionState.FAILED, (StepStatus.SUCCEEDED, StepStatus.FAILED),
                     errors=["erreur reelle"])
        for variante in range(len(PHRASES["echec"]) * 2):
            msg = message_attente(m, variante)
            self.assertIsNotNone(msg)
            self.assertNotIn("Mission terminée", msg)
            self.assertNotIn("2/2", msg)  # jamais « tout est réussi » sur un échec
        self.assertIn("échec", message_attente(m, 0))
        self.assertIn("1 erreur", message_attente(m, 0))

    def test_succes_seulement_si_reellement_terminee(self) -> None:
        m = _mission(MissionState.COMPLETED, (StepStatus.SUCCEEDED, StepStatus.SUCCEEDED))
        self.assertEqual(evenement(m)["type"], "terminee")
        self.assertIn("2/2", message_attente(m, 0))
        part = _mission(MissionState.PARTIAL, (StepStatus.SUCCEEDED, StepStatus.FAILED),
                        unfinished=["s2"])
        self.assertEqual(evenement(part)["type"], "terminee_partielle")
        self.assertIn("partiellement", message_attente(part, 0))

    def test_demandes_en_attente(self) -> None:
        clar = _mission(MissionState.NEEDS_CLARIFICATION,
                        pending=PendingRequest(kind="clarification", question="?"))
        self.assertIn("précision", message_attente(clar, 0))
        auth = _mission(MissionState.AWAITING_AUTHORIZATION,
                        pending=PendingRequest(kind="authorization", question="?"))
        self.assertIn("Autorisation", message_attente(auth, 0))

    def test_variation_des_formulations(self) -> None:
        m = _mission(MissionState.RUNNING, (StepStatus.SUCCEEDED, StepStatus.RUNNING))
        msg0 = message_attente(m, 0)
        msg1 = message_attente(m, 1)
        self.assertNotEqual(msg0, msg1)
        # même événement : les deux formulations parlent bien de l'étape 2 sur 2
        self.assertIn("2/2", msg0)          # « Étape 2/2 : … »
        self.assertIn("étape 2 sur 2", msg1)  # « … étape 2 sur 2 : … »

    def test_aucun_secret_dans_le_message(self) -> None:
        m = _mission(MissionState.RUNNING)
        steps = [PlanStep("s0", "Lire la cle sk-abc123456789 depuis la config",
                          "outil_test", status=StepStatus.RUNNING)]
        m.plan = Plan(mission_id="m1", steps=steps, planner="test")
        msg = message_attente(m, 0)
        self.assertIsNotNone(msg)
        self.assertNotIn("sk-abc123456789", msg)
        self.assertIn("[REDACTED]", msg)

    def test_aucun_evenement_pour_rien_a_raconter(self) -> None:
        self.assertIsNone(message_attente(_mission(MissionState.CREATED), 0))
        self.assertIsNone(evenement(_mission(MissionState.CREATED)))

    def test_phrase_indisponible_ne_crache_jamais(self) -> None:
        # Garde interne : format avec champ manquant = message neutre, pas de crash.
        m = _mission(MissionState.RUNNING, (StepStatus.RUNNING,))
        self.assertIsNotNone(message_attente(m, 0))


if __name__ == "__main__":
    unittest.main()
