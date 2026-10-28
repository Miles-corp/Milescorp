"""Tests du mode LAN opt-in (fail-closed) — web.py + miles.py."""

from __future__ import annotations

import contextlib
import io
import os
import unittest
from unittest.mock import patch

from app.interface.web import WebServerSecurityError, assert_lan_host, assert_local_host


class TestAssertLanHost(unittest.TestCase):
    def test_refus_sans_env_lan(self) -> None:
        """Fail-closed : sans MILES_WEB_LAN=1, toute adresse non-locale est refusée."""
        with patch.dict(os.environ, {"MILES_WEB_LAN": ""}):
            for hote in ("192.168.1.10", "10.0.0.5", "172.16.0.1", "127.0.0.1"):
                with self.assertRaises(WebServerSecurityError):
                    assert_lan_host(hote)

    def test_refus_adresses_trop_larges_ou_publiques(self) -> None:
        with patch.dict(os.environ, {"MILES_WEB_LAN": "1"}):
            for hote in ("0.0.0.0", "::", "*", "8.8.8.8", "203.0.113.10", ""):
                with self.assertRaises(WebServerSecurityError):
                    assert_lan_host(hote)

    def test_accepte_ip_prive_avec_env_lan(self) -> None:
        with patch.dict(os.environ, {"MILES_WEB_LAN": "1"}):
            for hote in ("192.168.1.10", "10.0.0.5", "172.16.0.1", "127.0.0.1", "localhost"):
                self.assertEqual(assert_lan_host(hote), hote)

    def test_assert_local_host_toujours_strict(self) -> None:
        """Le comportement fail-closed par défaut est préservé."""
        self.assertEqual(assert_local_host("127.0.0.1"), "127.0.0.1")
        for hote in ("192.168.1.10", "0.0.0.0", "::"):
            with self.assertRaises(WebServerSecurityError):
                assert_local_host(hote)


class TestMilesWebServerAllowLan(unittest.TestCase):
    def test_construction_refuse_lan_sans_env(self) -> None:
        from app.interface.web import MilesWebServer, WebApp

        app = WebApp.__new__(WebApp)  # contournement de __init__ lourd
        with patch.dict(os.environ, {"MILES_WEB_LAN": ""}):
            with self.assertRaises(WebServerSecurityError):
                MilesWebServer(app, host="192.168.1.10", allow_lan=True)

    def test_construction_refuse_lan_avec_0_0_0_0(self) -> None:
        from app.interface.web import MilesWebServer, WebApp

        app = WebApp.__new__(WebApp)
        with patch.dict(os.environ, {"MILES_WEB_LAN": "1"}):
            with self.assertRaises(WebServerSecurityError):
                MilesWebServer(app, host="0.0.0.0", allow_lan=True)

    def test_construction_accepte_lan_prive(self) -> None:
        from app.interface.web import MilesWebServer, WebApp

        app = WebApp.__new__(WebApp)
        with patch.dict(os.environ, {"MILES_WEB_LAN": "1"}):
            s = MilesWebServer(app, host="192.168.1.10", allow_lan=True)
        self.assertEqual(s.host, "192.168.1.10")
        self.assertTrue(s.allow_lan)

    def test_defaut_reste_local(self) -> None:
        from app.interface.web import MilesWebServer, WebApp

        app = WebApp.__new__(WebApp)
        s = MilesWebServer(app, port=8080)
        self.assertEqual(s.host, "127.0.0.1")
        self.assertFalse(s.allow_lan)


class _SettingsStub:
    """Settings minimal et déterministe (jamais de .env réel du poste)."""

    provider = "off"
    memory_enabled = False
    mission_enabled = False
    conversation_persist = False

    def __init__(self, jeton: str = "", **_ignores: object) -> None:
        self._jeton = jeton

    def get(self, key: str, default: object = None) -> object:
        if key == "web_auth_token":
            return self._jeton
        return default

    def __getattr__(self, name: str) -> object:
        return None


class TestWebLanFailClosedDansMiles(unittest.TestCase):
    """DEC-016 §2 : un test doit prouver le refus de --web-lan sans jeton.

    Le contrôle est placé en tête de ``miles.main`` : aucun accès disque,
    aucun objet créé avant le refus (fail-closed).
    """

    def _lancer(self, argv: list[str], settings: _SettingsStub) -> tuple[int, str]:
        import miles

        sortie = io.StringIO()
        with patch.object(miles, "Settings", lambda config_path=None: settings):
            with contextlib.redirect_stderr(sortie):
                code = miles.main(argv)
        return code, sortie.getvalue()

    def test_refus_sans_jeton_configure(self) -> None:
        """Sans MILES_WEB_AUTH_TOKEN : refus explicite, code 1."""
        with patch.dict(
            os.environ,
            {"MILES_WEB_AUTH_TOKEN": "", "MILES_WEB_LAN_HOST": "192.168.1.10"},
        ):
            code, err = self._lancer(["--web", "--web-lan"], _SettingsStub(jeton=""))
        self.assertEqual(code, 1)
        self.assertIn("--web-lan refuse sans jeton", err)

    def test_refus_sans_ip_privee_explicite(self) -> None:
        """Jeton OK mais pas d'IP privée : refus explicite, code 1."""
        with patch.dict(
            os.environ,
            {"MILES_WEB_AUTH_TOKEN": "jeton-valide", "MILES_WEB_LAN_HOST": ""},
        ):
            code, err = self._lancer(["--web", "--web-lan"], _SettingsStub())
        self.assertEqual(code, 1)
        self.assertIn("MILES_WEB_LAN_HOST", err)

    def test_jeton_depuis_le_dotenv_compte_aussi(self) -> None:
        """Le jeton du .env (settings) satisfait l'exigence, sans env."""
        with patch.dict(
            os.environ,
            {"MILES_WEB_AUTH_TOKEN": "", "MILES_WEB_LAN_HOST": ""},
        ):
            code, err = self._lancer(
                ["--web", "--web-lan"], _SettingsStub(jeton="jeton-du-env")
            )
        # Le jeton est présent : on passe l'étape jeton, on bute sur l'IP.
        self.assertEqual(code, 1)
        self.assertNotIn("refuse sans jeton", err)
        self.assertIn("MILES_WEB_LAN_HOST", err)

    def test_web_local_sans_lan_toujours_autorise(self) -> None:
        """Le mode local (sans --web-lan) n'est jamais bloqué par ce contrôle."""
        with patch.dict(
            os.environ,
            {"MILES_WEB_AUTH_TOKEN": "", "MILES_WEB_LAN_HOST": ""},
        ):
            import miles

            with patch.object(
                miles, "Settings", lambda config_path=None: _SettingsStub()
            ), patch.object(miles, "_build_transcript", return_value=None), patch.object(
                miles, "WebApp"
            ), patch.object(miles, "MilesWebServer") as serveur, patch.object(
                miles, "_build_web_authenticator"
            ) as auth:
                auth.return_value = (object(), "")
                sortie = io.StringIO()
                with contextlib.redirect_stderr(sortie), contextlib.redirect_stdout(sortie):
                    code = miles.main(["--web", "--no-persist"])
        self.assertEqual(code, 0, sortie.getvalue())
        # Le serveur local reste sur l'adresse par défaut, allow_lan absent.
        kwargs = serveur.call_args.kwargs
        self.assertFalse(kwargs.get("allow_lan", False))

    def test_lan_accepte_quand_jeton_et_ip_presents(self) -> None:
        """Chemin positif : jeton + IP privée → serveur construit en allow_lan."""
        with patch.dict(
            os.environ,
            {"MILES_WEB_AUTH_TOKEN": "jeton-valide", "MILES_WEB_LAN_HOST": "192.168.1.10"},
        ):
            import miles

            with patch.object(
                miles, "Settings", lambda config_path=None: _SettingsStub()
            ), patch.object(miles, "_build_transcript", return_value=None), patch.object(
                miles, "WebApp"
            ), patch.object(miles, "MilesWebServer") as serveur, patch.object(
                miles, "_build_web_authenticator"
            ) as auth:
                auth.return_value = (object(), "")
                sortie = io.StringIO()
                with contextlib.redirect_stderr(sortie), contextlib.redirect_stdout(sortie):
                    code = miles.main(["--web", "--web-lan", "--no-persist"])
            try:
                self.assertEqual(code, 0, sortie.getvalue())
                kwargs = serveur.call_args.kwargs
                self.assertEqual(kwargs.get("host"), "192.168.1.10")
                self.assertTrue(kwargs.get("allow_lan"))
                self.assertEqual(os.environ.get("MILES_WEB_LAN"), "1")
            finally:
                os.environ.pop("MILES_WEB_LAN", None)


if __name__ == "__main__":
    unittest.main()
