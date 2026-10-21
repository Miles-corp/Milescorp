"""Tests de régression des correctifs A-α et B-α (branche `fix/miles-answer-d1ter`).

Ces tests remplacent les tests d'observation
(`tests/test_investigation_d1ter_answer_path.py`, branche
`investigation/d1ter-and-answer-path`) et expriment le comportement **attendu
après correction**.

**A-α — réponse honnête de `POST /mission/<id>/answer`.**

Avant correction, la route répondait `{"answered": true}` même lorsque la
réponse était **réellement refusée** dans le fil d'exécution (refus de
session, demande expirée, budget d'interactions épuisé) : l'exception était
journalisée et absorbée par le fil. La validation est désormais **synchrone**
(identique au modèle de la correction D1-bis sur `/authorize`), avant le
lancement du fil.

Le **contrat** de la route est inchangé : le client transmet une réponse
texte et **aucun jeton n'est exigé** (l'option A-β n'est pas appliquée).

**B-α — suppression de la fenêtre de course D1-ter.**

Avant correction, le compte rendu d'une mission **en attente** demandait
l'analyse qualitative au fournisseur IA : le fil de la mission restait
occupé pendant l'appel, et une autorisation reçue pendant cette fenêtre était
**silencieusement ignorée** (HTTP 409). L'analyse n'est plus demandée
qu'une fois la mission terminée ; le 409 reste en place comme protection si
un conflit temporaire est encore possible.

Les tests sont non destructifs : outils simulés, répertoires temporaires,
fournisseur **simulé** (aucun appel réseau, aucun coût), aucune donnée
réelle lue ni écrite.
"""

from __future__ import annotations

import threading
import time
import unittest
from typing import Any, List, Optional, Tuple

from app.ai_providers.base import AIProvider
from app.config.settings import Settings
from app.interface.web import REASON_MISSION_BUSY, WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore, WebSession
from app.orchestration.models import ExecutionLimits, Plan, PlanStep
from app.orchestration.planner import PlanContext, ProviderPlanner
from app.orchestration.runner import (
    REASON_INTERACTION_BUDGET_EXCEEDED,
    REASON_MISSION_FINISHED,
    REASON_MISSION_NOT_FOUND,
    REASON_MISSION_NOT_OWNED,
    REASON_NO_PENDING_AUTHORIZATION,
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
    """Horloge mutable (expiration des demandes)."""

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
    produit un fait) avant l'outil sensible — c'est la situation réelle.
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


class _FournisseurSimule(AIProvider):
    """Fournisseur simulé : enregistre les consignes reçues.

    Aucun appel réseau, aucun coût : il permet de vérifier *quand* le
    fournisseur est interrogeé.
    """

    name = "simule"

    def __init__(self) -> None:
        self.prompts: List[list] = []

    def is_available(self) -> bool:
        return True

    def chat(self, messages: list) -> str:
        self.prompts.append(messages)
        return "{}"

    @property
    def analyses(self) -> list:
        """Les consignes d'analyse qualitative reçues."""
        return [
            p
            for p in self.prompts
            if any(
                "analyses les faits"
                in str(message.get("content") or "").lower()
                for message in p
            )
        ]


# ---------------------------------------------------------------------------
# A-α — la réponse de /answer est honnête
# ---------------------------------------------------------------------------

class TestReponseHonneteDeAnswer(unittest.TestCase):
    """A-α : la réponse positive n'est envoyée que si l'action a eu lieu."""

    def setUp(self) -> None:
        self.horloge = _Horloge()
        self.app, self.runner, self.grants, self.authenticator = _build_app(
            self.horloge
        )
        self.session = self.authenticator.login(JETON_ALICE)

    def _mission_en_attente(self, objectif: str = "Analyse de test") -> Tuple[str, str]:
        payload = self.app.create_mission(objectif, self.session)
        mission_id = payload["mission_id"]
        attente = _attendre_etat(
            self.app, mission_id, self.session, ("awaiting_authorization",)
        )
        self.assertEqual(attente.get("state"), "awaiting_authorization")
        pending = attente.get("pending") or {}
        return mission_id, str(pending.get("approval_token"))

    def test_reponse_valide_acceptee_et_mission_avancee(self) -> None:
        """1. Une réponse valide : réponse positive ET mission poursuivie."""
        mission_id, _ = self._mission_en_attente()
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
        self.assertIn(final.get("state"), ("completed", "partial"))

    def test_autre_session_refusee_explicitement(self) -> None:
        """2. Une autre session : REFUS EXPLICITE (et non une fausse
        réponse positive)."""
        mission_id, _ = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, autre_session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(reponse.get("reason"), REASON_SESSION_MISMATCH)
        # Aucune autorisation n'a été accordée.
        self.assertEqual(self.grants.list_grants(), [])
        self.assertEqual(
            self.runner.get(mission_id).state.value, "awaiting_authorization"
        )

    def test_mission_terminee_refusee_explicitement(self) -> None:
        """3. Une mission terminée : REFUS EXPLICITE."""
        mission_id, _ = self._mission_en_attente()
        self.app.answer_mission(mission_id, {"answer": "o"}, self.session)
        _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_FINISHED)

    def test_aucune_demande_en_attente_refusee_explicitement(self) -> None:
        """4. Un état invalide (aucune demande en attente) : refus explicite."""
        mission_id, _ = self._mission_en_attente()
        self.runner.get(mission_id).pending = None
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(reponse.get("reason"), REASON_NO_PENDING_AUTHORIZATION)

    def test_mission_inconnue_refusee_explicitement(self) -> None:
        """5. Une mission inconnue : refus explicite."""
        reponse = self.app.answer_mission(
            "mission-inexistante", {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_NOT_FOUND)

    def test_autre_utilisateur_refuse(self) -> None:
        """6. Un autre utilisateur : refus explicite (mission invisible)."""
        mission_id, _ = self._mission_en_attente()
        session_bob = self.authenticator.login(JETON_BOB)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, session_bob
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(self.grants.list_grants(), [])

    def test_demande_expiree_refusee_explicitement(self) -> None:
        """7. Une demande expirée : refus explicite (erreur
        avalée dans le fil)."""
        mission_id, _ = self._mission_en_attente()
        self.horloge.avancer(301.0)
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(self.grants.list_grants(), [])

    def test_budget_d_interactions_epuise_refuse_explicitement(self) -> None:
        """8. Un budget d'interactions épuisé : refus explicite (erreur
        avalée dans le fil)."""
        mission_id, _ = self._mission_en_attente()
        self.runner.get(mission_id).budget.interactions = 99
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)
        self.assertEqual(
            reponse.get("reason"), REASON_INTERACTION_BUDGET_EXCEEDED
        )
        self.assertEqual(self.grants.list_grants(), [])

    def test_reponse_vide_refusee(self) -> None:
        """9. Une réponse vide : refus explicite."""
        mission_id, _ = self._mission_en_attente()
        reponse = self.app.answer_mission(mission_id, {"answer": "  "}, self.session)
        self.assertIn("error", reponse)
        self.assertNotIn("answered", reponse)

    def test_le_contrat_de_answer_est_inchange(self) -> None:
        """10. Le contrat est préservé : AUCUN jeton n'est exigé (A-β n'est
        pas appliqué)."""
        mission_id, _ = self._mission_en_attente()
        reponse = self.app.answer_mission(
            mission_id, {"answer": "o"}, self.session
        )
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("answered"), True)

    def test_les_reponses_ne_divulguent_ni_jeton_ni_session(self) -> None:
        """11. Aucune réponse ne contient de jeton ni de session."""
        mission_id, token = self._mission_en_attente()
        autre_session = self.authenticator.login(JETON_ALICE)
        cas = [
            self.app.answer_mission(mission_id, {"answer": "o"}, autre_session),
            self.app.answer_mission(mission_id, {"answer": "  "}, self.session),
            self.app.answer_mission(
                "mission-inexistante", {"answer": "o"}, self.session
            ),
        ]
        for reponse in cas:
            with self.subTest(reponse=reponse):
                texte = " ".join(str(v) for v in reponse.values())
                self.assertNotIn(token, texte)
                self.assertNotIn(self.session.session_id, texte)
                self.assertNotIn(autre_session.session_id, texte)
                self.assertNotIn(str(self.session.csrf_token), texte)

    def test_les_codes_http_sont_explicites(self) -> None:
        """12. Au niveau HTTP : 200, 403 (refus), 409 (occupation)."""
        with WebTestServer(self.app, token=JETON_ALICE) as serveur:
            creation = serveur.raw_request(
                "POST", "/mission", {"objective": "Analyse de test"}
            )
            mission_id = (creation["json"] or {})["mission_id"]
            limite = time.time() + 20
            while time.time() < limite:
                detail = serveur.raw_request("GET", f"/mission/{mission_id}")
                if (detail["json"] or {}).get("state") == "awaiting_authorization":
                    break
                time.sleep(0.05)

            # Refus : autre session.
            autre = serveur.raw_request(
                "POST", "/session", {"token": JETON_ALICE}
            )
            session_autre = autre["json"] or {}
            entetes_autre = {
                "X-MILES-Session": session_autre["session_id"],
                "X-MILES-CSRF": session_autre["csrf_token"],
            }
            refus = serveur.raw_request(
                "POST",
                f"/mission/{mission_id}/answer",
                {"answer": "o"},
                headers=entetes_autre,
                authenticate=False,
            )
            self.assertEqual(refus["status"], 403)
            self.assertEqual(
                (refus["json"] or {}).get("reason"), REASON_SESSION_MISMATCH
            )

            # Réponse valide.
            accept = serveur.raw_request(
                "POST", f"/mission/{mission_id}/answer", {"answer": "o"}
            )
            self.assertEqual(accept["status"], 200)
            self.assertIs((accept["json"] or {}).get("answered"), True)


# ---------------------------------------------------------------------------
# B-α — la fenêtre de course D1-ter est supprimée
# ---------------------------------------------------------------------------

class TestFenetreD1terSupprimee(unittest.TestCase):
    """B-α : plus d'analyse IA pendant l'attente, plus d'autorisation
    ignorée."""

    def setUp(self) -> None:
        self.horloge = _Horloge()
        self.app, self.runner, self.grants, self.authenticator = _build_app(
            self.horloge, fait_dabord=True
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

    def test_pas_d_analyse_pendant_l_attente(self) -> None:
        """1. Aucune analyse qualitative n'est demandée pendant l'attente.

        C'est la cause racine de la fenêtre : sans appel au fournisseur, le
        fil de la mission se termine dès la demande d'autorisation.
        """
        fournisseur = _FournisseurSimule()
        self.runner.planner = ProviderPlanner(
            fournisseur, fallback=self.runner.planner
        )
        mission_id, _ = self._mission_en_attente()
        time.sleep(1.0)
        self.assertEqual(
            fournisseur.analyses,
            [],
            "une analyse qualitative a ete demandee pendant l'attente : la "
            "fenetre D1-ter subsiste",
        )

    def test_le_compte_rendu_final_conserve_l_analyse(self) -> None:
        """2. Le compte rendu DÉFINITIF conserve l'analyse qualitative."""
        fournisseur = _FournisseurSimule()
        self.runner.planner = ProviderPlanner(
            fournisseur, fallback=self.runner.planner
        )
        mission_id, token = self._mission_en_attente()
        self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        self.assertIn(final.get("state"), ("completed", "partial"))
        self.assertTrue(
            fournisseur.analyses,
            "le compte rendu final ne comporte pas d'analyse qualitative",
        )
        rapport = self.runner.get(mission_id).report or ""
        self.assertIn("Analyse qualitative", rapport)

    def test_le_compte_rendu_provisoire_est_coherent(self) -> None:
        """3. Le compte rendu provisoire d'une mission en attente reste
        cohérent (faits, erreurs, étapes) : seule l'analyse qualitative en
        est absente."""
        mission_id, _ = self._mission_en_attente()
        time.sleep(0.5)
        rapport = self.runner.get(mission_id).report or ""
        self.assertIn("Faits observés", rapport)
        self.assertIn("Étapes non terminées", rapport)
        self.assertIn("awaiting_authorization", rapport)

    def test_une_autorisation_n_est_plus_ignoree(self) -> None:
        """4. Une autorisation reçue juste après la demande n'est plus
        ignorée : elle est appliquée (pas de 409)."""
        mission_id, token = self._mission_en_attente()
        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertNotIn("error", reponse)
        self.assertIs(reponse.get("approved"), True)
        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        self.assertIn(final.get("state"), ("completed", "partial"))

    def test_le_409_reste_en_place_comme_filet(self) -> None:
        """5. Le 409 reste la réponse quand un conflit temporaire est
        encore possible (une autre action occupe la mission)."""
        mission_id, token = self._mission_en_attente()
        arreter = threading.Event()

        def _bloquant() -> None:
            arreter.wait(30)

        fil = threading.Thread(target=_bloquant, daemon=True)
        fil.start()
        self.addCleanup(arreter.set)
        self.app._mission_threads[mission_id] = fil

        reponse = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertIn("error", reponse)
        self.assertEqual(reponse.get("reason"), REASON_MISSION_BUSY)
        # La demande en attente est intacte : le réessai reste possible.
        self.assertEqual(
            self.runner.get(mission_id).pending.approval_token, token
        )

    def test_le_reessai_ne_duplique_ni_travail_ni_budget(self) -> None:
        """6. Le réessai ne duplique ni étape, ni appel d'outil, ni échange,
        et ne réinitialise aucun budget."""
        mission_id, token = self._mission_en_attente()
        arreter = threading.Event()

        def _bloquant() -> None:
            arreter.wait(30)

        fil = threading.Thread(target=_bloquant, daemon=True)
        fil.start()
        self.addCleanup(arreter.set)
        self.app._mission_threads[mission_id] = fil

        premier = self.app.authorize_mission(
            mission_id, {"approved": True, "approval_token": token}, self.session
        )
        self.assertEqual(premier.get("reason"), REASON_MISSION_BUSY)
        budget_avant = dict(self.runner.get(mission_id).budget.to_dict())

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

        final = _attendre_etat(
            self.app,
            mission_id,
            self.session,
            ("completed", "partial", "failed", "limit_reached"),
        )
        budget = final.get("budget") or {}
        self.assertEqual(budget.get("steps_executed"), 2)
        self.assertEqual(budget.get("tool_calls"), 2)
        self.assertEqual(budget.get("interactions"), 1)
        # Aucun budget n'a été réinitialisé par le réessai.
        self.assertGreaterEqual(
            budget.get("executed_seconds", 0), budget_avant.get("executed_seconds", 0)
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
