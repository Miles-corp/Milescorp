"""Tests des adaptateurs natifs Anthropic et Gemini (mission L2).

Réponses HTTP simulées uniquement : protocole, conversion de format,
erreurs 401/403/404/429 et réseau, disponibilité — **jamais de vraie clé,
jamais d'appel réseau réel** (urlopen systématiquement mocké, avec garde
AssertionError pour les cas « sans clé »).
"""

from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from app.ai_providers.anthropic import AnthropicProvider
from app.ai_providers.base import AIProviderError
from app.ai_providers.gemini import GeminiProvider

CLE_ANTH = "sk-ant-test-12345-valeur"   # valeur factice de test
CLE_GEMINI = "AIza-teste-67890-valeur"  # valeur factice de test

MESSAGES = [
    {"role": "system", "content": "Tu es MILES."},
    {"role": "user", "content": "Bonjour"},
    {"role": "user", "content": "Encore un message"},  # user consécutif
    {"role": "assistant", "content": "Salut"},
]


class _Resp:
    def __init__(self, status: int = 200, corps: bytes = b"{}") -> None:
        self.status = status
        self._corps = corps

    def read(self) -> bytes:
        return self._corps

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://probe", code, "err", None, None)


# --------------------------------------------------------------------------
# ANTHROPIC
# --------------------------------------------------------------------------
class TestAnthropicProtocol(unittest.TestCase):
    def test_requete_native(self) -> None:
        corps = json.dumps(
            {"content": [{"type": "text", "text": "Salut depuis Claude"}]}
        ).encode()
        p = AnthropicProvider(api_key=CLE_ANTH, model="claude-test")
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   return_value=_Resp(200, corps)) as m:
            reponse = p.chat(MESSAGES)
        self.assertEqual(reponse, "Salut depuis Claude")
        req = m.call_args[0][0]
        self.assertIn("/v1/messages", req.full_url)
        entetes = {k.lower(): v for k, v in req.headers.items()}
        self.assertEqual(entetes.get("x-api-key"), CLE_ANTH)
        self.assertIn("anthropic-version", entetes)
        corps_envoye = json.loads(req.data.decode())
        self.assertEqual(corps_envoye["model"], "claude-test")
        self.assertIn("max_tokens", corps_envoye)
        # system en top-level, roles alternés (2 users fusionnés)
        self.assertEqual(corps_envoye["system"], "Tu es MILES.")
        roles = [m_["role"] for m_ in corps_envoye["messages"]]
        self.assertEqual(roles, ["user", "assistant"])
        self.assertIn("Encore un message", corps_envoye["messages"][0]["content"])

    def test_erreurs_publiques_sans_cle(self) -> None:
        p = AnthropicProvider(api_key=CLE_ANTH)
        for code, fragment in ((401, "clé"), (403, "clé"), (404, "modèle"), (429, "limite")):
            with self.subTest(code=code):
                with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                           side_effect=_http_error(code)):
                    with self.assertRaises(AIProviderError) as ctx:
                        p.chat(MESSAGES)
                message = str(ctx.exception)
                self.assertIn(fragment, message)
                self.assertNotIn(CLE_ANTH, message)

    def test_sans_cle_refuse_avant_appel(self) -> None:
        p = AnthropicProvider(model="claude-test")
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)

    def test_reponse_invalide(self) -> None:
        p = AnthropicProvider(api_key=CLE_ANTH)
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   return_value=_Resp(200, b"pas-du-json")):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   return_value=_Resp(200, b'{"content": []}')):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)

    def test_is_available(self) -> None:
        p = AnthropicProvider(api_key=CLE_ANTH)
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   return_value=_Resp(200, b"{}")):
            self.assertTrue(p.is_available())
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   return_value=_Resp(401, b"{}")):
            self.assertFalse(p.is_available())
        sans = AnthropicProvider(model="claude-test")
        with patch("app.ai_providers.anthropic.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            self.assertFalse(sans.is_available())


# --------------------------------------------------------------------------
# GEMINI
# --------------------------------------------------------------------------
class TestGeminiProtocol(unittest.TestCase):
    def test_requete_native(self) -> None:
        corps = json.dumps({
            "candidates": [{"content": {"parts": [{"text": "Réponse Gemini"}]}}]
        }).encode()
        p = GeminiProvider(api_key=CLE_GEMINI, model="gemini-test")
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   return_value=_Resp(200, corps)) as m:
            reponse = p.chat(MESSAGES)
        self.assertEqual(reponse, "Réponse Gemini")
        req = m.call_args[0][0]
        self.assertIn("/v1beta/models/gemini-test:generateContent", req.full_url)
        self.assertIn(f"key={CLE_GEMINI}", req.full_url)
        corps_envoye = json.loads(req.data.decode())
        roles = [c["role"] for c in corps_envoye["contents"]]
        self.assertEqual(roles, ["user", "model"])  # assistant -> model
        self.assertEqual(corps_envoye["systemInstruction"]["parts"][0]["text"],
                         "Tu es MILES.")

    def test_erreurs_publiques_sans_cle(self) -> None:
        p = GeminiProvider(api_key=CLE_GEMINI)
        for code, fragment in ((401, "clé"), (400, "clé"), (404, "modèle"), (429, "limite")):
            with self.subTest(code=code):
                with patch("app.ai_providers.gemini.urllib.request.urlopen",
                           side_effect=_http_error(code)):
                    with self.assertRaises(AIProviderError) as ctx:
                        p.chat(MESSAGES)
                message = str(ctx.exception)
                self.assertIn(fragment, message)
                # La clé passe en query : JAMAIS reprise dans un message.
                self.assertNotIn(CLE_GEMINI, message)
                self.assertNotIn("key=", message)

    def test_sans_cle_refuse_avant_appel(self) -> None:
        p = GeminiProvider(model="gemini-test")
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)

    def test_reponse_invalide(self) -> None:
        p = GeminiProvider(api_key=CLE_GEMINI)
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   return_value=_Resp(200, b"pas-du-json")):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   return_value=_Resp(200, b'{"candidates": []}')):
            with self.assertRaises(AIProviderError):
                p.chat(MESSAGES)

    def test_is_available(self) -> None:
        p = GeminiProvider(api_key=CLE_GEMINI)
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   return_value=_Resp(200, b"{}")):
            self.assertTrue(p.is_available())
        sans = GeminiProvider(model="gemini-test")
        with patch("app.ai_providers.gemini.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            self.assertFalse(sans.is_available())


class TestFabrique(unittest.TestCase):
    def test_fabrique_construit_le_bon_adaptateur(self) -> None:
        from app.ai_providers.registry import build_provider, fournisseurs_soutenus
        self.assertEqual(set(fournisseurs_soutenus()),
                         {"groq", "openai", "anthropic", "gemini"})
        self.assertIsInstance(build_provider("anthropic", model="m"),
                              AnthropicProvider)
        self.assertIsInstance(build_provider("gemini", model="m"), GeminiProvider)
        self.assertIsInstance(build_provider("groq", model="m"), type(build_provider(
            "openai", model="m")))  # compat OpenAI partagée

    def test_modele_jamais_invente(self) -> None:
        from app.ai_providers.registry import build_provider
        with self.assertRaises(ValueError):
            build_provider("groq", model="")     # modele obligatoire
        with self.assertRaises(ValueError):
            build_provider("inconnu", model="m")  # supporte uniquement

    def test_fournisseur_non_configure_refuse_sans_reseau(self) -> None:
        from app.ai_providers.registry import build_provider
        for nom in ("anthropic", "gemini"):
            with self.subTest(nom=nom):
                p = build_provider(nom, model="m")
                with patch("app.ai_providers." + nom + ".urllib.request.urlopen",
                           side_effect=AssertionError("RESEAU INTERDIT")):
                    with self.assertRaises(AIProviderError):
                        p.chat([{"role": "user", "content": "salut"}])


if __name__ == "__main__":
    unittest.main()
