"""Invariant P1 : seule la route d'autorisation peut approuver une action.

Après la correction P1, l'approbation d'une autorisation de mission
n'est possible que par `POST /mission/<id>/authorize`, avec le jeton
d'approbation de la demande (usage unique, expiration, session,
propriétaire).

Cet invariant est vérifié de bout en bout :

- aucune réponse textuelle, par aucune des routes ni par l'API interne de
  l'orchestrateur, ne peut approuver l'action sensible ;
- aucune variante du jeton (absent, invalide, d'une autre mission, d'une
  autre session) ne peut approuver l'action ;
- l'outil sensible n'est exécuté qu'après une approbation valide ;
- l'approbation valide émet un grant **unique**, lié à la session et à la
  mission.

Les tests sont déterministes (outils simulés, aucun fournisseur, aucune
donnée réelle).
"""

from __future__ import annotations

import time
import unittest
from typing import Any, List, Optional, Tuple

from app.config.settings import Settings
from app.interface.web import WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore
from app.orchestration.models import ExecutionLimits, Plan, PlanStep
from app.orchestration.planner import PlanContext
from app.orchestration.runner import MissionAuthorizationError, MissionRunner
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService

#: Session de l'APPLICATION (celle du runner) : distincte de celle du client.
SESSION_APPLICATION = "session-application"

#: Jetons d'accès des clients de test.
JETON_ALICE = "jeton-alice-0123456789"
JETON_BOB = "jeton-bob-0123456789"

#: Toutes les réponses textuelles qui signifient « oui » dans l'interface.
MOTS_APPROBATION = ("o", "oui", "y", "yes", "ok", "autorise", "O", "Oui")


def _ok_handler(value: str = "ok") -> str:
    """Handler qui réussit toujours."""
    return value


def _sensible_handler() -> str:
    """Handler de risque MEDIUM : exige une autorisation."""
    return "sensible"


def _make_tool(
    tool_id: str,
    handler: Any,
    *,
    risk: str = "LOW",
    permissions: Tuple[str, ...] = (),
) -> ToolDefinition:
    """Construire une définition d'outil pour les tests."""
    return ToolDefinition(
        tool_id=tool_id,
        description="Outil de test " + tool_id,
        handler=handler,
        parameters=(),
        risk_level=risk,
        required_permissions=permissions,
        timeout_seconds=15,
    )


class _PlanFixe:
    """Planificateur de test : un outil sensible puis un outil simple."""

    name = "test"
    note = "plan de test fixe"

    def plan(self, objective: str, context: PlanContext) -> Plan:
        return Plan(
            mission_id=context.mission_id,
            steps=[
                PlanStep("s1", "Outil sensible", "outil_sensible"),
                PlanStep("s2", "Outil simple", "outil_ok"),
            ],
            planner="test",
        )


def _build_app() -> Tuple[WebApp, MissionRunner, GrantRegistry, WebAuthenticator]:
    """Construire une application web avec un runner de session distincte."""
    registry = ToolRegistry()
    registry.register(_make_tool("outil_ok", _ok_handler))
    registry.register(
        _make_tool(
            "outil_sensible",
            _sensible_handler,
            risk="MEDIUM",
            permissions=("lecture_systeme",),
        )
    )
    grants = GrantRegistry()
    service = ToolService(
        registry=registry,
        granted_permissions={"lecture_systeme"},
        grant_checker=grants,
    )
    runner = MissionRunner(
        service,
        planner=_PlanFixe(),
        limits=ExecutionLimits(
            max_steps=6,
            max_attempts_per_step=1,
            max_duration_seconds=60.0,
            max_tool_calls=12,
            max_interactions=3,
            max_identical_results=99,
        ),
        grant_registry=grants,
        session_id=SESSION_APPLICATION,
        allowed_tool_ids=["outil_ok", "outil_sensible"],
    )
    authenticator = WebAuthenticator(
        WebCredentialStore({"alice": JETON_ALICE, "bob": JETON_BOB})
    )
    app = WebApp(
        settings=Settings(),
        tool_service=service,
        mission_runner=runner,
        authenticator=authenticator,
    )
    return app, runner, grants, authenticator


class TestInvariantApprobationExigeLeJeton(unittest.TestCase):
    """Invariant : seule `/authorize` avec un jeton valide approuve."""

    def setUp(self) -> None:
        self.app, self.runner, self.grants, self.authenticator = _build_app()
        self.session = self.authenticator.login(JETON_ALICE)

    def _mission_en_attente(self, suffixe: str = "") -> Tuple[str, str]:
        """Créer une mission et attendre sa demande d'autorisation."""
        payload = self.app.create_mission("Analyse de test" + suffixe, self.session)
        mission_id = payload["mission_id"]
        limite = time.time() + 20
        detail: dict = {}
        while time.time() < limite:
            detail = self.app.mission_detail(mission_id, self.session)
            if detail.get("state") == "awaiting_authorization":
                break
            time.sleep(0.05)
        self.assertEqual(detail.get("state"), "awaiting_authorization")
        pending = detail.get("pending") or {}
        return mission_id, str(pending.get("approval_token"))

    def _aucune_action_sensible(self, mission_id: str) -> None:
        """Vérifier qu'aucune action sensible n'a été exécutée."""
        time.sleep(0.2)
        mission = self.runner.get(mission_id)
        self.assertEqual(
            mission.state.value,
            "awaiting_authorization",
            "la mission a ete approuvee sans autorisation valide",
        )
        self.assertEqual(self.grants.list_grants(), [])
        etapes = mission.plan.steps if mission.plan else []
        for etape in etapes:
            self.assertNotEqual(etape.status.value, "succeeded")

    def test_aucune_reponse_textuelle_n_approuve(self) -> None:
        """1. Aucun mot d'approbation, par `/answer`, n'approuve l'action."""
        for index, mot in enumerate(MOTS_APPROBATION):
            with self.subTest(mot=mot):
                mission_id, _ = self._mission_en_attente(f" {index}")
                reponse = self.app.answer_mission(
                    mission_id, {"answer": mot}, self.session
                )
                self.assertIn("error", reponse)
                self.assertNotIn("answered", reponse)
                self._aucune_action_sensible(mission_id)

    def test_l_api_interne_de_l_orchestrateur_n_approuve_pas(self) -> None:
        """2. L'API interne (`MissionRunner.answer`) n'approuve pas non
        plus : elle refuse explicitement."""
        mission_id, _ = self._mission_en_attente()
        with self.assertRaises(MissionAuthorizationError):
            self.runner.answer(mission_id, "o", requester_user_id="alice")
        self._aucune_action_sensible(mission_id)

    def test_une_autorisation_sans_jeton_valide_est_refusee(self) -> None:
        """3. `/authorize` sans jeton valide n'approuve pas."""
        for jeton in (None, "", "jeton-invalide", 123):
            with self.subTest(jeton=jeton):
                mission_id, _ = self._mission_en_attente(f" {jeton}")
                reponse = self.app.authorize_mission(
                    mission_id, {"approved": True, "approval_token": jeton},
                    self.session,
                )
                self.assertIn("error", reponse)
                self._aucune_action_sensible(mission_id)

    def test_le_jeton_dune_autre_mission_est_refuse(self) -> None:
        """4. Le jeton d'une autre mission est refusé (usage unique)."""
        mission_id, _ = self._mission_en_attente(" A")
        _, autre_jeton = self._mission_en_attente(" B")
        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": autre_jeton},
            self.session,
        )
        self.assertIn("error", reponse)
        self._aucune_action_sensible(mission_id)

    def test_le_jeton_dune_autre_session_est_refuse(self) -> None:
        """5. Le jeton d'une autre session est refusé."""
        mission_id, jeton = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": jeton}, autre_session
        )
        self.assertIn("error", reponse)
        self._aucune_action_sensible(mission_id)

    def test_le_jeton_dautre_utilisateur_est_refuse(self) -> None:
        """6. Un autre utilisateur ne peut pas approuver."""
        mission_id, jeton = self._mission_en_attente()
        session_bob = self.authenticator.login(JETON_BOB)
        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": jeton}, session_bob
        )
        self.assertIn("error", reponse)
        self._aucune_action_sensible(mission_id)

    def test_une_autorisation_valide_approuve_et_execute(self) -> None:
        """7. Avec un jeton valide, l'action est approuvée puis exécutée."""
        mission_id, jeton = self._mission_en_attente()
        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": jeton}, self.session
        )
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("approved"), True)

        limite = time.time() + 20
        detail: dict = {}
        while time.time() < limite:
            detail = self.app.mission_detail(mission_id, self.session)
            if detail.get("state") in (
                "completed", "partial", "failed", "limit_reached"
            ):
                break
            time.sleep(0.05)
        self.assertIn(detail.get("state"), ("completed", "partial"))
        mission = self.runner.get(mission_id)
        etats = {
            s.step_id: s.status.value for s in (mission.plan.steps if mission.plan else [])
        }
        self.assertEqual(etats.get("s1"), "succeeded")
        grants = self.grants.list_grants()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].session_id, self.session.session_id)
        self.assertEqual(grants[0].mission_id, mission_id)

    def test_le_jeton_ne_sert_qu_une_seule_fois(self) -> None:
        """8. Le jeton est à usage unique : une seconde présentation est
        refusée."""
        mission_id, jeton = self._mission_en_attente()
        premier = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": jeton}, self.session
        )
        self.assertNotIn("error", premier)
        second = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": jeton}, self.session
        )
        self.assertIn("error", second)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
