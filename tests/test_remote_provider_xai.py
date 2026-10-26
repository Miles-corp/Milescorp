import io
import json
import unittest
from unittest import mock

from app.ai_providers.base import AIProviderError
from app.ai_providers.remote import RemoteProvider


class TestRemoteProviderXaiCompatibility(unittest.TestCase):
    """Tests de compatibilite du RemoteProvider avec l'API xAI (mocks uniquement)."""

    def _make_response(self, status=200, body=None):
        if body is None:
            body = {"choices": [{"message": {"content": "Hello from Grok"}}]}
        raw = json.dumps(body).encode("utf-8")
        mock_resp = mock.MagicMock()
        mock_resp.status = status
        mock_resp.read.return_value = raw
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        return mock_resp

    def test_url_construction_no_v1_duplication(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="test-key",
        )
        self.assertEqual(provider._base_url, "https://api.x.ai")
        mock_resp = self._make_response()
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = provider.chat([{"role": "user", "content": "hello"}])
            self.assertEqual(result, "Hello from Grok")
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://api.x.ai/v1/chat/completions")

    def test_url_construction_without_v1(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai",
            model="grok-3",
            api_key="test-key",
        )
        mock_resp = self._make_response()
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.chat([{"role": "user", "content": "hello"}])
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://api.x.ai/v1/chat/completions")

    def test_api_key_sent_in_header(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="xai-secret-key",
        )
        mock_resp = self._make_response()
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.chat([{"role": "user", "content": "hello"}])
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_header("Authorization"), "Bearer xai-secret-key")

    def test_no_api_key_no_header(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
        )
        mock_resp = self._make_response()
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.chat([{"role": "user", "content": "hello"}])
            req = mock_urlopen.call_args[0][0]
            self.assertIsNone(req.get_header("Authorization"))

    def test_model_in_payload(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3-mini",
            api_key="test-key",
        )
        mock_resp = self._make_response()
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            provider.chat([{"role": "user", "content": "hello"}])
            req = mock_urlopen.call_args[0][0]
            payload = json.loads(req.data.decode("utf-8"))
            self.assertEqual(payload["model"], "grok-3-mini")
            self.assertEqual(payload["stream"], False)
            self.assertAlmostEqual(payload["temperature"], 0.7)

    def test_auth_error_401(self) -> None:
        import urllib.error
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="bad-key",
        )
        http_error = urllib.error.HTTPError(
            url="https://api.x.ai/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": "invalid api key"}'),
        )
        with mock.patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(AIProviderError) as ctx:
                provider.chat([{"role": "user", "content": "hello"}])
            self.assertIn("401", str(ctx.exception))

    def test_connection_refused(self) -> None:
        import urllib.error
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
        )
        url_error = urllib.error.URLError("Connection refused")
        with mock.patch("urllib.request.urlopen", side_effect=url_error):
            with self.assertRaises(AIProviderError) as ctx:
                provider.chat([{"role": "user", "content": "hello"}])
            self.assertIn("Impossible de joindre", str(ctx.exception))

    def test_invalid_json_response(self) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="test-key",
        )
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(AIProviderError) as ctx:
                provider.chat([{"role": "user", "content": "hello"}])
            self.assertIn("non-JSON", str(ctx.exception))

    def test_empty_choices_response(self) -> None:
        mock_resp = self._make_response(body={"choices": []})
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="test-key",
        )
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(AIProviderError) as ctx:
                provider.chat([{"role": "user", "content": "hello"}])
            self.assertIn("choix", str(ctx.exception).lower())

    def test_is_available_true(self) -> None:
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
            api_key="test-key",
        )
        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            self.assertTrue(provider.is_available())

    def test_is_available_false_on_error(self) -> None:
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-3",
        )
        with mock.patch("urllib.request.urlopen", side_effect=Exception("refused")):
            self.assertFalse(provider.is_available())



    def test_is_reachable_true(self) -> None:
        """is_reachable retourne True si la connexion TCP reussit."""
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-4.7",
        )
        with mock.patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = mock.MagicMock()
            mock_conn.return_value.__exit__ = mock.MagicMock(return_value=False)
            self.assertTrue(provider.is_reachable())

    def test_is_reachable_false_on_error(self) -> None:
        """is_reachable retourne False si la connexion echoue."""
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-4.7",
        )
        with mock.patch("socket.create_connection", side_effect=OSError("refused")):
            self.assertFalse(provider.is_reachable())

    def test_is_available_calls_v1_models(self) -> None:
        """is_available appelle GET /v1/models (pas /health)."""
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-4.7",
            api_key="test-key",
        )
        with mock.patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            self.assertTrue(provider.is_available())
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://api.x.ai/v1/models")

    def test_is_available_false_on_401(self) -> None:
        """is_available retourne False si la cle est invalide (401)."""
        import urllib.error
        provider = RemoteProvider(
            base_url="https://api.x.ai/v1",
            model="grok-4.7",
            api_key="bad-key",
        )
        http_error = urllib.error.HTTPError(
            url="https://api.x.ai/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": "invalid api key"}'),
        )
        with mock.patch("urllib.request.urlopen", side_effect=http_error):
            self.assertFalse(provider.is_available())


if __name__ == "__main__":
    unittest.main()
