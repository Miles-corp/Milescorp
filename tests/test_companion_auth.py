"""Comptes, sessions, rôles et audit du site Companion.

Les tests portent sur la logique réelle (`app/interface/companion/auth.py`) et
sur une base SQLite temporaire. Aucun réseau, aucun fichier du dépôt.
"""

from __future__ import annotations

import http.client
import json
import time
import unittest
from pathlib import Path

from app.interface.companion import audit, auth
from tests.companion_test_support import CompanionStoreCase, CompanionTestServer


class PasswordTest(unittest.TestCase):
    def test_hash_and_verify(self) -> None:
        stored = auth.hash_password("un-mot-de-passe-solide")
        self.assertTrue(auth.verify_password("un-mot-de-passe-solide", stored))
        self.assertFalse(auth.verify_password("mauvais", stored))
        self.assertNotIn("un-mot-de-passe-solide", stored)

    def test_hash_is_salted(self) -> None:
        first = auth.hash_password("un-mot-de-passe-solide")
        second = auth.hash_password("un-mot-de-passe-solide")
        self.assertNotEqual(first, second)

    def test_malformed_hash_is_refused(self) -> None:
        self.assertFalse(auth.verify_password("x", "pas-un-hash"))
        self.assertFalse(auth.verify_password("x", "scrypt$1$1$1$bad"))


class AccountRulesTest(CompanionStoreCase):
    def test_create_and_list(self) -> None:
        account = auth.create_account(
            "alice", "mot-de-passe-alice", role="admin", store=self.store
        )
        self.assertEqual(account["role"], "admin")
        self.assertFalse(account["disabled"])
        self.assertEqual(len(auth.list_accounts(store=self.store)), 1)

    def test_username_is_normalised(self) -> None:
        account = auth.create_account("Alice", "mot-de-passe-alice", store=self.store)
        self.assertEqual(account["username"], "alice")

    def test_invalid_username_is_refused(self) -> None:
        for username in ("a", "avec espace", "-debut", "très-long-" + "x" * 40):
            with self.subTest(username=username):
                with self.assertRaises(auth.AuthError):
                    auth.create_account(username, "mot-de-passe-alice", store=self.store)

    def test_short_password_is_refused(self) -> None:
        with self.assertRaises(auth.AuthError):
            auth.create_account("alice", "court", store=self.store)

    def test_duplicate_username_is_refused(self) -> None:
        auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        with self.assertRaises(Exception):
            auth.create_account("alice", "autre-mot-de-passe", store=self.store)

    def test_two_admins_maximum(self) -> None:
        auth.create_account("admin1", "mot-de-passe-admin1", role="admin", store=self.store)
        auth.create_account("admin2", "mot-de-passe-admin2", role="admin", store=self.store)
        with self.assertRaises(auth.AuthError):
            auth.create_account("admin3", "mot-de-passe-admin3", role="admin", store=self.store)
        # Un utilisateur reste possible.
        auth.create_account("user1", "mot-de-passe-user1", store=self.store)

    def test_last_admin_cannot_be_removed(self) -> None:
        admin = auth.create_account(
            "admin1", "mot-de-passe-admin1", role="admin", store=self.store
        )
        with self.assertRaises(auth.AuthError):
            auth.update_account(admin["id"], role="user", store=self.store)
        with self.assertRaises(auth.AuthError):
            auth.update_account(admin["id"], disabled=True, store=self.store)
        with self.assertRaises(auth.AuthError):
            auth.delete_account(admin["id"], store=self.store)

    def test_second_admin_can_be_demoted(self) -> None:
        first = auth.create_account(
            "admin1", "mot-de-passe-admin1", role="admin", store=self.store
        )
        second = auth.create_account(
            "admin2", "mot-de-passe-admin2", role="admin", store=self.store
        )
        updated = auth.update_account(second["id"], role="user", store=self.store)
        self.assertEqual(updated["role"], "user")

    def test_disabled_account_cannot_authenticate(self) -> None:
        account = auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        self.assertIsNotNone(auth.authenticate("alice", "mot-de-passe-alice", store=self.store))
        auth.update_account(account["id"], disabled=True, store=self.store)
        self.assertIsNone(auth.authenticate("alice", "mot-de-passe-alice", store=self.store))

    def test_wrong_password_is_refused(self) -> None:
        auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        self.assertIsNone(auth.authenticate("alice", "mauvais", store=self.store))
        self.assertIsNone(auth.authenticate("inconnu", "mot-de-passe-alice", store=self.store))


class SessionTest(CompanionStoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.account = auth.create_account(
            "alice", "mot-de-passe-alice", store=self.store
        )

    def test_session_roundtrip(self) -> None:
        token, csrf, expires = auth.create_session(
            self.account["id"], ip="127.0.0.1", user_agent="test", store=self.store
        )
        self.assertTrue(token)
        self.assertTrue(csrf)
        self.assertGreater(expires, time.time())
        session = auth.resolve_session(token, store=self.store)
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session["account_id"], self.account["id"])
        self.assertEqual(session["role"], "user")
        # Le jeton n'est jamais stocké en clair.
        row = self.store.query_one("SELECT id_hash FROM sessions")
        assert row is not None
        self.assertNotEqual(row["id_hash"], token)

    def test_unknown_session_is_refused(self) -> None:
        self.assertIsNone(auth.resolve_session("inconnu", store=self.store))

    def test_absolute_expiry(self) -> None:
        token, _, _ = auth.create_session(self.account["id"], store=self.store)
        self.store.execute("UPDATE sessions SET expires_at = ?", (time.time() - 1,))
        self.assertIsNone(auth.resolve_session(token, store=self.store))
        self.assertEqual(self.store.query_one("SELECT COUNT(*) AS n FROM sessions")["n"], 0)

    def test_idle_expiry(self) -> None:
        token, _, _ = auth.create_session(self.account["id"], store=self.store)
        self.store.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE id_hash != ''",
            (time.time() - auth.IDLE_TTL_S - 1,),
        )
        self.assertIsNone(auth.resolve_session(token, store=self.store))

    def test_logout_revokes_only_that_session(self) -> None:
        first, _, _ = auth.create_session(self.account["id"], store=self.store)
        second, _, _ = auth.create_session(self.account["id"], store=self.store)
        auth.revoke_session(first, store=self.store)
        self.assertIsNone(auth.resolve_session(first, store=self.store))
        self.assertIsNotNone(auth.resolve_session(second, store=self.store))

    def test_disable_revokes_sessions(self) -> None:
        token, _, _ = auth.create_session(self.account["id"], store=self.store)
        auth.update_account(self.account["id"], disabled=True, store=self.store)
        self.assertIsNone(auth.resolve_session(token, store=self.store))

    def test_password_change_revokes_sessions(self) -> None:
        token, _, _ = auth.create_session(self.account["id"], store=self.store)
        auth.set_password(self.account["id"], "nouveau-mot-de-passe", store=self.store)
        self.assertIsNone(auth.resolve_session(token, store=self.store))
        self.assertIsNotNone(
            auth.authenticate("alice", "nouveau-mot-de-passe", store=self.store)
        )


class LoginLimitTest(CompanionStoreCase):
    def test_five_failures_lock_the_pair(self) -> None:
        for _ in range(auth.MAX_FAILURES):
            auth.record_login_failure("alice", "127.0.0.1", store=self.store)
        self.assertTrue(auth.login_locked("alice", "127.0.0.1", store=self.store))
        self.assertFalse(auth.login_locked("alice", "10.0.0.2", store=self.store))

    def test_success_clears_failures(self) -> None:
        auth.record_login_failure("alice", "127.0.0.1", store=self.store)
        auth.clear_login_failures("alice", "127.0.0.1", store=self.store)
        self.assertFalse(auth.login_locked("alice", "127.0.0.1", store=self.store))


class PreferencesTest(CompanionStoreCase):
    def test_dev_mode_roundtrip(self) -> None:
        account = auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        self.assertFalse(auth.get_preferences(account["id"], store=self.store)["dev_mode"])
        auth.set_dev_mode(account["id"], True, store=self.store)
        self.assertTrue(auth.get_preferences(account["id"], store=self.store)["dev_mode"])


class AuditTest(CompanionStoreCase):
    def test_secrets_are_redacted(self) -> None:
        account = auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        secret = "sk-test-valeur-qui-ne-doit-jamais-sortir"
        audit.log_event(
            "provider.key",
            account=account,
            target="groq",
            detail={
                "api_key": secret,
                "nested": {"token": secret, "csrf": secret, "note": "visible"},
            },
            store=self.store,
        )
        row = self.store.query_one("SELECT detail FROM audit")
        assert row is not None
        self.assertNotIn(secret, row["detail"])
        self.assertIn("visible", row["detail"])
        log = Path(self.store.path).parent / "audit.jsonl"
        self.assertTrue(log.is_file())
        self.assertNotIn(secret, log.read_text(encoding="utf-8"))

    def test_events_are_filtered_by_account(self) -> None:
        alice = auth.create_account("alice", "mot-de-passe-alice", store=self.store)
        bob = auth.create_account("bob", "mot-de-passe-bob", store=self.store)
        audit.log_event("a", account=alice, store=self.store)
        audit.log_event("b", account=bob, store=self.store)
        only_alice = audit.list_events(account_id=alice["id"], store=self.store)
        self.assertEqual([event["event"] for event in only_alice], ["a"])


class KeepAliveFramingTest(CompanionStoreCase):
    """Un POST dont le corps n'est pas lu ne doit pas corrompre la suite.

    `auth/logout` répond sans lire son corps JSON. En HTTP/1.1 keep-alive, ce
    `{}` restait dans la socket : la requête suivante devenait « {}GET … » et
    le serveur répondait 501 après une déconnexion suivie d'un rechargement.
    """

    def test_logout_then_navigation_on_the_same_connection(self) -> None:
        auth.create_account("alice", "mot-de-passe-alice", role="admin", store=self.store)
        server = CompanionTestServer()
        self.addCleanup(server.close)

        login = server.login("alice", "mot-de-passe-alice")
        self.assertEqual(login["status"], 200, login["body"])
        csrf = str(login["json"]["csrf_token"])
        cookie = "; ".join("%s=%s" % (item.name, item.value) for item in server.jar)

        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        self.addCleanup(conn.close)
        conn.request(
            "POST",
            "/api/companion/auth/logout",
            body="{}",
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
                "Cookie": cookie,
            },
        )
        logout = conn.getresponse()
        logout.read()
        self.assertEqual(logout.status, 200)

        # Même connexion : la coque doit être servie, pas un 501 de framing.
        conn.request("GET", "/connexion")
        page = conn.getresponse()
        body = page.read().decode("utf-8", "replace")
        self.assertEqual(page.status, 200)
        self.assertIn("text/html", page.getheader("Content-Type", ""))
        self.assertIn("Miles Companion", body)

    def test_oversized_json_keeps_the_connection_framed(self) -> None:
        """Un 413 sur corps trop gros ne coupe pas la requête suivante."""
        auth.create_account("alice", "mot-de-passe-alice", role="admin", store=self.store)
        server = CompanionTestServer()
        self.addCleanup(server.close)
        login = server.login("alice", "mot-de-passe-alice")
        self.assertEqual(login["status"], 200, login["body"])
        csrf = str(login["csrf"])
        cookie = "; ".join("%s=%s" % (item.name, item.value) for item in server.jar)

        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=15)
        self.addCleanup(conn.close)
        oversized = json.dumps({"current_password": "peu-importe", "new_password": "x" * 1_200_000})
        conn.request(
            "POST",
            "/api/companion/password",
            body=oversized,
            headers={
                "Content-Type": "application/json",
                "X-CSRF-Token": csrf,
                "Cookie": cookie,
                "Origin": server.origin,
            },
        )
        refused = conn.getresponse()
        refused.read()
        self.assertEqual(refused.status, 413)

        conn.request("GET", "/connexion")
        page = conn.getresponse()
        body = page.read().decode("utf-8", "replace")
        self.assertEqual(page.status, 200)
        self.assertIn("Miles Companion", body)

    def test_oversized_form_keeps_the_connection_framed(self) -> None:
        """Un formulaire /setup refusé (70 Ko) ne laisse pas `csrf=…` en tête."""
        server = CompanionTestServer()
        self.addCleanup(server.close)
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=15)
        self.addCleanup(conn.close)
        conn.request(
            "POST",
            "/setup",
            body="csrf=" + "x" * 70_000,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        refused = conn.getresponse()
        refused.read()
        self.assertEqual(refused.status, 400)

        conn.request("GET", "/connexion")
        page = conn.getresponse()
        body = page.read().decode("utf-8", "replace")
        self.assertEqual(page.status, 200)
        self.assertIn("Miles Companion", body)


if __name__ == "__main__":
    unittest.main()
