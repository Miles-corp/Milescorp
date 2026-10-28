"""Ouverture réseau opt-in (`--web-lan`) : refus par défaut, preuve du refus.

DEC-016 §2 : l'écoute sur le réseau local est un choix explicite, refusé au
démarrage tant que les deux conditions ne sont pas réunies — un jeton porteur
**persistant** et une adresse **privée** nommée. Le défaut reste `127.0.0.1`.

Ces tests prouvent trois choses distinctes :

- le défaut n'a pas bougé (aucune régression : sans `--web-lan`, rien ne
  change et le serveur reste local) ;
- chaque condition manquante provoque un refus **au démarrage**, code de
  sortie 1, sans qu'aucun serveur ne soit construit ;
- le cas complet est accepté, et l'adresse retenue est bien celle demandée.

Aucune socket d'écoute n'est ouverte par ces tests : on vérifie la décision,
pas le trafic.
"""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import miles
from app.config.settings import Settings
from app.interface.web import (
    LAN_HOST_ENV,
    LOCAL_ONLY_HOST,
    MilesWebServer,
    WebServerSecurityError,
    assert_listen_host,
)
from tests.web_test_support import build_app

TOKEN = "jeton-porteur-de-test-0123456789"


def _sans_variables_web() -> dict[str, str]:
    """Environnement nettoyé des variables qui décideraient du mode d'écoute."""
    return {
        cle: valeur
        for cle, valeur in os.environ.items()
        if cle
        not in (
            "MILES_WEB_AUTH_TOKEN",
            "MILES_WEB_USERS_FILE",
            LAN_HOST_ENV,
            "MILES_WEB_LAN",
        )
    }


class TestRefusSansCondition(unittest.TestCase):
    """Le démarrage échoue, et aucun serveur n'est construit."""

    def _main(self, argv: list[str], env: dict[str, str]) -> tuple[int, str]:
        sortie = io.StringIO()
        with patch.dict(os.environ, env, clear=True):
            with patch.object(miles, "_build_transcript", return_value=None):
                # Preuve : si le serveur était construit, le test échouerait.
                with patch.object(
                    miles,
                    "MilesWebServer",
                    side_effect=AssertionError("serveur construit malgré le refus"),
                ):
                    with redirect_stderr(sortie):
                        try:
                            code = miles.main(argv)
                        except AssertionError as exc:  # pragma: no cover
                            self.fail(str(exc))
        return code, sortie.getvalue()

    def test_refus_sans_jeton_porteur(self) -> None:
        """Sans jeton configuré, `--web-lan` est refusé (DEC-016 §2)."""
        env = _sans_variables_web()
        env[LAN_HOST_ENV] = "192.168.1.42"
        code, erreur = self._main(["--web", "--web-lan"], env)
        self.assertEqual(code, 1)
        self.assertIn("--web-lan", erreur)
        self.assertIn("MILES_WEB_AUTH_TOKEN", erreur)

    def test_refus_sans_adresse_privee(self) -> None:
        """Avec un jeton mais sans adresse nommée, le démarrage est refusé."""
        env = _sans_variables_web()
        env["MILES_WEB_AUTH_TOKEN"] = TOKEN
        code, erreur = self._main(["--web", "--web-lan"], env)
        self.assertEqual(code, 1)
        self.assertIn(LAN_HOST_ENV, erreur)

    def test_refus_adresse_publique(self) -> None:
        env = _sans_variables_web()
        env["MILES_WEB_AUTH_TOKEN"] = TOKEN
        env[LAN_HOST_ENV] = "8.8.8.8"
        code, erreur = self._main(["--web", "--web-lan"], env)
        self.assertEqual(code, 1)
        self.assertIn("privée", erreur)

    def test_refus_toutes_interfaces(self) -> None:
        env = _sans_variables_web()
        env["MILES_WEB_AUTH_TOKEN"] = TOKEN
        env[LAN_HOST_ENV] = "0.0.0.0"
        code, erreur = self._main(["--web", "--web-lan"], env)
        self.assertEqual(code, 1)
        self.assertIn("toutes les interfaces", erreur)

    def test_refus_sans_option_web(self) -> None:
        """`--web-lan` seul n'ouvre rien : il n'a de sens qu'avec `--web`."""
        code, erreur = self._main(["--web-lan"], _sans_variables_web())
        self.assertEqual(code, 1)
        self.assertIn("--web", erreur)


class TestConditionsReunies(unittest.TestCase):
    """Avec jeton persistant et adresse privée, l'ouverture est acceptée."""

    def _settings(self, env: dict[str, str]) -> Settings:
        with patch.dict(os.environ, env, clear=True):
            return Settings()

    def test_conditions_reunies_ne_sont_pas_refusees(self) -> None:
        env = _sans_variables_web()
        env["MILES_WEB_AUTH_TOKEN"] = TOKEN
        env[LAN_HOST_ENV] = "192.168.1.42"
        settings = self._settings(env)
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(miles._lan_refusal_reason(settings))

    def test_adresse_retenue_est_celle_demandee(self) -> None:
        self.assertEqual(
            assert_listen_host("192.168.1.42", allow_lan=True), "192.168.1.42"
        )

    def test_jeton_ephemere_ne_suffit_pas(self) -> None:
        """`--web-lan` exige un jeton persistant, pas un jeton d'un seul lancement."""
        env = _sans_variables_web()
        env[LAN_HOST_ENV] = "192.168.1.42"
        settings = self._settings(env)
        with patch.dict(os.environ, env, clear=False):
            motif = miles._lan_refusal_reason(settings)
        self.assertIsNotNone(motif)
        self.assertIn("MILES_WEB_AUTH_TOKEN", motif or "")


class TestDefautInchange(unittest.TestCase):
    """Aucune régression : sans opt-in, le serveur reste strictement local."""

    def test_serveur_par_defaut_reste_local(self) -> None:
        server = MilesWebServer(app=build_app(settings=Settings()))
        self.assertEqual(server.host, LOCAL_ONLY_HOST)
        self.assertFalse(server.allow_lan)

    def test_garde_locale_inchangee(self) -> None:
        with self.assertRaises(WebServerSecurityError):
            assert_listen_host("192.168.1.42")
        self.assertEqual(assert_listen_host(LOCAL_ONLY_HOST), LOCAL_ONLY_HOST)


if __name__ == "__main__":
    unittest.main()
