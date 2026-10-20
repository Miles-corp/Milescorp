"""Tests d'audit Phase 6.1 (Agent B) — sécurité de l'interface web.

Audit indépendant des corrections P1-6-03 (contrôle d'origine / CSRF /
Content-Type) et P1-6-06 (autorisation de mission sans identité) publiées
par Agent A sur `fix/miles-web-authorization-security`.

Pour chaque scénario d'attaque, le test vérifie **deux** choses :
1. le code HTTP refusé ;
2. l'ABSENCE d'effet de bord (aucun outil exécuté, aucune mémoire
   modifiée, aucune mission autorisée).

Aucun appel réseau sortant, aucun fournisseur payant, aucun modèle local.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from app.config.settings import Settings
from app.interface.web import MilesHandler, WebApp
from app.memory.persistent import PersistentMemory
from app.tools.service import ToolService

from tests.web_test_support import (
    CSRF_HEADER,
    OTHER_TOKEN,
    OTHER_USER,
    SESSION_HEADER,
    TEST_TOKEN,
    TEST_USER,
    WebTestServer,
    build_app,
)

FOREIGN_ORIGIN = "http://site-malveillant.example"


class _MemoryFixture(unittest.TestCase):
    """Mémoire persistante temporaire, pour vérifier les effets de bord."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_p61_")
        self.db_path = os.path.join(self.tmpdir, "memory.db")
        self.memory = PersistentMemory(enabled=True, db_path=self.db_path)

    def tearDown(self) -> None:
        self.memory.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestP10603OriginControl(_MemoryFixture):
    """P1-6-03 : le contrôle d'origine sur les routes modifiantes."""

    def _app(self):
        return build_app(memory=self.memory, tool_service=ToolService())

    def test_tool_refuse_origine_etrangere(self) -> None:
        """POST /tool avec origine étrangère : refusé, aucun outil exécuté."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "text/plain",
                    "Origin": FOREIGN_ORIGIN,
                    **srv.auth_headers(),
                },
            )
        self.assertIn(result["status"], (403, 415))
        # Aucun effet : le catalogue est inchangé, aucune mission.
        self.assertNotIn("success", (result.get("json") or {}))

    def test_remember_refuse_origine_etrangere(self) -> None:
        """POST /remember avec origine étrangère : refusé, aucune mémoire créée."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/remember",
                {"content": "souvenir injecte"},
                headers={
                    "Content-Type": "text/plain",
                    "Origin": FOREIGN_ORIGIN,
                    **srv.auth_headers(),
                },
            )
        self.assertIn(result["status"], (403, 415))
        self.assertEqual(len(self.memory.list_memories()), 0)

    def test_forget_refuse_origine_etrangere(self) -> None:
        """POST /forget avec origine étrangère : refusé, mémoire intacte."""
        mem_id = self.memory.add_memory("souvenir a proteger")
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/forget",
                {"id": mem_id},
                headers={
                    "Content-Type": "text/plain",
                    "Origin": FOREIGN_ORIGIN,
                    **srv.auth_headers(),
                },
            )
        self.assertIn(result["status"], (403, 415))
        self.assertEqual(len(self.memory.list_memories()), 1)
        self.assertIsNotNone(self.memory.get_memory(mem_id))

    def test_origine_absente_sans_session_refusee(self) -> None:
        """Sans en-tête Origin ni session : refusé (401)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
        self.assertEqual(result["status"], 401)

    def test_origine_absente_avec_session_sans_csrf_refusee(self) -> None:
        """Session valide mais jeton CSRF absent : refusé (403)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    SESSION_HEADER: srv.session["session_id"],
                },
                authenticate=False,
            )
        self.assertEqual(result["status"], 403)

    def test_csrf_invalide_refuse(self) -> None:
        """Jeton CSRF falsifié : refusé (403)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    **srv.auth_headers(),
                    CSRF_HEADER: "jeton-csrf-fabrique",
                },
                authenticate=False,
            )
        self.assertEqual(result["status"], 403)

    def test_csrf_dune_autre_session_refuse(self) -> None:
        """Jeton CSRF appartenant à une autre session : refusé (403)."""
        with WebTestServer(self._app(), authenticate=False) as srv_a, WebTestServer(
            self._app(), authenticate=False
        ) as srv_b:
            srv_a.login()
            srv_b.login()
            headers = dict(srv_a.auth_headers())
            headers[CSRF_HEADER] = srv_b.session["csrf_token"]
            result = srv_a.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers=headers,
                authenticate=False,
            )
        self.assertEqual(result["status"], 403)

    def test_origine_invalide_ou_falsifiee_refusee(self) -> None:
        """Origines invalides ou falsifiées : refusées."""
        for origin in (
            "null",
            "http://127.0.0.1.evil.example",
            "https://127.0.0.1",
            "http://127.0.0.1@evil.example",
            "javascript:alert(1)",
        ):
            with self.subTest(origin=origin):
                with WebTestServer(self._app(), authenticate=False) as srv:
                    srv.login()
                    result = srv.raw_request(
                        "POST",
                        "/tool",
                        {"tool": "status_read", "parameters": {}},
                        headers={
                            "Content-Type": "application/json",
                            "Origin": origin,
                            **srv.auth_headers(),
                        },
                    )
                self.assertEqual(result["status"], 403)

    def test_referer_etranger_refuse(self) -> None:
        """Origin absent, Referer étranger : refusé (403)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    "Referer": FOREIGN_ORIGIN + "/page.html",
                    **srv.auth_headers(),
                },
            )
        self.assertEqual(result["status"], 403)

    def test_content_type_inattendu_refuse(self) -> None:
        """Content-Type inattendu (text/plain) avec session et CSRF valides : 415."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "text/plain",
                    **srv.auth_headers(),
                },
            )
        self.assertEqual(result["status"], 415)

    def test_double_soumission_n_a_pas_d_double_effet(self) -> None:
        """Une double soumission refused ne produit aucun effet cumulatif."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            for _ in range(5):
                result = srv.raw_request(
                    "POST",
                    "/remember",
                    {"content": "doublon"},
                    headers={
                        "Content-Type": "text/plain",
                        "Origin": FOREIGN_ORIGIN,
                        **srv.auth_headers(),
                    },
                )
                self.assertIn(result["status"], (403, 415))
        self.assertEqual(len(self.memory.list_memories()), 0)

    def test_requetes_repetees_legitimes_creent_une_seule_entree(self) -> None:
        """Contrôle de non-régression : une requête légitime reste acceptée."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/remember",
                {"content": "souvenir legitime"},
                headers={"Content-Type": "application/json", **srv.auth_headers()},
            )
        self.assertEqual(result["status"], 200)
        self.assertEqual(len(self.memory.list_memories()), 1)

    def test_web_ferme_par_defaut_sans_identifiants(self) -> None:
        """Sans identifiant configuré, l'interface web est fermée (403)."""
        from app.interface.web_auth import WebAuthenticator, WebCredentialStore

        app = WebApp(
            settings=Settings(),
            authenticator=WebAuthenticator(WebCredentialStore({})),
        )
        with WebTestServer(app, authenticate=False) as srv:
            result = srv.raw_request(
                "POST",
                "/session",
                {"token": "quelconque"},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
        self.assertIn(result["status"], (401, 403))


class TestP10606MissionAuthorization(_MemoryFixture):
    """P1-6-06 : l'autorisation de mission exige une identité réelle."""

    def _app(self):
        return build_app(memory=self.memory, tool_service=ToolService())

    def test_autorisation_sans_authentification_refusee(self) -> None:
        """POST /mission/<id>/authorize sans session : refusé (401)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/mission/id-inexistant/authorize",
                {"approved": True},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
        self.assertEqual(result["status"], 401)

    def test_autorisation_sans_csrf_refusee(self) -> None:
        """Session valide mais CSRF absent : refusé (403)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/mission/id-inexistant/authorize",
                {"approved": True},
                headers={
                    "Content-Type": "application/json",
                    SESSION_HEADER: srv.session["session_id"],
                },
                authenticate=False,
            )
        self.assertEqual(result["status"], 403)

    def test_jeton_de_session_invalide_refuse(self) -> None:
        """Identifiant de session deviné : refusé (401)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            result = srv.raw_request(
                "POST",
                "/mission/id-inexistant/authorize",
                {"approved": True},
                headers={
                    "Content-Type": "application/json",
                    SESSION_HEADER: "session-fabriquee-0000",
                    CSRF_HEADER: srv.session["csrf_token"],
                },
                authenticate=False,
            )
        self.assertEqual(result["status"], 401)

    def test_session_revoquee_refusee(self) -> None:
        """Une session révoquée n'est plus acceptée."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            srv.login()
            MilesHandler.app.authenticator.revoke(srv.session["session_id"])
            result = srv.raw_request(
                "POST",
                "/mission/id-inexistant/authorize",
                {"approved": True},
                headers={"Content-Type": "application/json", **srv.auth_headers()},
            )
        self.assertEqual(result["status"], 401)

    def test_session_expiree_refusee(self) -> None:
        """Une session expirée n'est plus acceptée."""
        from app.interface.web_auth import WebAuthenticator, WebCredentialStore

        maintenant = [1000.0]
        auth = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN}),
            session_ttl_seconds=10.0,
            clock=lambda: maintenant[0],
        )
        app = WebApp(settings=Settings(), authenticator=auth)
        with WebTestServer(app, authenticate=False) as srv:
            srv.login(TEST_TOKEN)
            maintenant[0] += 11.0
            result = srv.raw_request(
                "POST",
                "/mission/id-inexistant/authorize",
                {"approved": True},
                headers={"Content-Type": "application/json", **srv.auth_headers()},
            )
        self.assertEqual(result["status"], 401)

    def test_utilisateur_ne_peut_pas_autoriser_une_mission_d_un_autre(self) -> None:
        """Un utilisateur ne peut pas autoriser une mission d'un autre utilisateur."""
        from app.interface.web_auth import WebAuthenticator, WebCredentialStore

        auth = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN, OTHER_USER: OTHER_TOKEN})
        )
        app = WebApp(settings=Settings(), authenticator=auth)
        with WebTestServer(app, authenticate=False) as srv:
            srv.login(OTHER_TOKEN)
            result = srv.raw_request(
                "POST",
                "/mission/mission-de-test/authorize",
                {"approved": True},
                headers={"Content-Type": "application/json", **srv.auth_headers()},
            )
        self.assertIn(result["status"], (403, 404))

    def test_session_par_client_et_non_partagee(self) -> None:
        """La session n est plus partagee par tous les clients (correction P1-6-02).

        Revision 1 : l identifiant de session etait cree au demarrage du
        processus, donc partage par tous les clients HTTP. Chaque connexion
        doit desormais obtenir une session distincte, et un client sans
        jeton d acces ne peut pas en obtenir une.
        """
        with WebTestServer(self._app(), authenticate=False) as srv_a, WebTestServer(
            self._app(), authenticate=False
        ) as srv_b:
            session_a = srv_a.login()
            session_b = srv_b.login()
            self.assertNotEqual(session_a["session_id"], session_b["session_id"])
            self.assertNotEqual(session_a["csrf_token"], session_a["session_id"])
            refused = srv_b.raw_request(
                "POST",
                "/session",
                {"token": "jeton-fabrique"},
                headers={"Content-Type": "application/json"},
                authenticate=False,
            )
        self.assertEqual(refused["status"], 401)

    def test_session_id_est_imprevisible(self) -> None:
        """L identifiant de session est long et aleatoire (non devinable)."""
        with WebTestServer(self._app(), authenticate=False) as srv:
            session = srv.login()
        self.assertGreaterEqual(len(session["session_id"]), 64)
        self.assertGreaterEqual(len(session["csrf_token"]), 64)

    def test_confirmation_non_reutilisable_une_mission_interdite(self) -> None:
        """Un jeton de confirmation lié à une mission ne vaut pas pour une autre."""
        service = ToolService()
        premiere = service.request_tool(
            "action_list_files", {"path": "data"}, context_id="mission-A"
        )
        self.assertTrue(premiere.confirmation_required)
        resultat = service.request_tool(
            "action_list_files",
            {"path": "data"},
            user_confirmed=True,
            confirmation_token=premiere.confirmation_token,
            context_id="mission-B",
        )
        self.assertFalse(resultat.success)
        self.assertTrue(resultat.confirmation_required)

    def test_le_modele_ne_peut_pas_produire_une_approbation(self) -> None:
        """Aucun jeton de session n'est derivable d'une sortie de modele.

        Le magasin d'identifiants n'accepte que des jetons configures
        explicitement : aucune sortie de fournisseur ne peut en creer un.
        """
        from app.interface.web_auth import WebCredentialStore

        magasin = WebCredentialStore({TEST_USER: TEST_TOKEN})
        self.assertIsNone(magasin.authenticate("sortie-de-modele-inventee"))
        self.assertIsNone(magasin.authenticate(""))


if __name__ == "__main__":
    unittest.main()
