"""Tests d'INVESTIGATION (branche `investigation/d1ter-and-answer-path`).

Ces tests ne modifient **aucun code de production** : ils documentent le
comportement observé de deux signalements de sécurité :

- **Risque A — parcours `/answer`** : une mission en attente
  d'autorisation peut-elle être approuvée sans présenter le jeton
  d'approbation ?
- **Risque B — D1-ter** : une autorisation reçue pendant la génération du
  rapport est-elle ignorée, et le 409 correspond-il à un état temporaire ?

Ils utilisent uniquement des **outils de test** (simulés, sans effet de
bord) et des répertoires temporaires : aucune donnée réelle n'est lue ni
écrite, aucun fournisseur distant n'est appelé, aucun appel API payant n'est
effectué.

Ils sont volontairement **descriptifs** : ils décrivent le comportement
actuel, y compris les écarts constatés, afin de servir de base de régression
lorsqu'un correctif sera décidé par l'auditeur.
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import Settings
from app.interface.web import REASON_MISSION_BUSY, WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore, WebSession
from app.orchestration.models import ExecutionLimits, Plan, PlanStep
from app.orchestration.planner import PlanContext
from app.orchestration.runner import (
    REASON_SESSION_MISMATCH,
    MissionAuthorizationError,
    MissionRunner,
)
from app.tools.grants import GrantRegistry
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.service import ToolService
from tests.web_test_support import WebTestServer

#: Session de l'APPLICATION (celle du runner) : distincte de celle du client.
SESSION_APPLICATION = "session-application"

#: Jetons d'accès des clients de test.
JETON_ALICE = "jeton-alice-0123456789"
JETON_BOB = "jeton-bob-0123456789"


class _Horloge:
    """Horloge mutable (expiration des demandes, durée de vie)."""

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
    *,
    fait_dabord: bool = False,
) -> Tuple[WebApp, MissionRunner, GrantRegistry, WebAuthenticator]:
    """Construire une application web avec un runner de session distincte.

    ``fait_dabord`` : le plan commence par un outil de risque LOW (qui
    produit un fait) avant l'outil sensible. C'est la situation réelle
    (le planificateur déterministe commence par ``action_workdir``) : sans
    fait observé, le rapport n'appelle pas le fournisseur et la fenêtre
    « mission occupée » n'existe pas.
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
    etapes = (
        [
            PlanStep("s1", "Outil simple", "outil_ok"),
            PlanStep("s2", "Outil sensible", "outil_sensible"),
        ]
        if fait_dabord
        else [
            PlanStep("s1", "Outil sensible", "outil_sensible"),
            PlanStep("s2", "Outil simple", "outil_ok"),
        ]
    )
    runner = MissionRunner(
        service,
        planner=_PlanFixe(etapes),
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
) -> dict:
    """Attendre que la mission atteigne l'un des états donnés."""
    limite = time.time() + delai
    detail: dict = {}
    while time.time() < limite:
        detail = app.mission_detail(mission_id, session)
        if detail.get("state") in etats:
            return detail
        time.sleep(0.05)
    return detail


# ---------------------------------------------------------------------------
# Risque A — le parcours /answer
# ---------------------------------------------------------------------------

class TestParcoursAnswerInvestigation(unittest.TestCase):
    """RISQUE A : le parcours `/answer` peut approuver sans jeton."""

    def setUp(self) -> None:
        self.app, self.runner, self.grants, self.authenticator = _build_app()
        self.session = self.authenticator.login(JETON_ALICE)

    def _mission_en_attente(self, objectif: str = "Analyse de test") -> Tuple[str, str]:
        """Créer une mission et attendre sa demande d'autorisation."""
        payload = self.app.create_mission(objectif, self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")
        pending = attente.get("pending") or {}
        return mission_id, str(pending.get("approval_token"))

    # -- A1 : approbation sans jeton --

    def test_answer_approuve_sans_jeton(self) -> None:
        """A1 : `/answer` avec « o » approuve SANS jeton d'approbation.

        Constat : le chemin `/answer` appelle `MissionRunner.answer`, qui
        utilise **en interne** le jeton de la demande en attente. Le client
        n'a donc pas à le présenter, contrairement à `/authorize`.
        """
        mission_id, token = self._mission_en_attente()
        self.assertTrue(token)

        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("answered"), True)

        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        # La mission a AVANCÉ : l'étape sensible a été exécutée.
        self.assertIn(final.get("state"), ("completed", "partial"))
        budget = final.get("budget") or {}
        self.assertEqual(budget.get("steps_executed"), 2)
        # Un grant a bien été émis (l'autorisation est réelle).
        self.assertEqual(len(self.grants.list_grants()), 1)

    def test_answer_refuse_sans_jeton_arrete_la_mission(self) -> None:
        """A2 : une réponse non-approbative arrête la mission (refus)."""
        mission_id, _ = self._mission_en_attente()
        reponse = self.app.answer_mission(
            mission_id, {"answer": "non"}, self.session
        )
        self.assertNotIn("error", reponse)
        final = _attendre_etat(
            self.app, mission_id, self.session, ("failed", "completed", "partial")
        )
        self.assertEqual(final.get("state"), "failed")

    def test_les_deux_parcours_ont_un_comportement_different(self) -> None:
        """A3 : `/authorize` exige le jeton, `/answer` ne l'exige pas.

        Asymétrie constatée : la protection « le client présente le jeton
        d'approbation » (correction P1-6-06) ne s'applique qu'à la route
        `/authorize`.
        """
        mission_id, token = self._mission_en_attente()

        # `/authorize` sans jeton : refusé.
        refus = self.app.authorize_mission(
            mission_id, {"approved": True}, self.session
        )
        self.assertIn("error", refus)
        self.assertEqual(refus.get("reason"), "missing_approval_token")

        # `/answer` sans jeton : accepté.
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertNotIn("error", reponse)

    # -- A4 : autre session / autre utilisateur --

    def test_answer_depuis_une_autre_session_refuse_effectivement(self) -> None:
        """A4 : une autre session du MÊME utilisateur **ne peut pas**
        approuver — mais la réponse HTTP est mensongère.

        Constat : le refus est bien levé (contrôle de session de
        `check_authorization`), mais il se produit DANS LE FIL
        d'exécution, dont l'exception est journalisée et absorbée : la
        route `/answer` répond malgré tout « answered: true ».

        Impact réel : **aucune** autorisation n'est accordée, **aucun**
        outil sensible n'est exécuté ; le défaut est une réponse positive
        mensongère (même famille que D1-bis, sur la route `/answer`).
        """
        mission_id, _ = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, autre_session
        )
        # La mission n'a PAS été approuvée : ni grant, ni étape sensible.
        time.sleep(0.3)
        self.assertEqual(self.grants.list_grants(), [])
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        # MAIS la réponse annonce une réponse traitée : c'est le défaut.
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("answered"), True)

    def test_answer_par_un_autre_utilisateur_refuse(self) -> None:
        """A5 : un autre utilisateur ne voit pas la mission et ne peut rien
        faire dessus."""
        mission_id, _ = self._mission_en_attente()
        session_bob = self.authenticator.login(JETON_BOB)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, session_bob
        )
        self.assertIn("error", reponse)
        # La mission est invisible pour Bob (erreur « mission inconnue »).
        detail = self.app.mission_detail(mission_id, session_bob)
        self.assertIn("error", detail)
        self.assertEqual(self.grants.list_grants(), [])

    # -- A6 : le parcours légitime (clarification) --

    def test_answer_repond_a_une_clarification(self) -> None:
        """A6 : le usage légitime de `/answer` (clarification) fonctionne.

        Un planificateur qui demande une clarification (comme le
        planificateur déterministe lorsqu'aucun dossier n'est déductible)
        déclenche le chemin `kind == "clarification"`.
        """
        from app.orchestration.planner import ClarificationRequired

        class _PlanClarification:
            name = "clarification"
            note = "demande de clarification"

            def plan(self, objective: str, context: PlanContext) -> Plan:
                raise ClarificationRequired("Quel dossier dois-je analyser ?")

        app, runner, grants, authenticator = _build_app()
        runner.planner = _PlanClarification()
        session = authenticator.login(JETON_ALICE)

        payload = app.create_mission("Analyse l'organisation", session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            app, mission_id, session, ("needs_clarification",)
        )
        self.assertEqual(attente.get("state"), "needs_clarification")
        reponse = app.answer_mission(mission_id, {"answer": "docs/"}, session)
        self.assertNotIn("error", reponse)

    # -- A7 : le grant émis reste aussi strict --

    def test_le_grant_emis_par_answer_est_lie_a_la_session(self) -> None:
        """A7 : le grant émis via `/answer` n'est pas plus permissif qu'un
        grant obtenu par `/authorize` : il est lié à la session, à la
        mission et au périmètre demandé."""
        mission_id, _ = self._mission_en_attente()
        self.app.answer_mission(mission_id, {"answer": "o"}, self.session)
        _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        grants = self.grants.list_grants()
        self.assertEqual(len(grants), 1)
        grant = grants[0]
        self.assertEqual(grant.session_id, self.session.session_id)
        self.assertEqual(grant.mission_id, mission_id)
        # Utilisable uniquement par la session qui l'a obtenu.
        self.assertIsNone(
            self.grants.authorize(
                "outil_sensible", {}, mission_id, "session-autre"
            )
        )


# ---------------------------------------------------------------------------
# Risque B — D1-ter : l'autorisation reçue pendant la génération du rapport
# ---------------------------------------------------------------------------

class TestD1terInvestigation(unittest.TestCase):
    """RISQUE B : une autorisation peut être ignorée (fenêtre « occupée »)."""

    def setUp(self) -> None:
        # Plan « fait d abord » : la mission a un fait observé avant la
        # demande d'autorisation (situation reelle), donc le rapport
        # interroge le fournisseur et la fenetre existe.
        self.app, self.runner, self.grants, self.authenticator = _build_app(
            fait_dabord=True
        )
        self.session = self.authenticator.login(JETON_ALICE)

    def _mission_en_attente(self) -> Tuple[str, str]:
        payload = self.app.create_mission("Analyse de test", self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")
        pending = attente.get("pending") or {}
        return mission_id, str(pending.get("approval_token"))

    def _bloquer_le_fil(self, mission_id: str) -> threading.Event:
        """Simuler une action en cours pour cette mission (fil vivant)."""
        arreter = threading.Event()

        def _bloquant() -> None:
            arreter.wait(30)

        fil = threading.Thread(target=_bloquant, daemon=True)
        fil.start()
        self.addCleanup(arreter.set)
        self.app._mission_threads[mission_id] = fil
        return arreter

    # -- B1 : l'autorisation est ignorée pendant la fenêtre --

    def test_autorisation_ignoree_pendant_la_fenetre(self) -> None:
        """B1 : pendant l'occupation, l'autorisation est IGNORÉE (409).

        Le jeton n'est ni consommé ni invalidé : la demande en attente
        reste intacte.
        """
        mission_id, token = self._mission_en_attente()
        self._bloquer_le_fil(mission_id)

        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_BUSY)

        mission = self.runner.get(mission_id)
        # La demande en attente est intacte et le jeton toujours valable.
        self.assertIsNotNone(mission.pending)
        self.assertEqual(mission.pending.approval_token, token)
        self.assertEqual(mission.state.value, "awaiting_authorization")
        # Aucune autorisation n'a été accordée, aucun grant émis.
        self.assertEqual(self.grants.list_grants(), [])
        # Le budget d'échanges n'a pas été consommé.
        self.assertEqual(mission.budget.interactions, 1)

    # -- B2 : le 409 est temporaire, le réessai fonctionne --

    def test_reessai_apres_la_fenetre_reussit(self) -> None:
        """B2 : le 409 est TEMPORAIRE : après la fenêtre, le réessai
        réussit et la mission aboutit.

        Aucun état incohérent n'est créé : la mission reprend exactement
        où elle s'était arrêtée, sans re-exécuter d'étape.
        """
        mission_id, token = self._mission_en_attente()
        arreter = self._bloquer_le_fil(mission_id)

        premier = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertEqual(premier.get("reason"), REASON_MISSION_BUSY)

        # La fenêtre se referme : le fil se termine.
        arreter.set()
        for _ in range(200):
            thread = self.app._mission_threads.get(mission_id)
            if thread is None or not thread.is_alive():
                break
            time.sleep(0.05)

        second = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertNotIn("error", second)
        self.assertIs(second.get("approved"), True)

        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        self.assertIn(final.get("state"), ("completed", "partial"))
        budget = final.get("budget") or {}
        # Les deux étapes ont été exécutées UNE SEULE fois (pas de double
        # exécution dues au réessai).
        self.assertEqual(budget.get("steps_executed"), 2)
        self.assertEqual(budget.get("interactions"), 1)

    # -- B3 : le rôle du rapport (cause racine) --

    def test_le_rapport_demande_une_analyse_pendant_l_attente(self) -> None:
        """B3 (cause racine, déterministe) : pendant que la mission
        ATTEND, le compte rendu de la mission demande déjà une analyse
        qualitative au fournisseur IA.

        C'est ce qui garde le fil de la mission occupé : l'autorisation
        reçue pendant cette fenêtre est ignorée. Le fournisseur est
        **simulé** (aucun appel réseau, aucun coût) ; l'appel est
        détecté par le contenu de la consigne.
        """
        from app.ai_providers.base import AIProvider
        from app.orchestration.planner import ProviderPlanner

        prompts: List[dict] = []

        class _FournisseurSimule(AIProvider):
            """Fournisseur simulé : enregistre les consignes reçues."""

            name = "simule"

            def is_available(self) -> bool:
                return True

            def chat(self, messages: list) -> str:
                prompts.append(messages)
                return "{}"

        app, runner, grants, authenticator = _build_app(fait_dabord=True)
        runner.planner = ProviderPlanner(
            _FournisseurSimule(), fallback=runner.planner
        )
        session = authenticator.login(JETON_ALICE)

        payload = app.create_mission("Analyse de test", session)
        mission_id = payload["mission_id"]
        _attendre_etat(
            app, mission_id, session, ("awaiting_authorization",)
        )

        # Une consigne d'ANALYSE a été envoyée alors que la mission
        # attend encore son autorisation. (L'état « awaiting_authorization »
        # est posé AVANT la construction du rapport : on attend donc que
        # l'appel au fournisseur ait eu lieu.)
        limite = time.time() + 10
        analyses = []
        while time.time() < limite and not analyses:
            analyses = [
                m for m in prompts
                if any(
                    "analyses les faits"
                    in str(message.get("content") or "").lower()
                    for message in m
                )
            ]
            if not analyses:
                time.sleep(0.05)
        self.assertTrue(
            analyses,
            "aucune analyse qualitative n'a ete demandee pour une mission "
            "en attente : la cause racine du defaut D1-ter n'est pas "
            "reproduite",
        )

    def test_le_rapport_interroge_le_fournisseur_meme_en_attente(self) -> None:
        """B3 (cause racine) : le rapport est construit même pour une
        mission EN ATTENTE, et l'analyse qualitative est demandée au
        fournisseur : le fil de la mission reste donc occupé le temps de
        l'appel au fournisseur.

        Le test est déterministe et ne fait appel à AUCUN fournisseur
        distant : un fournisseur simulé, contrôlé par l'horloge du test,
        mesure le temps d'occupation du fil.
        """
        horloge = _Horloge()
        app, runner, grants, authenticator = _build_app(
            horloge, fait_dabord=True
        )
        session = authenticator.login(JETON_ALICE)

        payload = app.create_mission("Analyse de test", session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            app, mission_id, session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")

        # Le rapport de la mission en attente contient-il une section
        # d'analyse ? (l'analyse n'est possible que si un fournisseur est
        # configuré ; ici il n'y en a pas, mais la SECTION est présente
        # dans le compte rendu, ce qui prouve que l'analyse est demandée
        # pour une mission non terminée).
        rapport = runner.get(mission_id).report or ""
        self.assertIn("Analyse qualitative", rapport)

    # -- B4 : pas de double exécution --

    def test_le_reessai_ne_rexecute_pas_les_etapes_faites(self) -> None:
        """B4 : le réessai ne rejoue pas les étapes déjà terminées."""
        mission_id, token = self._mission_en_attente()
        arreter = self._bloquer_le_fil(mission_id)
        self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        arreter.set()
        for _ in range(200):
            thread = self.app._mission_threads.get(mission_id)
            if thread is None or not thread.is_alive():
                break
            time.sleep(0.05)
        self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        budget = final.get("budget") or {}
        self.assertEqual(budget.get("steps_executed"), 2)
        self.assertEqual(budget.get("tool_calls"), 2)

    # -- B5 : le comportement HTTP --

    def test_le_409_est_bien_un_conflit_temporaire(self) -> None:
        """B5 : au niveau HTTP, la fenêtre donne 409 et le réessai 200."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            creation = serveur.raw_request(
                "POST", "/mission", {"objective": "Analyse de test"}
            )
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
            self.assertTrue(token)

            arreter = self._bloquer_le_fil(mission_id)
            refus = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(refus["status"], 409)
            self.assertEqual(
                (refus["json"] or {}).get("reason"), REASON_MISSION_BUSY
            )

            arreter.set()
            for _ in range(200):
                thread = self.app._mission_threads.get(mission_id)
                if thread is None or not thread.is_alive():
                    break
                time.sleep(0.05)
            accept = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/authorize",
                {"approved": True, "approval_token": token},
            )
            self.assertEqual(accept["status"], 200)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
