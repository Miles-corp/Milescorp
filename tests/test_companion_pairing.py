"""Appairage par QR code : identité de la box, jeton et appareils associés.

Les tests ne sortent jamais du réseau local : le serveur écoute sur
`127.0.0.1` et l'identité est écrite dans un dossier temporaire.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from app.interface.companion import auth, pairing
from app.interface.companion import server as companion
from tests.companion_test_support import CompanionStoreCase, CompanionTestServer


class IdentityCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._previous = os.environ.get("COMPANION_IDENTITY")
        os.environ["COMPANION_IDENTITY"] = str(self.tmp / "box_identity.json")
        pairing.reset_identity()
        companion._PAIR_ATTEMPTS.clear()

    def tearDown(self) -> None:
        pairing.reset_identity()
        companion._PAIR_ATTEMPTS.clear()
        if self._previous is None:
            os.environ.pop("COMPANION_IDENTITY", None)
        else:
            os.environ["COMPANION_IDENTITY"] = self._previous
        self._tmp.cleanup()


class IdentityTest(IdentityCase):
    def test_identity_is_created_once_and_persisted(self) -> None:
        first = pairing.get_identity()
        self.assertTrue(first["token"])
        self.assertRegex(first["box_id"], r"^[a-f0-9]{12}$")
        path = Path(os.environ["COMPANION_IDENTITY"])
        self.assertTrue(path.is_file())
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored["token"], first["token"])

        pairing.reset_identity()
        second = pairing.get_identity()
        self.assertEqual(second["token"], first["token"])
        self.assertNotIn("_created", second)

    def test_pairing_url_keeps_the_token_in_the_fragment(self) -> None:
        identity = pairing.get_identity()
        url = pairing.pairing_url(identity, "192.168.1.42", 8787)
        self.assertTrue(url.startswith("http://192.168.1.42:8787/appairer#t="))
        self.assertNotIn("?t=", url)
        self.assertTrue(url.endswith(identity["token"]))

    def test_token_comparison(self) -> None:
        identity = pairing.get_identity()
        self.assertTrue(pairing.token_matches(identity["token"], identity))
        self.assertFalse(pairing.token_matches("mauvais", identity))
        self.assertFalse(pairing.token_matches("", identity))

    def test_rotation_invalidates_the_previous_token(self) -> None:
        before = dict(pairing.get_identity())
        after = pairing.rotate()
        self.assertNotEqual(before["token"], after["token"])
        self.assertEqual(before["box_id"], after["box_id"])
        self.assertFalse(pairing.token_matches(before["token"], after))
        self.assertTrue(pairing.token_matches(after["token"], after))

    def test_qr_files_are_written(self) -> None:
        identity = pairing.get_identity()
        url = pairing.pairing_url(identity, "192.168.1.42")
        png = pairing.write_qr(url, self.tmp / "box.png")
        svg = pairing.write_qr(url, self.tmp / "box.svg")
        self.assertGreater(png.stat().st_size, 500)
        self.assertIn(b"<svg", svg.read_bytes())


class PairingRoutesTest(CompanionStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self._identity = tempfile.TemporaryDirectory()
        self._previous_identity = os.environ.get("COMPANION_IDENTITY")
        os.environ["COMPANION_IDENTITY"] = str(Path(self._identity.name) / "box.json")
        pairing.reset_identity()
        companion._PAIR_ATTEMPTS.clear()

        self.admin = auth.create_account(
            "admin1", "mot-de-passe-admin1", role="admin", store=self.store
        )
        self.user = auth.create_account("user1", "mot-de-passe-user1", store=self.store)
        self.server = CompanionTestServer()
        self.addCleanup(self.server.close)
        self.token = pairing.get_identity()["token"]

    def tearDown(self) -> None:
        pairing.reset_identity()
        companion._PAIR_ATTEMPTS.clear()
        if self._previous_identity is None:
            os.environ.pop("COMPANION_IDENTITY", None)
        else:
            os.environ["COMPANION_IDENTITY"] = self._previous_identity
        self._identity.cleanup()
        super().tearDown()

    def _login(self, username: str) -> str:
        result = self.server.login(username, "mot-de-passe-" + username)
        self.assertEqual(result["status"], 200)
        return str(result["csrf"])

    def test_pair_without_account_sets_a_device_cookie(self) -> None:
        result = self.server.request(
            "/api/companion/pair", method="POST", body={"token": self.token, "label": "Téléphone"}
        )
        self.assertEqual(result["status"], 200, result["body"])
        self.assertEqual(result["json"]["box"]["name"], pairing.get_identity()["name"])
        self.assertEqual(result["json"]["device"]["label"], "Téléphone")
        cookie = result["headers"].get("Set-Cookie", "")
        self.assertIn("miles_companion_device=", cookie)
        self.assertIn("HttpOnly", cookie)

    def test_wrong_token_is_refused(self) -> None:
        result = self.server.request(
            "/api/companion/pair", method="POST", body={"token": "mauvais-jeton"}
        )
        self.assertEqual(result["status"], 401)
        self.assertNotIn("miles_companion_device", result["headers"].get("Set-Cookie", ""))

    def test_foreign_origin_is_refused(self) -> None:
        result = self.server.request(
            "/api/companion/pair",
            method="POST",
            body={"token": self.token},
            origin="http://attaquant.example",
        )
        self.assertEqual(result["status"], 403)

    def test_same_origin_lan_is_accepted(self) -> None:
        """Le site ouvert via l'IP du LAN doit pouvoir appairer un téléphone."""
        result = self.server.request(
            "/api/companion/pair",
            method="POST",
            body={"token": self.token},
            headers={"Origin": "http://192.168.1.50:8787", "Host": "192.168.1.50:8787"},
        )
        self.assertEqual(result["status"], 200, result["body"])

    def test_attempts_are_rate_limited(self) -> None:
        statuses = []
        for _ in range(companion.PAIR_MAX_ATTEMPTS + 1):
            result = self.server.request(
                "/api/companion/pair", method="POST", body={"token": "mauvais"}
            )
            statuses.append(result["status"])
        self.assertEqual(statuses[-1], 429)

    def test_device_appears_in_me_and_can_be_revoked(self) -> None:
        self._login("admin1")
        paired = self.server.request(
            "/api/companion/pair", method="POST", body={"token": self.token, "label": "Tablette"}
        )
        self.assertEqual(paired["status"], 200)

        me = self.server.request("/api/companion/me")
        self.assertEqual(me["status"], 200)
        self.assertEqual(me["json"]["device"]["label"], "Tablette")
        self.assertTrue(me["json"]["box_name"])

        listed = self.server.request("/api/companion/devices")
        self.assertEqual(listed["status"], 200)
        self.assertEqual(len(listed["json"]["devices"]), 1)
        device_id = listed["json"]["devices"][0]["id"]

        csrf = self.server.request("/api/companion/me")["json"]["csrf_token"]
        revoked = self.server.request(
            "/api/companion/devices/%s" % device_id, method="DELETE", csrf=csrf
        )
        self.assertEqual(revoked["status"], 200)
        self.assertIsNone(self.server.request("/api/companion/me")["json"]["device"])

    def test_devices_list_is_admin_only(self) -> None:
        self._login("user1")
        result = self.server.request("/api/companion/devices")
        self.assertEqual(result["status"], 403)

    def test_token_never_reaches_the_access_log(self) -> None:
        self.server.request("/api/companion/pair", method="POST", body={"token": self.token})
        log = Path(os.environ["COMPANION_AUDIT_LOG"])
        content = log.read_text(encoding="utf-8") if log.exists() else ""
        self.assertNotIn(self.token, content)


if __name__ == "__main__":
    unittest.main()
