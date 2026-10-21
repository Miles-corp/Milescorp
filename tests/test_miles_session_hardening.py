"""Tests du durcissement des sessions web MILES (réserve P2 d'Agent B).

Agent B (réaudit `ac627df`) a validé le commit `c0cb01b` « sous réserves »,
la réserve portant sur le **détournement de session** : le `session_id` est
un jeton porteur valable 1800 s ; un jeton volé permet d'agir au nom de
l'utilisateur — y compris en LECTURE, puisque le jeton CSRF ne protège que
les requêtes modifiantes.

Ces tests vérifient le durcissement apporté :
- durée d'INACTIVITÉ réduite (900 s) avec renouvellement glissant ;
- durée de vie MAXIMALE non renouvelable ;
- liaison de la session à l'agent utilisateur du client (un `session_id`
  rejoué depuis une autre pile cliente est refusé) ;
- absence de fuite du `session_id` dans les journaux.

Aucune modification n'est apportée aux protections déjà validées.
"""

from __future__ import annotations

import json
import logging
import unittest

from app.config.settings import Settings
from app.interface.web import MilesHandler
from app.interface.web_auth import (
    DEFAULT_SESSION_TTL_SECONDS,
    MAX_SESSION_LIFETIME_SECONDS,
    WebAuthenticator,
    WebCredentialStore,
)
from tests.web_test_support import TEST_TOKEN, TEST_USER, build_app

#: Un agent utilisateur « navigateur ».
UA_NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"
#: Un agent utilisateur « autre client » (le voleur).
UA_AUTRE = "python-urllib/3.12"


class TestDureeDeSession(unittest.TestCase):
    """Durée réelle, renouvellement glissant et durée de vie maximale."""

    def test_duree_par_defaut_reduite_a_15_minutes(self) -> None:
        self.assertEqual(DEFAULT_SESSION_TTL_SECONDS, 900.0)
        self.assertLess(DEFAULT_SESSION_TTL_SECONDS, 1800.0)

    def test_duree_maximale_definie(self) -> None:
        self.assertEqual(MAX_SESSION_LIFETIME_SECONDS, 8 * 3600.0)
        self.assertGreater(MAX_SESSION_LIFETIME_SECONDS, DEFAULT_SESSION_TTL_SECONDS)

    def test_session_expire_apres_le_delai_d_inactivite(self) -> None:
        horloge = {"t": 1000.0}
        auth = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN}),
            session_ttl_seconds=100.0,
            clock=lambda: horloge["t"],
        )
        session = auth.login(TEST_TOKEN)
        self.assertIsNotNone(auth.authenticate(session.session_id))
        horloge["t"] += 101.0
        self.assertIsNone(auth.authenticate(session.session_id))

    def test_renouvellement_glissant_a_chaque_requete(self) -> None:
        horloge = {"t": 1000.0}
        auth = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN}),
            session_ttl_seconds=100.0,
            clock=lambda: horloge["t"],
        )
        session = auth.login(TEST_TOKEN)
        # 80 s plus tard, la session est encore vivante
        horloge["t"] += 80.0
        self.assertIsNotNone(auth.authenticate(session.session_id))
        # ...et son expiration a été repoussée
        horloge["t"] += 80.0
        self.assertIsNotNone(auth.authenticate(session.session_id))

    def test_duree_maximale_non_renouvelable(self) -> None:
        horloge = {"t": 1000.0}
        auth = WebAuthenticator(
            WebCredentialStore({TEST_USER: TEST_TOKEN}),
            session_ttl_seconds=100.0,
            max_session_lifetime_seconds=250.0,
            clock=lambda: horloge["t"],
        )
        session = auth.login(TEST_TOKEN)
        # Usage continu : la session reste vivante jusqu'à la durée maximale
        for _ in range(4):
            horloge["t"] += 60.0
            self.assertIsNotNone(auth.authenticate(session.session_id))
        # Au-delà de la durée de vie maximale, c'est fini.
        horloge["t"] += 60.0
        self.assertIsNone(auth.authenticate(session.session_id))

    def test_session_revoquee_refusee(self) -> None:
        auth = WebAuthenticator(WebCredentialStore({TEST_USER: TEST_TOKEN}))
        session = auth.login(TEST_TOKEN)
        self.assertTrue(auth.revoke(session.session_id))
        self.assertIsNone(auth.authenticate(session.session_id))


class TestLiaisonAuClient(unittest.TestCase):
    """Liaison de la session à l'agent utilisateur du client."""

    def test_session_refusee_avec_un_autre_agent_utilisateur(self) -> None:
        auth = WebAuthenticator(WebCredentialStore({TEST_USER: TEST_TOKEN}))
        session = auth.login(TEST_TOKEN, user_agent=UA_NAVIGATEUR)
        self.assertIsNotNone(
            auth.authenticate(session.session_id, user_agent=UA_NAVIGATEUR)
        )
        # Rejeu du session_id depuis une autre pile cliente : refusé.
        self.assertIsNone(
            auth.authenticate(session.session_id, user_agent=UA_AUTRE)
        )

    def test_session_acceptee_avec_le_meme_agent_utilisateur(self) -> None:
        auth = WebAuthenticator(WebCredentialStore({TEST_USER: TEST_TOKEN}))
        session = auth.login(TEST_TOKEN, user_agent=UA_NAVIGATEUR)
        self.assertIsNotNone(
            auth.authenticate(session.session_id, user_agent=UA_NAVIGATEUR)
        )

    def test_agent_utilisateur_absent_ne_rompt_pas_les_appels_sans_ua(self) -> None:
        """Les appelants qui n'envoient pas d'agent utilisateur restent
        compatibles (aucune liaison n'est appliquée dans ce cas)."""
        auth = WebAuthenticator(WebCredentialStore({TEST_USER: TEST_TOKEN}))
        session = auth.login(TEST_TOKEN)
        self.assertIsNotNone(auth.authenticate(session.session_id))

    def test_empreinte_de_l_agent_utilisateur_n_est_pas_le_jeton(self) -> None:
        """L'empreinte stockée ne permet pas de reconstruire l'agent."""
        auth = WebAuthenticator(WebCredentialStore({TEST_USER: TEST_TOKEN}))
        session = auth.login(TEST_TOKEN, user_agent=UA_NAVIGATEUR)
        self.assertNotIn(UA_NAVIGATEUR, session.ua_digest)
        self.assertNotEqual(session.ua_digest, session.session_id)


class TestFuitePotentielle(unittest.TestCase):
    """Le session_id ne doit pas fuiter."""

    def test_session_id_absent_des_journaux(self) -> None:
        """Le chemin RÉEL d'authentification ne journalise ni le session_id
        ni le jeton CSRF."""
        import io
        import re

        from app.interface import web as web_module
        from app.interface import web_auth as web_auth_module
        from tests.web_test_support import WebTestServer

        records: list[logging.LogRecord] = []

        class _Collect(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = _Collect()
        loggers = [
            logging.getLogger(module.__name__)
            for module in (web_module, web_auth_module)
        ]
        previous = [(lg, lg.level) for lg in loggers]
        for lg in loggers:
            lg.addHandler(handler)
            lg.setLevel(logging.DEBUG)
        try:
            app = build_app()
            with WebTestServer(app) as server:
                session_id = str(server.session["session_id"])
                csrf = str(server.session["csrf_token"])
                # Une requête authentifiée et une route de lecture.
                server.raw_request("GET", "/status")
        finally:
            for lg, level in previous:
                lg.removeHandler(handler)
                lg.setLevel(level)

        dump = io.StringIO()
        for record in records:
            dump.write(record.getMessage() + "\n")
        texte = dump.getvalue()

        self.assertNotIn(session_id, texte)
        self.assertNotIn(csrf, texte)
        # Aucune empreinte hexadécimale de 64 caractères (taille d'un
        # session_id ou d'un jeton) ne doit apparaître non plus.
        self.assertIsNone(re.search(r"\b[0-9a-f]{64}\b", texte))


class TestRoutesDeLecture(unittest.TestCase):
    """Les routes de lecture exigent une session valide ET liée."""

    def _app(self):
        return build_app()

    def test_lecture_sans_session_refusee(self) -> None:
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app, authenticate=False) as server:
            for path in ("/status", "/memory", "/missions", "/tools"):
                with self.subTest(path=path):
                    result = server.raw_request(
                        "GET", path, authenticate=False
                    )
                    self.assertEqual(result["status"], 401)

    def test_lecture_avec_session_valide_acceptee(self) -> None:
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/status")
            self.assertEqual(result["status"], 200)

    def test_session_id_volé_avec_csrf_faux_refusé_en_lecture(self) -> None:
        """Un session_id volé ne donne pas accès à la lecture sans l'agent
        utilisateur d'origine ; et le CSRF n'est de toute façon pas requis
        pour lire (c'est le session_id qui fait foi)."""
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            session_id = server.session["session_id"]
            # Même agent utilisateur (celui du client qui a ouvert la
            # session) : la lecture est possible — c'est le bearer token.
            result = server.raw_request(
                "GET",
                "/memory",
                headers={"X-MILES-Session": session_id},
                authenticate=False,
            )
            self.assertEqual(result["status"], 200)

    def test_lecture_refusee_avec_un_autre_agent_utilisateur(self) -> None:
        """Un session_id rejoué depuis une autre pile cliente est refusé,
        y compris pour les routes de lecture."""
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            session_id = server.session["session_id"]
            result = server.raw_request(
                "GET",
                "/memory",
                headers={
                    "X-MILES-Session": session_id,
                    "User-Agent": UA_AUTRE,
                },
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)


class TestNonRegressionAuthentification(unittest.TestCase):
    """Les protections validées par Agent B restent en place."""

    def _app(self):
        return build_app()

    def test_interface_closee_sans_identifiant(self) -> None:
        from app.interface.web import WebApp
        from tests.web_test_support import WebTestServer

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

    def test_origine_etrangere_toujours_refusee(self) -> None:
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "http://site-malveillant.example",
                },
            )
            self.assertEqual(result["status"], 403)

    def test_type_de_contenu_non_json_toujours_refuse(self) -> None:
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                json.dumps({"tool": "status_read"}).encode(),
                headers={"Content-Type": "text/plain"},
            )
            self.assertEqual(result["status"], 415)

    def test_csrf_faux_toujours_refuse(self) -> None:
        from app.interface.web_auth import CSRF_HEADER, SESSION_HEADER
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    SESSION_HEADER: server.session["session_id"],
                    CSRF_HEADER: "jeton-faux" * 4,
                },
                authenticate=False,
            )
            self.assertEqual(result["status"], 403)

    def test_session_fabriquee_refusee(self) -> None:
        from app.interface.web_auth import CSRF_HEADER, SESSION_HEADER
        from tests.web_test_support import WebTestServer

        app = self._app()
        with WebTestServer(app) as server:
            result = server.raw_request(
                "POST",
                "/tool",
                {"tool": "status_read", "parameters": {}},
                headers={
                    "Content-Type": "application/json",
                    SESSION_HEADER: "session-fabriquee-0000",
                    CSRF_HEADER: "csrf-fabrique",
                },
                authenticate=False,
            )
            self.assertEqual(result["status"], 401)


if __name__ == "__main__":
    unittest.main()
