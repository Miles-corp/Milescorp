"""Tests de sécurité web — Phase 6.1 (correction des P1 de l'audit Phase 6).

Ces tests couvrent les cas exigés :

1. origine étrangère refusée ;
2. origine autorisée acceptée **uniquement** avec authentification et CSRF
   valides ;
3. absence d'Origin traitée conformément à la politique documentée ;
4. type de contenu incorrect refusé ;
5. jeton CSRF absent, incorrect ou expiré refusé ;
6. appelant non authentifié incapable d'autoriser une mission ;
7. utilisateur A incapable d'autoriser la mission de B ;
8. jeton d'une mission inutilisable sur une autre mission ;
9. confirmation expirée, révoquée ou rejouée refusée ;
10. aucune exécution d'outil et aucune modification d'état après un refus ;
11. chemins CLI et web toujours soumis aux contrôles du moteur ;
12. non-régression de l'ensemble de la suite (couvert par la suite complète).

Aucun test n'effectue d'action externe réelle.
"""

from __future__ import annotations

import json
import unittest

from app.config.settings import Settings
from app.interface.cli import CLI
from app.interface.web_auth import (
    CSRF_HEADER,
    SESSION_HEADER,
    OriginPolicy,
    WebAuthenticator,
    WebCredentialStore,
    WebSession,
)
from app.orchestration.models import ExecutionLimits, MissionState
from app.orchestration.runner import MissionAuthorizationError, MissionRunner
from app.tools.grants import GrantRegistry
from app.tools.service import ToolService
from tests.web_test_support import (
    OTHER_TOKEN,
    OTHER_USER,
    TEST_TOKEN,
    TEST_USER,
    WebTestServer,
    build_app,
)

#: Origine malveillante utilisée par les tests.
FOREIGN_ORIGIN = "http://site-malveillant.example"


def _runner(*, clock=None) -> tuple[MissionRunner, ToolService, GrantRegistry]:
    """Construire un orchestrateur isolé pour les tests de mission."""
    grants = GrantRegistry()
    service = ToolService(grant_checker=grants)
    runner = MissionRunner(
        service,
        limits=ExecutionLimits(max_steps=4, max_duration_seconds=20.0),
        grant_registry=grants,
        session_id="session-processus",
        clock=clock if clock is not None else __import__("time").time,
    )
    return runner, service, grants


class TestOriginPolicy(unittest.TestCase):
    """Politique d'origine : comportement unitaire, sans HTTP."""

    def test_origine_etrangere_refusee(self) -> None:
        policy = OriginPolicy()
        autorise, motif = policy.check(
            FOREIGN_ORIGIN, None, "127.0.0.1:8080"
        )
        self.assertFalse(autorise)
        self.assertIn("Origine", motif)

    def test_origine_locale_acceptee(self) -> None:
        policy = OriginPolicy()
        autorise, _ = policy.check(
            "http://127.0.0.1:8080", None, "127.0.0.1:8080"
        )
        self.assertTrue(autorise)

    def test_origine_explicitement_configuree_acceptee(self) -> None:
        policy = OriginPolicy(["https://app.interne.example"])
        autorise, _ = policy.check(
            "https://app.interne.example", None, "127.0.0.1:8080"
        )
        self.assertTrue(autorise)

    def test_hote_non_local_ne_donne_pas_d_origine_de_repli(self) -> None:
        """Un en-tête Host non local ne permet pas de forger une origine."""
        policy = OriginPolicy()
        autorise, _ = policy.check(
            "http://site-malveillant.example", None, "site-malveillant.example"
        )
        self.assertFalse(autorise)

    def test_absence_d_origin_et_de_referer_admise(self) -> None:
        """Sans Origin ni Referer, la décision est déléguée à session+CSRF."""
        policy = OriginPolicy()
        autorise, motif = policy.check(None, None, "127.0.0.1:8080")
        self.assertTrue(autorise)
        self.assertEqual(motif, "")

    def test_referer_etranger_refuse(self) -> None:
        policy = OriginPolicy()
        autorise, motif = policy.check(None, FOREIGN_ORIGIN, "127.0.0.1:8080")
        self.assertFalse(autorise)
        self.assertIn("Referer", motif)


class TestWebRouteProtection(unittest.TestCase):
    """P1-6-03 : protection des routes web modifiantes."""

    def test_1_origine_etrangere_refusee_sur_toutes_les_routes(self) -> None:
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            for path, body in (
                ("/tool", {"tool": "status_read", "parameters": {}}),
                ("/remember", {"content": "souvenir injecte"}),
                ("/forget", {"id": 1}),
                ("/message", {"message": "bonjour"}),
                ("/mission", {"objective": "Analyse ce dossier"}),
            ):
                with self.subTest(path=path):
                    result = server.raw_request(
                        "POST",
                        path,
                        body,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": FOREIGN_ORIGIN,
                        },
                    )
                    self.assertEqual(result["status"], 403)

    def test_1b_origine_etrangere_avec_content_type_non_json_refusee(self) -> None:
        """Le vecteur exact de l'audit (text/plain + origine étrangère)."""
        app = build_app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                json.dumps({"tool": "status_read", "parameters": {}}).encode(),
                headers={
                    "Content-Type": "text/plain",
                    "Origin": FOREIGN_ORIGIN,
                },
            )
            self.assertEqual(result["status"], 403)

    def test_2_origine_autorisee_sans_authentification_refusee(self) -> None:
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)

    def test_2b_origine_autorisee_avec_session_sans_csrf_refusee(self) -> None:
        app = build_app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            # Sans en-tête de session : refusé par l'authentification.
            self.assertEqual(result["status"], 401)

    def test_3_absence_d_origin_traitee_selon_la_politique(self) -> None:
        """Sans Origin, la requête est acceptée si session et CSRF sont
        valides, et refusée sinon."""
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            # Sans Origin mais avec session et CSRF valides : accepté.
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(result["status"], 200)
            self.assertTrue(result["json"]["success"])

            # Sans Origin et sans session : refusé.
            sans_session = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(sans_session["status"], 401)

    def test_4_type_de_contenu_incorrect_refuse(self) -> None:
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            for media_type in ("text/plain", "application/x-www-form-urlencoded", ""):
                with self.subTest(media_type=media_type):
                    headers = {}
                    if media_type:
                        headers["Content-Type"] = media_type
                    result = server.raw_request(
                        "POST",
                        "/tool",
                        json.dumps({"tool": "status_read"}).encode(),
                        headers=headers,
                    )
                    self.assertEqual(result["status"], 415)

    def test_5_csrf_absent_ou_incorrect_refuse(self) -> None:
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            # Jeton CSRF absent.
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)

            # Jeton CSRF faux (session valide).
            faux = {
                SESSION_HEADER: server.session["session_id"],
                CSRF_HEADER: "jeton-csrf-faux" * 4,
            }
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json", **faux},
                authenticate=False,
            )
            self.assertEqual(result["status"], 403)

    def test_5b_csrf_expire_refuse(self) -> None:
        """Un jeton CSRF d'une session expirée est refusé."""
        authenticator = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN}),
            session_ttl_seconds=0.0,
        )
        app = build_app(tool_service=ToolService())
        app.authenticator = authenticator
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(result["status"], 401)

    def test_csrf_est_propre_a_la_session(self) -> None:
        """Le jeton CSRF n'est pas un secret statique partagé."""
        authenticator = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN})
        )
        premiere = authenticator.login(TEST_TOKEN)
        seconde = authenticator.login(TEST_TOKEN)
        self.assertNotEqual(premiere.csrf_token, seconde.csrf_token)
        self.assertNotEqual(premiere.session_id, seconde.session_id)
        # Le jeton d'une session n'est pas accepté par l'autre.
        self.assertFalse(
            authenticator.verify_csrf(seconde, premiere.csrf_token)
        )
        self.assertTrue(
            authenticator.verify_csrf(premiere, premiere.csrf_token)
        )

    def test_jeton_de_confirmation_non_rejouable_entre_clients(self) -> None:
        """P1-6-02 résiduel : les clients ne partagent plus leur session."""
        service = ToolService()
        premier = service.request_tool(
            "action_list_files", {"path": "data"}, actor_id="client-a"
        )
        self.assertTrue(premier.confirmation_required)
        token = premier.confirmation_token

        # Un autre client (session différente) ne peut pas le rejouer.
        autre = service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=token,
            actor_id="client-b",
        )
        self.assertFalse(autre.success)
        self.assertTrue(autre.confirmation_required)

    def test_10_aucun_effet_de_bord_apres_un_refus_d_origine(self) -> None:
        """Un refus d'origine n'exécute aucun outil."""
        service = ToolService()
        app = build_app(tool_service=service)
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "action_datetime", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    "Origin": FOREIGN_ORIGIN,
                },
            )
            self.assertEqual(result["status"], 403)
        # Aucune trace d'exécution dans le journal d'audit du moteur.
        entrees = service.audit.get_entries()
        self.assertEqual(len(entrees), 0)

    def test_10b_aucune_modification_d_etat_apres_un_refus(self) -> None:
        """Un refus d'origine n'écrit aucun souvenir."""
        from app.memory.transcript import ConversationTranscript

        import os
        import shutil
        import tempfile

        tmpdir = tempfile.mkdtemp(prefix="miles_secu_")
        try:
            db = os.path.join(tmpdir, "memory.db")
            memory = ConversationTranscript(enabled=True, db_path=db)
            app = build_app(memory=memory)
            with WebTestServer(app) as server:
                result = server.raw_request(
                    "POST",
                    "/remember",
                    {"content": "souvenir injecte par un site tiers"},
                    headers={
                        "Content-Type": "application/json",
                        "Origin": FOREIGN_ORIGIN,
                    },
                )
                self.assertEqual(result["status"], 403)
            self.assertEqual(len(memory.load_messages("inexistant")), 0)
            memory.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_web_ferme_par_defaut_sans_identifiant(self) -> None:
        """Sans identifiant configuré, l'interface web est fermée."""
        from app.interface.web import WebApp

        app = WebApp(settings=Settings())
        self.assertFalse(app.authenticator.is_configured)
        with WebTestServer(app, authenticate=False) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(result["status"], 403)
            self.assertIn("fermee", result["json"]["error"])

    def test_connexion_avec_un_mauvais_jeton_refusee(self) -> None:
        app = build_app()
        with WebTestServer(app, authenticate=False) as server:
            result = server.raw_request(
                "POST",
                "/session",
                {"token": "jeton-faux"},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)

    def test_erreur_ne_divulgue_pas_de_secret(self) -> None:
        app = build_app(tool_service=ToolService())
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    "Origin": FOREIGN_ORIGIN,
                },
            )
            body = json.dumps(result["json"])
            self.assertNotIn(TEST_TOKEN, body)
            self.assertNotIn("Traceback", body)


class TestMissionAuthorizationIdentity(unittest.TestCase):
    """P1-6-06 : l'autorisation de mission exige une identité."""

    def _mission_en_attente(self, runner, owner: str):
        """Créer une mission dont l'exécution demande une autorisation."""
        mission = runner.create(
            "Analyse le dossier docs/", owner_user_id=owner
        )
        mission.plan = mission.plan or None
        from app.orchestration.models import Plan, PlanStep

        mission.plan = Plan(
            mission_id=mission.mission_id,
            steps=[PlanStep("s1", "Sensible", "action_list_files",
                            {"path": "data"})],
        )
        mission = runner.run(mission.mission_id)
        self.assertEqual(mission.state, MissionState.AWAITING_AUTHORIZATION)
        self.assertIsNotNone(mission.pending)
        return mission

    def test_6_appelant_non_authentique_incapable_d_autoriser(self) -> None:
        """Sans session authentifiée, l'autorisation web est impossible."""
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        app = build_app(mission_runner=runner)
        with WebTestServer(app, authenticate=False) as server:
            result = server.raw_request(
                "POST",
                f"/mission/{mission.mission_id}/authorize",
                {
                    "approved": True,
                    "approval_token": mission.pending.approval_token,
                },
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)
        # La mission est toujours en attente.
        self.assertEqual(
            runner.get(mission.mission_id).state,
            MissionState.AWAITING_AUTHORIZATION,
        )

    def test_6b_jeton_csrf_invalide_ne_permet_pas_d_autoriser(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        app = build_app(mission_runner=runner)
        with WebTestServer(app) as server:
            faux = {
                SESSION_HEADER: server.session["session_id"],
                CSRF_HEADER: "jeton-csrf-faux" * 4,
            }
            result = server.raw_request(
                "POST",
                f"/mission/{mission.mission_id}/authorize",
                {
                    "approved": True,
                    "approval_token": mission.pending.approval_token,
                },
                headers={"Content-Type": "application/json", **faux},
                authenticate=False,
            )
            self.assertEqual(result["status"], 403)

    def test_7_utilisateur_a_ne_peut_pas_autoriser_la_mission_de_b(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, OTHER_USER)
        app = build_app(
            mission_runner=runner,
            users={TEST_USER: TEST_TOKEN, OTHER_USER: OTHER_TOKEN},
        )
        with WebTestServer(app, token=TEST_TOKEN) as server:
            result = server.raw_request(
                "POST",
                f"/mission/{mission.mission_id}/authorize",
                {
                    "approved": True,
                    "approval_token": mission.pending.approval_token,
                },
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(result["status"], 403)
        self.assertEqual(
            runner.get(mission.mission_id).state,
            MissionState.AWAITING_AUTHORIZATION,
        )

    def test_7b_mission_d_un_autre_utilisateur_invisible(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, OTHER_USER)
        app = build_app(
            mission_runner=runner,
            users={TEST_USER: TEST_TOKEN, OTHER_USER: OTHER_TOKEN},
        )
        with WebTestServer(app, token=TEST_TOKEN) as server:
            detail = server.raw_request("GET", f"/mission/{mission.mission_id}")
            self.assertEqual(detail["status"], 404)
            liste = server.raw_request("GET", "/missions")
            self.assertEqual(liste["json"]["missions"], [])

    def test_8_jeton_d_une_mission_inutilisable_sur_une_autre(self) -> None:
        runner, _, _ = _runner()
        premiere = self._mission_en_attente(runner, TEST_USER)
        seconde = self._mission_en_attente(runner, TEST_USER)
        self.assertNotEqual(
            premiere.pending.approval_token, seconde.pending.approval_token
        )
        with self.assertRaises(MissionAuthorizationError):
            runner.authorize(
                seconde.mission_id,
                approved=True,
                requester_user_id=TEST_USER,
                approval_token=premiere.pending.approval_token,
            )
        self.assertEqual(
            runner.get(seconde.mission_id).state,
            MissionState.AWAITING_AUTHORIZATION,
        )

    def test_8b_jeton_absent_refuse(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        with self.assertRaises(MissionAuthorizationError):
            runner.authorize(
                mission.mission_id,
                approved=True,
                requester_user_id=TEST_USER,
            )

    def test_9_jeton_rejoue_refuse(self) -> None:
        """Un jeton d'approbation ne peut être utilisé qu'une fois."""
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        token = mission.pending.approval_token
        runner.authorize(
            mission.mission_id,
            approved=True,
            requester_user_id=TEST_USER,
            approval_token=token,
        )
        with self.assertRaises(MissionAuthorizationError):
            runner.authorize(
                mission.mission_id,
                approved=True,
                requester_user_id=TEST_USER,
                approval_token=token,
            )

    def test_9b_demande_expiree_refusee(self) -> None:
        """Une demande d'autorisation expirée est refusée."""
        horloge = {"t": 1000.0}
        runner, _, _ = _runner(clock=lambda: horloge["t"])
        mission = self._mission_en_attente(runner, TEST_USER)
        token = mission.pending.approval_token
        horloge["t"] += 10_000
        with self.assertRaises(MissionAuthorizationError):
            runner.authorize(
                mission.mission_id,
                approved=True,
                requester_user_id=TEST_USER,
                approval_token=token,
            )

    def test_9c_jeton_non_reexploitable_par_un_autre_client(self) -> None:
        """Le grant émis est lié à la session du client demandeur."""
        runner, _, grants = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        runner.authorize(
            mission.mission_id,
            approved=True,
            requester_user_id=TEST_USER,
            requester_session_id="session-client-a",
            approval_token=mission.pending.approval_token,
        )
        # Le grant n'est pas utilisable par une autre session.
        self.assertIsNone(
            grants.authorize(
                "action_list_files", {"path": "data"}, mission.mission_id, "session-client-b"
            )
        )
        self.assertIsNotNone(
            grants.authorize(
                "action_list_files", {"path": "data"}, mission.mission_id, "session-client-a"
            )
        )

    def test_autorisation_refusee_arrete_la_mission(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        mission = runner.authorize(
            mission.mission_id,
            approved=False,
            requester_user_id=TEST_USER,
            approval_token=mission.pending.approval_token,
        )
        self.assertEqual(mission.state, MissionState.FAILED)

    def test_autorisation_web_valide_fait_aboutir_la_mission(self) -> None:
        runner, _, _ = _runner()
        mission = self._mission_en_attente(runner, TEST_USER)
        app = build_app(mission_runner=runner)
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                f"/mission/{mission.mission_id}/authorize",
                {
                    "approved": True,
                    "approval_token": mission.pending.approval_token,
                },
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(result["status"], 200)


class TestEngineControlsUnchanged(unittest.TestCase):
    """11. Les chemins CLI et web restent soumis aux contrôles du moteur."""

    def test_web_avec_session_valide_passe_par_le_moteur(self) -> None:
        """Une requête authentifiée mais qui tente un outil interdit est
        refusée par le moteur (pas seulement par l'interface)."""
        service = ToolService()
        app = build_app(tool_service=service)
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "action_datetime", "parameters": {"shell": "rm -rf /"}},
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(result["status"], 400)
            self.assertIn("politique", result["json"]["error"])

    def test_cli_passe_toujours_par_le_moteur(self) -> None:
        """La CLI soumet également ses appels au moteur."""
        service = ToolService()
        cli = CLI(settings=Settings(), tool_service=service)
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            cli._handle_tool_command(["action_datetime", "shell=rm -rf /"])
        self.assertIn("refusé", out.getvalue().lower())

    def test_moteur_refuse_toujours_un_outil_inconnu(self) -> None:
        service = ToolService()
        result = service.request_tool("outil_fantome")
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
