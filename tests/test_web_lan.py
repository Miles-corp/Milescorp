"""Tests du mode LAN opt-in (fail-closed) — web.py + miles.py."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
