"""Tests /status et /provider (CLI et web) : aucun appel reseau implicite.

Invariants du rendez-vous de correction :

- la disponibilite du fournisseur est INCONNUE tant qu'aucun controle
  explicite n'a ete execute ;
- is_available() n'est jamais appele par une commande d'affichage
  (aucune requete reseau implicite, en particulier pour un fournisseur
  local) ;
- la configuration affichee (mode, URL de base, modele) n'expose
  aucun secret (cles API jamais incluses) ;
- la route web GET /provider suit la protection de session des autres
  routes de consultation.
"""

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app.config.settings import Settings
from app.interface.cli import CLI
from app.utilities.redaction import sanitize_text
from tests.web_test_support import build_app, WebTestServer

SECRET_REMOTE = "cle-api-distance-tres-secrete-1657"
SECRET_LOCAL = "cle-api-locale-tres-secrete-1657"


class SpyProvider:
    """Fournisseur espion : is_available() doit rester appele zero fois."""

    def __init__(self, name: str = "fournisseur-espion") -> None:
        self._name = name
        self.is_available_calls = 0

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        self.is_available_calls += 1
        raise AssertionError(
            "is_available() ne doit pas etre appele par une commande "
            "d'affichage (aucune requete reseau implicite)."
        )

    def chat(self, messages: list[dict[str, str]]) -> str:
        return "reponse simulee"


class StubSettings:
    """Jeu de configuration minimal : cle utile absente -> get() = None.

    Les autres cles retournent la valeur par defaut transmise, comme le
    vrai Settings, pour ne pas casser la construction du CLI.
    """

    provider = "remote"

    def get(self, key: str, default=None):
        if key in ("remote_base_url", "remote_model"):
            return None
        return default


def _capture(cli: CLI, command: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli._handle_command(command)
    return buffer.getvalue()


class TestCLINoImplicitNetwork(unittest.TestCase):
    """Aucune commande d'affichage ne doit tester la disponibilite."""

    def setUp(self) -> None:
        self.cli = CLI(settings=Settings(), provider=SpyProvider())

    def test_status_never_calls_is_available(self) -> None:
        output = _capture(self.cli, "/status")
        self.assertEqual(self.cli.provider.is_available_calls, 0)
        self.assertIn("Disponibilite : non testee", output)

    def test_provider_never_calls_is_available(self) -> None:
        output = _capture(self.cli, "/provider")
        self.assertEqual(self.cli.provider.is_available_calls, 0)
        self.assertIn("Disponibilite : inconnue", output)


class TestCLIStatus(unittest.TestCase):
    def test_status_without_provider(self) -> None:
        cli = CLI(settings=Settings(), provider=None)
        output = _capture(cli, "/status")
        self.assertIn("Fournisseur : non configure", output)

    def test_status_shows_provider_name_and_mode(self) -> None:
        cli = CLI(settings=Settings(), provider=SpyProvider())
        output = _capture(cli, "/status")
        self.assertIn("Fournisseur : fournisseur-espion", output)
        self.assertIn("Mode : remote", output)


class TestCLIProvider(unittest.TestCase):
    def test_provider_without_provider_object(self) -> None:
        cli = CLI(settings=Settings(), provider=None)
        output = _capture(cli, "/provider")
        self.assertIn("Fournisseur courant : non configure", output)
        self.assertIn("Mode : aucun", output)
        self.assertIn("URL de base : (aucune)", output)

    def test_provider_remote_configuration(self) -> None:
        cli = CLI(settings=Settings(), provider=SpyProvider())
        output = _capture(cli, "/provider")
        self.assertIn("Mode : remote", output)
        self.assertIn("URL de base : http://localhost:8000", output)
        self.assertIn("Modele : miles-default", output)

    def test_provider_local_configuration(self) -> None:
        settings = Settings()
        settings.provider = "local"
        cli = CLI(settings=settings, provider=SpyProvider("fournisseur-local"))
        output = _capture(cli, "/provider")
        self.assertIn("Mode : local", output)
        self.assertIn("URL de base : http://localhost:11434", output)
        self.assertIn("Modele : miles-local", output)

    def test_provider_with_missing_configuration_keys(self) -> None:
        cli = CLI(settings=StubSettings(), provider=SpyProvider())
        output = _capture(cli, "/provider")
        self.assertIn("Fournisseur courant : fournisseur-espion", output)
        self.assertIn("URL de base : None", output)
        self.assertIn("Modele : None", output)

    def test_provider_invalid_mode_rejected_by_settings(self) -> None:
        settings = Settings()
        with self.assertRaises(Exception):
            settings.provider = "invalide"


class TestCLISecretFiltering(unittest.TestCase):
    """Aucune commande d'affichage ne doit divulguer une clee API."""

    def test_provider_and_status_hide_api_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MILES_REMOTE_API_KEY": SECRET_REMOTE,
                "MILES_LOCAL_API_KEY": SECRET_LOCAL,
            },
        ):
            settings = Settings()
        cli = CLI(settings=settings, provider=SpyProvider())
        provider_output = _capture(cli, "/provider")
        status_output = _capture(cli, "/status")
        for output in (provider_output, status_output):
            self.assertNotIn(SECRET_REMOTE, output)
            self.assertNotIn(SECRET_LOCAL, output)

    def test_sanitize_text_keeps_normal_url_intact(self) -> None:
        self.assertEqual(
            sanitize_text("http://localhost:8000"), "http://localhost:8000"
        )


class TestWebProviderRoute(unittest.TestCase):
    """Route GET /provider : config lisible, sessions protegees."""

    def test_provider_route_returns_provider_state(self) -> None:
        app = build_app(settings=Settings(), provider=SpyProvider("web-espion"))
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/provider")
            self.assertEqual(result["status"], 200)
            payload = result["json"]
            self.assertEqual(payload["name"], "web-espion")
            self.assertEqual(payload["mode"], "remote")
            self.assertEqual(payload["base_url"], "http://localhost:8000")
            self.assertEqual(payload["model"], "miles-default")
            self.assertIsNone(payload["available"])

    def test_provider_route_requires_session(self) -> None:
        app = build_app(settings=Settings())
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/provider", authenticate=False)
            self.assertEqual(result["status"], 401)

    def test_web_status_availability_unknown(self) -> None:
        provider = SpyProvider("web-espion")
        app = build_app(settings=Settings(), provider=provider)
        with WebTestServer(app) as server:
            result = server.raw_request("GET", "/status")
            self.assertEqual(result["status"], 200)
            self.assertIsNone(result["json"]["available"])
            self.assertEqual(provider.is_available_calls, 0)


if __name__ == "__main__":
    unittest.main()
