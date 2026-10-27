"""Tests de la disponibilité du fournisseur distant (diagnostic 2026-10-26).

Cause racine traitée : is_available() interrogeait un endpoint /health codé
en dur, absent des contrats type OpenAI (Groq) -> « indisponible » alors que
le chat fonctionnait. Ici : ZÉRO appel réseau (urlopen systématiquement
mocké), distinction des causes, aucun secret dans la sortie.
"""

from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from app.ai_providers.remote import RemoteProvider

CLE = "sk-test-XYZ-98765-secret"  # doit APPARAITRE dans aucun résultat de probe


class _Resp:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://probe", code, "err", None, None)


def _provider(base: str = "https://api.groq.com/openai/v1", **kwargs) -> RemoteProvider:
    kwargs.setdefault("model", "openai/gpt-oss-120b")
    kwargs.setdefault("api_key", CLE)
    return RemoteProvider(base_url=base, **kwargs)


def _urls(mock_call: object) -> list[str]:
    """URLs réellement construites par la sonde (urlopen mocké)."""
    call_args = getattr(mock_call, "call_args_list", None) or []
    return [c[0][0].full_url for c in call_args]


class TestResolutionEndpoint(unittest.TestCase):
    def test_groq_compat_sonde_models_sans_v1(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen", return_value=_Resp(200)) as m:
            p = _provider()
            self.assertTrue(p.is_available())
        self.assertEqual(_urls(m)[0], "https://api.groq.com/openai/models")

    def test_base_heritagee_sonde_health_d_abord(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen", return_value=_Resp(200)) as m:
            p = _provider(base="http://127.0.0.1:9999")
            self.assertTrue(p.is_available())
        self.assertIn("/health", _urls(m)[0])

    def test_sante_sur_mesure(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen", return_value=_Resp(200)) as m:
            p = _provider(health_path="/etat")
            self.assertTrue(p.is_available())
        self.assertIn("/etat", _urls(m)[0])


class TestCauses(unittest.TestCase):
    def test_ok_200(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen", return_value=_Resp(200)):
            probe = _provider().availability_probe()
        self.assertEqual((probe["disponible"], probe["cause"]), (True, "ok"))

    def test_repli_health_apres_404(self) -> None:
        # contrat OpenAI : /models 404 -> repli sur /health accessible
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=[_http_error(404), _Resp(200)]):
            probe = _provider().availability_probe()
        self.assertEqual((probe["disponible"], probe["cause"], probe["endpoint"]),
                         (True, "ok", "/health"))

    def test_endpoint_absent_404_partout(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=_http_error(404)):
            probe = _provider().availability_probe()
        self.assertEqual((probe["disponible"], probe["cause"]), (False, "endpoint_absent"))

    def test_auth_invalide_401(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=_http_error(401)):
            probe = _provider().availability_probe()
        self.assertEqual((probe["disponible"], probe["cause"]), (False, "auth_invalide"))

    def test_delai_passe(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=TimeoutError()):
            probe = _provider().availability_probe()
        self.assertEqual(probe["cause"], "delai_passe")
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=urllib.error.URLError(TimeoutError())):
            probe = _provider().availability_probe()
        self.assertEqual(probe["cause"], "delai_passe")

    def test_reseau_injoignable(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=urllib.error.URLError(ConnectionRefusedError())):
            probe = _provider().availability_probe()
        self.assertEqual((probe["disponible"], probe["cause"]), (False, "reseau_injoignable"))

    def test_configuration_absente_sans_appel(self) -> None:
        p = RemoteProvider(base_url="", model="")
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT DANS CE TEST")):
            probe = p.availability_probe()
            self.assertFalse(p.is_available())
        self.assertEqual(probe["cause"], "configure_absente")

    def test_is_available_coherent_avec_probe(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen", return_value=_Resp(404)):
            p = _provider()
            self.assertEqual(p.is_available(), p.availability_probe()["disponible"])
            self.assertFalse(p.is_available())

    def test_aucun_secret_dans_le_probe(self) -> None:
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=_http_error(404)):
            probe = _provider().availability_probe()
        self.assertNotIn(CLE, json.dumps(probe))
        self.assertNotIn(CLE, repr(probe))


if __name__ == "__main__":
    unittest.main()
