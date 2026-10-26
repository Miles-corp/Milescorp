"""Tests de POST /configure - connexion rapide IA (S6 web, niveau 4).

Invariants : authentification exigee, liste blanche fournisseurs, cle
refusee si invalide, ecriture .env atomique, ET aucune cle jamais
retournee dans la reponse.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.config.settings import Settings
from tests.web_test_support import WebTestServer, build_app

CLE = "groq-cle-test-123456"


class TestConfigureRoute(unittest.TestCase):
    def _server(self):
        return WebTestServer(build_app(settings=Settings()))

    def test_configure_valide_ecrit_env_sans_rendre_cle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with patch.dict(os.environ, {"MILES_ENV_FILE": env_path}):
                with self._server() as server:
                    r = server.raw_request(
                        "POST", "/configure",
                        {"provider": "groq", "api_key": CLE},
                    )
            self.assertEqual(r["status"], 200)
            payload = r["json"]
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["restart_required"])
            self.assertNotIn(CLE, r.get("body") or "")
            contenu = open(env_path, encoding="utf-8").read()
            self.assertIn("MILES_REMOTE_API_KEY=" + CLE, contenu)
            self.assertIn("MILES_API_KEY_GROQ=" + CLE, contenu)
            self.assertIn("MILES_PROVIDER=remote", contenu)

    def test_fournisseur_hors_liste_blanchie_refuse(self) -> None:
        with self._server() as server:
            r = server.raw_request(
                "POST", "/configure",
                {"provider": "autre", "api_key": CLE},
            )
        self.assertEqual(r["status"], 400)
        self.assertIn("choix", r["json"])

    def test_cle_vide_ou_dangereuse_refusee(self) -> None:
        for mauvaise in ("", 'avec"guillemet', "avec\\antislash", "avec\nsaut"):
            with self.subTest(cle=repr(mauvaise)):
                with self._server() as server:
                    r = server.raw_request(
                        "POST", "/configure",
                        {"provider": "gemini", "api_key": mauvaise},
                    )
                self.assertEqual(r["status"], 400)

    def test_configure_exige_session(self) -> None:
        with self._server() as server:
            r = server.raw_request(
                "POST", "/configure",
                {"provider": "groq", "api_key": CLE},
                authenticate=False,
            )
        self.assertEqual(r["status"], 401)


if __name__ == "__main__":
    unittest.main()
