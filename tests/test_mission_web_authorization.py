"""Tests de régression du défaut D1 : autorisation d'une mission depuis l'interface web.

DÉFAUT D1 (constaté par la campagne de validation, §4 du rapport
``PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md``) :

    Le grant d'autorisation est ÉMIS pour la session du client qui a
    demandé l'autorisation (``runner.authorize`` ->
    ``session_id=requester_session_id or mission.session_id``), mais il était
    VÉRIFIÉ avec la session de l'APPLICATION (``_ensure_authorization`` ->
    ``self.session_id``).

    Or, dans l'interface web, ces deux sessions diffèrent : l'application a
    une session par processus, chaque client web a la sienne. Le grant
    légitime était donc refusé, une nouvelle demande d'autorisation était
    levée, et la mission ne pouvait pas aboutir (jusqu'à l'épuisement du
    budget d'échanges).

    Le correctif consiste à vérifier le grant avec la session du client
    PROPRIÉTAIRE de la mission (``mission.session_id``), comme le fait
    déjà l'exécuteur pour les jetons de confirmation des outils.

Ces tests exercent le vrai chemin web : ``WebApp.create_mission`` puis
``WebApp.authorize_mission``.
"""

from __future__ import annotations

import time
import unittest
from typing import Any, List, Optional, Tuple

from app.config.settings import Settings
from app.interface.web import WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore, WebSession
from app.orchestration.models import ExecutionLimits, Plan, PlanStep
from app.orchestration.planner import PlanContext
from app.orchestration.runner import MissionRunner
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService

#: Session de l'APPLICATION (celle du runner) : distincte de celle du client.
SESSION_APPLICATION = "session-application"

#: Jetons d'accès des clients de test.
JETON_ALICE = "jeton-alice-0123456789"
JETON_BOB = "jeton-bob-0123456789"


def _ok_handler(value: str = "ok") -> str:
    """Handler qui réussit toujours (niveau module : picklable)."""
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
    """Planificateur de test : renvoie toujours le même plan.

    Le planificateur déterministe de production utilise les outils réels
    (action_workdir, action_list_files, …) : il ne peut pas servir ici,
    où l'on veut un plan composé d'outils de test.
    """

    name = "test"
    note = "plan de test fixe"

    def __init__(self, steps: List[PlanStep]) -> None:
        self._steps = steps

    def plan(self, objective: str, context: PlanContext) -> Plan:
        plan = Plan(
            mission_id=context.mission_id,
            steps=[
                PlanStep(
                    step_id=step.step_id,
                    objective=step.objective,
                    tool_id=step.tool_id,
                    parameters=dict(step.parameters),
                )
                for step in self._steps
            ],
            planner=self.name,
        )
        plan.note = self.note
        return plan


def _build_app() -> Tuple[WebApp, MissionRunner, GrantRegistry, WebAuthenticator]:
    """Construire une application web avec un runner de session distincte.

    La session du runner est celle de l'application ; la session du client web
    est créée par l'authentificateur : les deux diffèrent, comme en
    production (c'est exactement le cas que le défaut D1 ne couvrait pas).
    """
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
        planner=_PlanFixe(
            [
                PlanStep("s1", "Outil sensible", "outil_sensible"),
                PlanStep("s2", "Outil simple", "outil_ok"),
            ]
        ),
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


def _attendre_etat(
    app: WebApp,
    mission_id: str,
    session: WebSession,
    etats: Tuple[str, ...],
    delai: float = 20.0,
) -> dict[str, Any]:
    """Attendre que la mission atteigne l'un des états donnés."""
    limite = time.time() + delai
    detail: dict[str, Any] = {}
    while time.time() < limite:
        detail = app.mission_detail(mission_id, session)
        if detail.get("state") in etats:
            return detail
        time.sleep(0.1)
    return detail


class TestD1WebAuthorization(unittest.TestCase):
    """Régression D1 : l'autorisation web doit être prise en compte."""

    def setUp(self) -> None:
        self.app, self.runner, self.grants, self.authenticator = _build_app()
        self.session = self.authenticator.login(JETON_ALICE)

    def test_session_client_differente_de_la_session_application(self) -> None:
        """Pré-condition du défaut : les deux sessions sont distinctes."""
        self.assertNotEqual(self.session.session_id, SESSION_APPLICATION)

    def test_mission_web_autorisee_se_termine(self) -> None:
        """D1 (régression) : une mission web autorisée doit CONTINUER et
        se terminer, au lieu de redemander une autorisation.

        Avant le correctif : la mission restait en ``awaiting_authorization``
        et le compteur d'échanges augmentait à chaque tour.
        """
        payload = self.app.create_mission("Analyse de test", self.session)
        mission_id = payload["mission_id"]

        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")
        pending = attente.get("pending") or {}
        self.assertTrue(pending)
        self.assertEqual(pending.get("kind"), "authorization")

        reponse = self.app.authorize_mission(
            mission_id,
            {"approved": True, "approval_token": pending.get("approval_token")},
            self.session,
        )
        self.assertEqual(reponse.get("approved"), True)

        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        self.assertIn(
            final.get("state"),
            ("completed", "partial"),
            "la mission n'a pas continué après l'autorisation : "
            f"etat={final.get('state')} budget={final.get('budget')}",
        )
        budget = final.get("budget") or {}
        # Une seule demande d'autorisation : le défaut D1 en déclenchait une
        # nouvelle demande à chaque tour.
        self.assertEqual(budget.get("interactions"), 1)
        self.assertEqual(budget.get("steps_executed"), 2)

    def test_mission_web_sans_autorisation_valide_ne_continue_pas(self) -> None:
        """Sans jeton d'approbation valide, la mission NE DOIT PAS continuer.

        Ce qui est vérifié ici est la PROPRIÉTÉ DE SÉCURITÉ : la mission
        reste en attente, l'étape sensible n'est pas exécutée et aucun
        grant n'est émis.

        NOTE (défaut D1-bis, signalé, non corrigé dans cette mission) :
        l'endpoint renvoie malgré tout ``started: True``, car la validation
        du jeton d'approbation a lieu dans le FIL d'exécution, dont
        l'exception est journalisée et non retournée au client. L'autorisation
        n'est PAS accordée pour autant : le comportement de sécurité est
        correct, la réponse HTTP est trompeuse.
        """
        payload = self.app.create_mission("Analyse de test", self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")

        # Jeton d'approbation FABRIQUÉ
        self.app.authorize_mission(
            mission_id,
            {"approved": True, "approval_token": "jeton-fabrique" * 4},
            self.session,
        )
        # Jeton d'approbation ABSENT
        self.app.authorize_mission(
            mission_id, {"approved": True}, self.session
        )

        detail = self.app.mission_detail(mission_id, self.session)
        # La mission n'a PAS continué.
        self.assertEqual(detail.get("state"), "awaiting_authorization")
        # Aucune étape n'a été exécutée : la première est sensible, elle
        # attend l'autorisation.
        self.assertEqual((detail.get("budget") or {}).get("steps_executed"), 0)
        # Et le grant n'a pas été émis.
        self.assertEqual(len(self.grants.list_grants()), 0)

    def test_autorisation_non_reutilisable_par_une_autre_session(self) -> None:
        """Le grant émis pour une session n'est pas utilisable par une autre."""
        payload = self.app.create_mission("Analyse de test", self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        pending = attente.get("pending") or {}
        self.app.authorize_mission(
            mission_id,
            {"approved": True, "approval_token": pending.get("approval_token")},
            self.session,
        )
        _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )

        grants_actifs = self.grants.list_grants()
        self.assertTrue(grants_actifs, "un grant doit avoir été émis")
        for grant in grants_actifs:
            self.assertEqual(grant.session_id, self.session.session_id)
            self.assertEqual(grant.mission_id, mission_id)

        # Le même grant, présenté depuis la session d'un AUTRE client, est
        # refusé.
        session_bob = self.authenticator.login(JETON_BOB)
        self.assertNotEqual(session_bob.session_id, self.session.session_id)
        self.assertIsNone(
            self.grants.authorize(
                "outil_sensible", {}, mission_id, session_bob.session_id
            )
        )
        # Et il reste valide pour la session qui l'a obtenu.
        self.assertIsNotNone(
            self.grants.authorize(
                "outil_sensible", {}, mission_id, self.session.session_id
            )
        )

    def test_mission_d_un_autre_utilisateur_refusee(self) -> None:
        """Un autre client ne peut pas agir sur la mission d'un client."""
        payload = self.app.create_mission("Analyse de test", self.session)
        mission_id = payload["mission_id"]
        _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        session_bob = self.authenticator.login(JETON_BOB)
        detail = self.app.mission_detail(mission_id, session_bob)
        self.assertIn("error", detail)


class TestD1RunnerInvariant(unittest.TestCase):
    """Invariant du runner : la vérification suit la session de la mission."""

    def test_la_verification_utilise_la_session_de_la_mission(self) -> None:
        """Le grant est vérifié avec la session du propriétaire de la mission.

        L'invariant est vérifié au niveau du runner (indépendamment de
        l'interface) : un grant émis pour la session du client est accepté
        pour la mission de ce client, et refusé pour la session d'un autre.
        """
        app, runner, grants, authenticator = _build_app()
        session = authenticator.login(JETON_ALICE)
        mission = runner.create(
            "Analyse de test", owner_user_id=session.user_id,
            owner_session_id=session.session_id,
        )
        self.assertEqual(mission.session_id, session.session_id)
        self.assertNotEqual(mission.session_id, SESSION_APPLICATION)

        # Le grant est émis pour la session du client.
        grant = grants.issue(
            session_id=session.session_id,
            mission_id=mission.mission_id,
            tool_ids={"outil_sensible"},
        )
        # Il est refusé pour la session de l'application (l'identifiant
        # utilisé AVANT le correctif).
        self.assertIsNone(
            grants.authorize(
                "outil_sensible", {}, mission.mission_id, SESSION_APPLICATION
            )
        )
        # Il est accepté pour la session du client (l'identifiant utilisé
        # APRÈS le correctif).
        self.assertEqual(
            grants.authorize(
                "outil_sensible", {}, mission.mission_id, session.session_id
            ),
            grant.grant_id,
        )


if __name__ == "__main__":
    unittest.main()
