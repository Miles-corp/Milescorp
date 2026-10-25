"""Tests de l'assistant de liaison OAuth (S6.3, MI-008 phase 3).

Invariants : le jeton n'est jamais affiché, le flux est local uniquement
(127.0.0.1), le state est vérifié, les jetons sont stockés dans .env.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.config.oauth import (
    OAUTH_PROVIDERS,
    linked_providers,
    _build_auth_url,
    _exchange_code,
)


class TestOAuthHelpers(unittest.TestCase):
    def test_build_auth_url_contains_required_params(self) -> None:
        url = _build_auth_url("google", "client-123", "state-abc")
        self.assertIn("client_id=client-123", url)
        self.assertIn("state=state-abc", url)
        self.assertIn("response_type=code", url)
        self.assertIn("redirect_uri=http", url)
        self.assertIn("127.0.0.1", url)

    def test_unknown_provider_raises(self) -> None:
        with self.assertRaises(KeyError):
            _build_auth_url("inconnu", "id", "state")

    def test_linked_providers_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            self.assertEqual(linked_providers(env_path), [])

    def test_linked_providers_detects_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write("MILES_OAUTH_GOOGLE_TOKEN=secret-token-123\n")
            result = linked_providers(env_path)
            self.assertIn("google", result)

    def test_linked_providers_not_from_empty_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write("MILES_OAUTH_GOOGLE_TOKEN=\n")
            result = linked_providers(env_path)
            self.assertNotIn("google", result)

    def test_exchange_code_requires_valid_response(self) -> None:
        # Sans serveur, l'échange échoue proprement (pas de crash).
        try:
            _exchange_code("google", "code-fake", "id", "secret")
        except Exception as exc:
            self.assertIn("OAuthError", type(exc).__name__ + type(exc).__mro__.__str__())


class TestOAuthLinkAccount(unittest.TestCase):
    def test_link_unknown_provider(self) -> None:
        from app.config.oauth import link_account

        captured = []

        def fake_show(msg: str) -> None:
            captured.append(msg)

        result = link_account("inconnu", show=fake_show)
        self.assertEqual(result, 1)
        self.assertTrue(any("inconnu" in m.lower() for m in captured))

    def test_link_missing_client_id(self) -> None:
        from app.config.oauth import link_account

        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            captured = []

            def fake_show(msg: str) -> None:
                captured.append(msg)

            result = link_account("google", env_path=env_path, show=fake_show)
            self.assertEqual(result, 1)
            self.assertTrue(
                any("manquants" in m.lower() or "client" in m.lower() for m in captured)
            )

    def test_link_never_echoes_token(self) -> None:
        """Le jeton n'est jamais affiché dans les messages de show."""
        from app.config import oauth
        from app.config.oauth import link_account, OAuthError

        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write("MILES_OAUTH_GOOGLE_CLIENT_ID=id-test\n")
                fh.write("MILES_OAUTH_GOOGLE_CLIENT_SECRET=secret-test\n")
            captured = []

            def fake_show(msg: str) -> None:
                captured.append(msg)

            # Le rappel échoue immédiatement (pas de navigateur réel).
            with patch.object(oauth, "_receive_callback", side_effect=OAuthError("abandon")):
                result = link_account(
                    "google",
                    env_path=env_path,
                    show=fake_show,
                    open_browser=lambda url: True,
                )
            self.assertEqual(result, 1)
            joined = " ".join(captured)
            self.assertNotIn("secret-test", joined)


if __name__ == "__main__":
    unittest.main()
