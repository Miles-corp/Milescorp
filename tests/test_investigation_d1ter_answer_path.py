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
    REASON_AUTHORIZATION_REQUIRES_TOKEN,
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

    def test_answer_n_approuve_plus_sans_jeton(self) -> None:
        """A1 (corrige P1) : `/answer` n'approuve PLUS une autorisation.

        Constat initial (avant correction P1) : le chemin `/answer`
        appelait `MissionRunner.answer`, qui utilisait **en interne** le
        jeton de la demande en attente : le client n'avait pas a le
        presenter, contrairement a `/authorize`.

        Apres correction P1 : `/answer` ne traite plus que les
        **clarifications**. Une demande d'autorisation reçoit un refus
        explicite ; la mission n'est ni approuvee ni arretee.
        """
        mission_id, token = self._mission_en_attente()
        self.assertTrue(token)

        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(
            reponse.get("reason"), REASON_AUTHORIZATION_REQUIRES_TOKEN
        )

        time.sleep(0.3)
        # La mission n'est ni approuvee ni tuee : elle attend toujours.
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(len(self.grants.list_grants()), 0)
        # La demande en attente et son jeton sont intacts.
        self.assertEqual(
            self.runner.get(mission_id).pending.approval_token, token
        )
    def test_answer_non_approbatif_ne_tue_pas_la_mission(self) -> None:
        """A2 (corrige P1) : une reponse non-approbative n'arrete pas la
        mission : elle est refusee comme toute reponse a une demande
        d'autorisation."""
        mission_id, _ = self._mission_en_attente()
        reponse = self.app.answer_mission(
            mission_id, {"answer": "non"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertEqual(
            reponse.get("reason"), REASON_AUTHORIZATION_REQUIRES_TOKEN
        )
        time.sleep(0.3)
        # La mission n'est pas arretee : elle attend toujours.
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        self.assertEqual(len(self.grants.list_grants()), 0)
    def test_les_deux_parcours_exigent_le_jeton(self) -> None:
        """A3 (corrige P1) : l'asymetrie a disparu.

        | Route | Jeton exige ? | Resultat |
        |-------|---------------|----------|
        | `POST /mission/<id>/authorize` | **oui** | sans jeton -> `403 missing_approval_token` |
        | `POST /mission/<id>/answer` | - | n'approuve pas : refus explicite |

        `/answer` ne traite plus que les **clarifications** ; l'approbation
        d'une autorisation passe par `/authorize` et son jeton (usage unique,
        expiration, session, proprietaire).
        """
        mission_id, _ = self._mission_en_attente()

        # `/authorize` sans jeton : refuse.
        refus = self.app.authorize_mission(
            mission_id, {"approved": True}, self.session
        )
        self.assertIn("error", refus)
        self.assertEqual(refus.get("reason"), "missing_approval_token")

        # `/answer` : refus explicite, aucune approbation.
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertEqual(
            reponse.get("reason"), REASON_AUTHORIZATION_REQUIRES_TOKEN
        )
        self.assertEqual(len(self.grants.list_grants()), 0)
    def test_answer_depuis_une_autre_session_est_refuse(self) -> None:
        """A4 (corrige P1) : une autre session du meme utilisateur ne peut
        pas approuver, et la reponse le dit.

        Avant correction P1 : le refus etait bien leve mais absorbe par le
        fil d'execution, et la route repondait « answered: true » (reponse
        positive mensongere). Apres correction P1 : le refus est explicite
        et l'autorisation n'est pas accordee.
        """
        mission_id, _ = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, autre_session
        )
        # La mission n'a PAS ete approuvee : ni grant, ni etape sensible.
        time.sleep(0.3)
        self.assertEqual(self.grants.list_grants(), [])
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )
        # Et la reponse le dit explicitement.
        self.assertIn("error", reponse)
        self.assertEqual(
            reponse.get("reason"), REASON_AUTHORIZATION_REQUIRES_TOKEN
        )
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

    def test_le_grant_emis_par_authorize_est_lie_a_la_session(self) -> None:
        """A7 (corrige P1) : `/answer` n'emet plus de grant.

        Le grant est emis par `/authorize` : il est lie a la session, a la
        mission et au perimetre demande.
        """
        mission_id, token = self._mission_en_attente()
        self.app.answer_mission(mission_id, {"answer": "o"}, self.session)
        self.assertEqual(len(self.grants.list_grants()), 0)
        self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
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

    def test_le_rapport_ne_demande_pas_d_analyse_pendant_l_attente(
        self,
    ) -> None:
        """B3 (corrige B-alpha) : pendant que la mission ATTEND, le compte
        rendu ne demande **pas** d'analyse qualitative au fournisseur IA.

        C'etait la cause racine de la fenetre D1-ter : l'appel au
        fournisseur gardait le fil de la mission occupe, et une
        autorisation recue pendant ce temps etait ignoree. Le correctif B-alpha
        n'appelle l'analyse que pour une mission terminee.
        """
        from app.ai_providers.base import AIProvider
        from app.orchestration.planner import ProviderPlanner

        prompts: List[dict] = []

        class _FournisseurSimule(AIProvider):
            """Fournisseur simule : enregistre les consignes recues."""

            name = "simule"

            def is_available(self) -> bool:
                return True

            def chat(self, messages: list) -> str:
                prompts.append(messages)
                return "{}"

        self.runner.planner = ProviderPlanner(
            _FournisseurSimule(), fallback=self.runner.planner
        )
        self._mission_en_attente()
        time.sleep(1.0)
        analyses = [
            m for m in prompts
            if any(
                "analyses les faits" in str(part).lower()
                for message in m
                for part in (message.get("content") or "")
            )
        ]
        self.assertEqual(
            analyses,
            [],
            "une analyse qualitative a ete demandee pendant l'attente : la "
            "fenetre D1-ter subsiste",
        )
    def test_le_rapport_provisoire_na_pas_de_section_analyse(self) -> None:
        """B3b (corrige B-alpha) : le compte rendu provisoire d'une mission
        en attente ne comporte pas de section « Analyse qualitative ».

        Le compte rendu DEFINITIF (mission terminee) la conserve : c'est
        l'analyse d'une mission terminee qui a du sens.
        """
        mission_id, _ = self._mission_en_attente()
        time.sleep(0.5)
        rapport = self.runner.get(mission_id).report or ""
        self.assertIn("Faits observés", rapport)
        self.assertNotIn("Analyse qualitative", rapport)
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
