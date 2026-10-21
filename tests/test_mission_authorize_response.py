"""Tests de régression du défaut D1-bis : réponse HTTP honnête de l'autorisation.

DÉFAUT D1-bis (constaté par la campagne de validation, §4 du rapport
``PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md``, puis reproduit le
2026-10-21) :

    ``POST /mission/<id>/authorize`` répondait **HTTP 200** avec
    ``{"approved": true, "started": true}`` même lorsque le jeton
    d'approbation était **invalide**.

    Cause : la validation du jeton avait lieu dans le FIL d'exécution de la
    mission (``MissionRunner.authorize``), dont l'exception
    (``MissionAuthorizationError``) était journalisée et non retournée au
    client. Le ``try/except`` placé autour du *démarrage* du fil ne pouvait
    jamais rien intercepter : la réponse positive était inconditionnelle.

    La PROPRIÉTÉ DE SÉCURITÉ n'était pas violée (aucun grant n'était émis,
    la mission ne continuait pas), mais la réponse HTTP était mensongère :
    un client automatisé croyait avoir autorisé la mission.

CORRECTIF : le jeton, l'expiration et la session sont validés de façon
**synchrone** avant le lancement du fil (``MissionRunner.check_authorization``),
et la réponse n'est positive que si l'autorisation a réellement été
acceptée. Les refus portent un code HTTP explicite et un corps explicite
avec un code de raison stable.

Ces tests exercent le vrai chemin HTTP (serveur web local, requêtes réelles).
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any, List, Optional, Tuple

from app.config.settings import Settings
from app.interface.web import REASON_MISSION_BUSY, WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore, WebSession
from app.orchestration.models import ExecutionLimits, Plan, PlanStep
from app.orchestration.planner import PlanContext
from app.orchestration.runner import (
    REASON_EXPIRED_APPROVAL_TOKEN,
    REASON_INVALID_APPROVAL_TOKEN,
    REASON_MISSING_APPROVAL_TOKEN,
    REASON_MISSION_FINISHED,
    REASON_MISSION_NOT_FOUND,
    REASON_MISSION_NOT_OWNED,
    REASON_NO_PENDING_AUTHORIZATION,
    REASON_SESSION_MISMATCH,
    MissionRunner,
)
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolRegistry
from app.tools.service import ToolService
from tests.web_test_support import WebTestServer

#: Session de l'APPLICATION (celle du runner) : distincte de celle du client.
SESSION_APPLICATION = "session-application"

#: Jetons d'accès des clients de test.
JETON_ALICE = "jeton-alice-0123456789"
JETON_BOB = "jeton-bob-0123456789"


class _Horloge:
    """Horloge mutable : permet de faire expirer une demande d'autorisation."""

    def __init__(self, debut: float = 1_000.0) -> None:
        self._instant = debut

    def __call__(self) -> float:
        return self._instant

    def avancer(self, secondes: float) -> None:
        self._instant += secondes


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
    """Planificateur de test : renvoie toujours le même plan."""

    name = "test"
    note = "plan de test fixe"

    def __init__(self, steps: List[PlanStep]) -> None:
        self._steps = steps

    def plan(self, objective: str, context: PlanContext) -> Plan:
        return Plan(
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


def _build_app(
    horloge: Optional[_Horloge] = None,
) -> Tuple[WebApp, MissionRunner, GrantRegistry, WebAuthenticator]:
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
            approval_ttl_seconds=300.0,
        ),
        grant_registry=grants,
        session_id=SESSION_APPLICATION,
        allowed_tool_ids=["outil_ok", "outil_sensible"],
        clock=horloge if horloge is not None else time.time,
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
        time.sleep(0.05)
    return detail


class TestD1bisReponseDAutorisation(unittest.TestCase):
    """D1-bis : la réponse HTTP doit refléter l'acceptation réelle."""

    def setUp(self) -> None:
        self.horloge = _Horloge()
        self.app, self.runner, self.grants, self.authenticator = _build_app(
            self.horloge
        )
        self.session = self.authenticator.login(JETON_ALICE)

    # -- Outils --

    def _mission_en_attente(self, objectif: str = "Analyse de test") -> Tuple[str, str]:
        """Créer une mission et attendre sa demande d'autorisation.

        L'objectif distingue les missions : deux appels avec le meme
        objectif renverraient la meme mission (protection anti-double
        clic de l'interface web).
        """
        payload = self.app.create_mission(objectif, self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")
        pending = attente.get("pending") or {}
        self.assertTrue(pending.get("approval_token"))
        return mission_id, str(pending["approval_token"])

    def _autoriser(
        self,
        mission_id: str,
        token: Any,
        *,
        session: Optional[WebSession] = None,
        approved: bool = True,
    ) -> dict[str, Any]:
        """Appeler l'interface web d'autorisation (sans HTTP)."""
        return self.app.authorize_mission(
            mission_id,
            {"approved": approved, "approval_token": token},
            session or self.session,
        )

    # -- 1. Autorisation valide --

    def test_autorisation_valide_acceptee(self) -> None:
        """1. Un jeton valide : la réponse est positive ET la mission avance."""
        mission_id, token = self._mission_en_attente()
        reponse = self._autoriser(mission_id, token)
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("approved"), True)
        self.assertIs(reponse.get("started"), True)
        self.assertEqual(reponse.get("mission_id"), mission_id)

        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        self.assertIn(final.get("state"), ("completed", "partial"))

    def test_autorisation_valide_refus_explicite_du_client(self) -> None:
        """1b. Un refus explicite (`approved: false`) arrête la mission."""
        mission_id, token = self._mission_en_attente()
        reponse = self._autoriser(mission_id, token, approved=False)
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("approved"), False)

    # -- 2. Jeton invalide --

    def test_jeton_invalide_refuse_avec_raison_explicite(self) -> None:
        """2. Un jeton invalide : refus explicite, PAS de réponse positive."""
        mission_id, _ = self._mission_en_attente()
        reponse = self._autoriser(mission_id, "jeton-invalide-0123456789abcdef")
        self.assertIn("error", reponse)
        self.assertNotIn("approved", reponse)
        self.assertNotIn("started", reponse)
        self.assertEqual(reponse.get("reason"), REASON_INVALID_APPROVAL_TOKEN)

    def test_jeton_invalide_n_accorde_aucune_autorisation(self) -> None:
        """2b. Propriété de sécurité : rien n'est accordé, rien n'est exécuté."""
        mission_id, _ = self._mission_en_attente()
        self._autoriser(mission_id, "jeton-invalide-0123456789abcdef")
        time.sleep(0.3)
        mission = self.runner.get(mission_id)
        self.assertEqual(mission.state.value, "awaiting_authorization")
        self.assertEqual(mission.budget.steps_executed, 0)
        self.assertEqual(self.grants.list_grants(), [])

    def test_jeton_dune_autre_mission_refuse(self) -> None:
        """2c. Le jeton d'une mission ne vaut pas pour une autre mission."""
        mission_id, _ = self._mission_en_attente("Analyse de test A")
        autre_id, autre_token = self._mission_en_attente("Analyse de test B")
        self.assertNotEqual(mission_id, autre_id)
        reponse = self._autoriser(mission_id, autre_token)
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_INVALID_APPROVAL_TOKEN)
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(
            self.runner.get(autre_id).state.value, "awaiting_authorization"
        )

    def test_jeton_absent_refuse(self) -> None:
        """2d. Un jeton absent ou vide est refusé explicitement."""
        mission_id, _ = self._mission_en_attente()
        for token in (None, "", 123):
            with self.subTest(token=token):
                reponse = self.app.authorize_mission(
                    mission_id, {"approved": True, "approval_token": token}, self.session
                )
                self.assertIn("error", reponse)
                self.assertEqual(
                    reponse.get("reason"), REASON_MISSING_APPROVAL_TOKEN
                )

    # -- 3. Jeton expiré --

    def test_jeton_expire_refuse_avec_raison_explicite(self) -> None:
        """3. Une demande d'autorisation expirée est refusée explicitement."""
        mission_id, token = self._mission_en_attente()
        # L'expiration de la demande est de 300 s (approval_ttl_seconds).
        self.horloge.avancer(301.0)
        reponse = self._autoriser(mission_id, token)
        self.assertIn("error", reponse)
        self.assertNotIn("approved", reponse)
        self.assertEqual(reponse.get("reason"), REASON_EXPIRED_APPROVAL_TOKEN)
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(self.grants.list_grants(), [])

    # -- 4. Autre session --

    def test_autre_session_refusee_avec_raison_explicite(self) -> None:
        """4. Une autre session du meme utilisateur ne peut pas autoriser."""
        mission_id, token = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        self.assertNotEqual(autre_session.session_id, self.session.session_id)

        reponse = self._autoriser(mission_id, token, session=autre_session)
        self.assertIn("error", reponse)
        self.assertNotIn("approved", reponse)
        self.assertEqual(reponse.get("reason"), REASON_SESSION_MISMATCH)
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(self.grants.list_grants(), [])

    def test_autre_utilisateur_refuse_avec_raison_explicite(self) -> None:
        """4b. Un autre utilisateur ne peut pas autoriser la mission."""
        mission_id, token = self._mission_en_attente()
        session_bob = self.authenticator.login(JETON_BOB)
        reponse = self._autoriser(mission_id, token, session=session_bob)
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_NOT_OWNED)

    # -- 5. Mission déjà terminée --

    def test_mission_deja_terminee_refusee(self) -> None:
        """5. Une mission terminée n'est pas ré-autorisable."""
        mission_id, token = self._mission_en_attente()
        self._autoriser(mission_id, token)
        _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        reponse = self._autoriser(mission_id, token)
        self.assertIn("error", reponse)
        self.assertNotIn("approved", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_FINISHED)

    def test_mission_inconnue_refusee(self) -> None:
        """5b. Une mission inconnue est refusée explicitement."""
        reponse = self.app.authorize_mission(
            "mission-inexistante",
            {"approved": True, "approval_token": "x" * 64},
            self.session,
        )
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_NOT_FOUND)

    def test_autorisation_non_en_attente_refusee(self) -> None:
        """5c. Une mission qui n'attend aucune autorisation est refusée."""
        mission_id, _ = self._mission_en_attente()
        # La demande est levée : la mission n'attend plus d'autorisation.
        self.runner.get(mission_id).pending = None
        reponse = self._autoriser(mission_id, "x" * 64)
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_NO_PENDING_AUTHORIZATION)

    # -- 6. Mission en cours de traitement --

    def test_mission_en_cours_refuse_le_lancement_de_laction(self) -> None:
        """6. Si une action est déjà en cours, l'autorisation n'est PAS
        annoncée comme appliquée (elle serait silencieusement ignorée)."""
        mission_id, token = self._mission_en_attente()
        arreter = threading.Event()

        def _bloquant() -> None:
            arreter.wait(30)

        fil = threading.Thread(target=_bloquant, daemon=True)
        fil.start()
        self.addCleanup(arreter.set)
        self.app._mission_threads[mission_id] = fil

        reponse = self._autoriser(mission_id, token)
        self.assertIn("error", reponse)
        self.assertNotIn("approved", reponse)
        self.assertNotIn("started", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_BUSY)
        # La mission n'a pas été autorisée : elle attend toujours.
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(self.grants.list_grants(), [])

    # -- 7. Aucune divulgation --
    def test_les_erreurs_ne_divulguent_ni_jeton_ni_session(self) -> None:
        """6. Aucun message d'erreur ne contient de jeton ni de session."""
        mission_id, token = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        sessions = {self.session.session_id, autre_session.session_id}
        sessions.add(str(self.session.csrf_token))
        sessions.add(str(autre_session.csrf_token))

        cas = [
            self._autoriser(mission_id, "jeton-invalide-0123456789abcdef"),
            self._autoriser(mission_id, token, session=autre_session),
            self._autoriser(mission_id, None),
            self.app.authorize_mission(
                "mission-inexistante", {"approved": True}, self.session
            ),
        ]
        for reponse in cas:
            with self.subTest(reponse=reponse):
                texte = " ".join(str(v) for v in reponse.values())
                self.assertNotIn(token, texte)
                for identifiant in sessions:
                    self.assertNotIn(identifiant, texte)
                self.assertNotIn(JETON_ALICE, texte)


class TestD1bisHttp(unittest.TestCase):
    """D1-bis vu du point de vue HTTP (codes de réponse)."""

    def setUp(self) -> None:
        self.horloge = _Horloge()
        self.app, self.runner, self.grants, self.authenticator = _build_app(
            self.horloge
        )

    def _mission_en_attente_http(self, serveur: WebTestServer) -> Tuple[str, str]:
        """Créer une mission par HTTP et attendre sa demande d'autorisation."""
        creation = serveur.raw_request(
            "POST", "/mission", {"objective": "Analyse de test"}
        )
        self.assertEqual(creation["status"], 200)
        mission_id = (creation["json"] or {})["mission_id"]
        limite = time.time() + 20
        token = ""
        while time.time() < limite:
            detail = serveur.raw_request("GET", f"/mission/{mission_id}")
            payload = detail["json"] or {}
            if payload.get("state") == "awaiting_authorization":
                token = str((payload.get("pending") or {}).get("approval_token"))
                break
            time.sleep(0.05)
        self.assertTrue(token, "la mission n'a pas demande d'autorisation")
        return mission_id, token

    def test_jeton_invalide_repond_403(self) -> None:
        """Le jeton invalide est refusé par HTTP 403 (et non 200)."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, _ = self._mission_en_attente_http(serveur)
            reponse = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": "jeton-invalide-0123456789"},
            )
            self.assertEqual(reponse["status"], 403)
            corps = reponse["json"] or {}
            self.assertEqual(corps.get("reason"), REASON_INVALID_APPROVAL_TOKEN)
            self.assertNotIn("approved", corps)

    def test_jeton_valide_repond_200(self) -> None:
        """Le jeton valide est accepté par HTTP 200 et la mission avance."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, token = self._mission_en_attente_http(serveur)
            reponse = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(reponse["status"], 200)
            corps = reponse["json"] or {}
            self.assertIs(corps.get("approved"), True)
            self.assertIs(corps.get("started"), True)

    def test_jeton_expire_repond_403(self) -> None:
        """Une demande expirée est refusée par HTTP 403."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, token = self._mission_en_attente_http(serveur)
            self.horloge.avancer(301.0)
            reponse = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(reponse["status"], 403)
            corps = reponse["json"] or {}
            self.assertEqual(corps.get("reason"), REASON_EXPIRED_APPROVAL_TOKEN)

    def test_mission_terminee_repond_403(self) -> None:
        """Une mission déjà terminée est refusée par HTTP 403."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, token = self._mission_en_attente_http(serveur)
            premier = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(premier["status"], 200)
            limite = time.time() + 20
            while time.time() < limite:
                detail = serveur.raw_request("GET", f"/mission/{mission_id}")
                if (detail["json"] or {}).get("state") in (
                    "completed",
                    "partial",
                    "failed",
                    "limit_reached",
                ):
                    break
                time.sleep(0.05)
            second = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(second["status"], 403)
            corps = second["json"] or {}
            self.assertEqual(corps.get("reason"), REASON_MISSION_FINISHED)

    def test_mission_en_cours_repond_409(self) -> None:
        """Une mission encore en cours de traitement : HTTP 409 (reessai)."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, token = self._mission_en_attente_http(serveur)
            arreter = threading.Event()

            def _bloquant() -> None:
                arreter.wait(30)

            fil = threading.Thread(target=_bloquant, daemon=True)
            fil.start()
            self.addCleanup(arreter.set)
            self.app._mission_threads[mission_id] = fil

            reponse = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(reponse["status"], 409)
            corps = reponse["json"] or {}
            self.assertEqual(corps.get("reason"), REASON_MISSION_BUSY)
            self.assertNotIn("approved", corps)

    def test_les_reponses_erreur_ne_divulguent_pas_de_jeton(self) -> None:
        """Aucune réponse d'erreur HTTP ne contient le jeton d'approbation."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            mission_id, token = self._mission_en_attente_http(serveur)
            reponse = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": "jeton-invalide-0123456789"},
            )
            self.assertEqual(reponse["status"], 403)
            self.assertNotIn(token, reponse["body"])
            self.assertNotIn(
                str(serveur.session["session_id"]), reponse["body"]
            )
            self.assertNotIn(str(serveur.session["csrf_token"]), reponse["body"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
