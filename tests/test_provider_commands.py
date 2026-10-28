"""Tests des commandes CLI multi-IA (mission L3) — réseau simulé uniquement.

Couvre : /providers, /provider <nom>, /model, /api status|add|test|remove.
Invariants : aucun secret dans AUCUNE sortie, aucune écriture de cle non
confirmee, configuration precedente conservee en cas d'echec, aucun appel
reseau hors commande explicite (gards AssertionError sur les lectures).
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app.config.settings import Settings
from app.interface.cli import CLI

CLE_TEST = "cle-factice-de-test-777"  # valeur factice, jamais reelle


class _Resp:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a: object) -> bool:
        return False


class _SettingsTest:
    """Configuration de test deterministe : zero dependance a l'environnement
    reel (les tests ne doivent jamais dependre du .env ni des variables du poste)."""

    provider = "remote"

    def get(self, key: str, default=None):
        return {
            "remote_model": "test-model-unit",
            "remote_base_url": "https://api.test.local/v1",
            "remote_timeout": 2,
            "local_base_url": "http://127.0.0.1:9",
            "local_model": "m-local-test",
            "local_timeout": 2,
            "history_limit": 10,
            "memory_enabled": False,
            "conversation_persist": False,
            "mission_enabled": False,
        }.get(key, default)

    def __getitem__(self, key):
        return self.get(key)


def _cli(env_path: str | None = None) -> CLI:
    return CLI(settings=_SettingsTest(), provider=None)


def _run(cli: CLI, commande: str) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli._handle_command(commande)
    return buf.getvalue()


class TestLectureSansReseau(unittest.TestCase):
    def test_providers_sans_secret(self) -> None:
        cli = _cli()
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            sortie = _run(cli, "/providers")
        for nom in ("Groq", "Openai", "Anthropic", "Gemini"):
            self.assertIn(nom, sortie)
        self.assertIn("pas de cle", sortie)
        self.assertNotIn("gsk-", sortie)
        self.assertNotIn("AIza", sortie)

    def test_model_affichage(self) -> None:
        cli = _cli()
        sortie = _run(cli, "/model")
        self.assertIn("Modele actif", sortie)

    def test_api_status_sans_reseau_ni_secret(self) -> None:
        cli = _cli()
        with patch("app.ai_providers.remote.urllib.request.urlopen",
                   side_effect=AssertionError("RESEAU INTERDIT")):
            sortie = _run(cli, "/api status")
        self.assertIn("groq", sortie)
        self.assertNotIn(CLE_TEST, sortie)


class TestSelectionProvider(unittest.TestCase):
    def test_fournisseur_non_supporte(self) -> None:
        cli = _cli()
        sortie = _run(cli, "/provider mistral-x")
        self.assertIn("non pris en charge", sortie)

    def test_selection_sans_cle_echoue_et_preserve(self) -> None:
        cli = _cli()
        sortie = _run(cli, "/provider anthropic")
        self.assertIn("Selection refusee", sortie)
        self.assertIn("Aucun changement effectue", sortie)

    def test_selection_avec_cle_active(self) -> None:
        cli = _cli()
        with patch.dict(os.environ, {"MILES_API_KEY_ANTHROPIC": CLE_TEST}):
            with patch("app.ai_providers.remote.urllib.request.urlopen",
                       side_effect=AssertionError("RESEAU INTERDIT")):
                sortie = _run(cli, "/provider anthropic")
        self.assertIn("Fournisseur actif : anthropic", sortie)
        self.assertIn("prochain demarrage", sortie)
        self.assertNotIn(CLE_TEST, sortie)


class TestApiCommandes(unittest.TestCase):
    def test_api_add_ecrit_et_verifie(self) -> None:
        cli = _cli()
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with patch.dict(os.environ, {"MILES_ENV_FILE": env_path,
                                         "MILES_REMOTE_PROVIDER": ""}), \
                 patch("getpass.getpass", return_value=CLE_TEST), \
                 patch("app.ai_providers.remote.urllib.request.urlopen",
                       return_value=_Resp(200)):
                sortie = _run(cli, "/api add groq")
            self.assertIn("Cle nouvelle", sortie)
            self.assertIn("Connexion reussie.", sortie)
            self.assertNotIn(CLE_TEST, sortie)
            with open(env_path, encoding="utf-8") as fh:
                contenu = fh.read()
            self.assertIn(f"MILES_API_KEY_GROQ={CLE_TEST}", contenu)

    def test_api_remove_reclame_confirmation(self) -> None:
        cli = _cli()
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with open(env_path, "w", encoding="utf-8") as fh:
                fh.write("MILES_API_KEY_GEMINI=AIza-factice\n")
            with patch.dict(os.environ, {"MILES_ENV_FILE": env_path}):
                with patch("builtins.input", return_value="n"):
                    sortie = _run(cli, "/api remove gemini")
                self.assertIn("annulee", sortie)
                self.assertTrue(os.path.exists(env_path))
                contenu = open(env_path, encoding="utf-8").read()
                self.assertIn("MILES_API_KEY_GEMINI", contenu)
                with patch("builtins.input", return_value="o"):
                    sortie = _run(cli, "/api remove gemini")
                self.assertIn("supprimee", sortie)
                contenu = open(env_path, encoding="utf-8").read()
                self.assertNotIn("MILES_API_KEY_GEMINI", contenu)

    def test_api_test_sans_cle(self) -> None:
        cli = _cli()
        with patch.dict(os.environ, {"MILES_API_KEY_OPENAI": "",
                                     "MILES_REMOTE_PROVIDER": ""}):
            with patch("app.ai_providers.remote.urllib.request.urlopen",
                       side_effect=AssertionError("RESEAU INTERDIT")):
                sortie = _run(cli, "/api test openai")
        self.assertIn("Pas de cle", sortie)

    def test_model_selection_ecrit_le_modele(self) -> None:
        cli = _cli()
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with patch.dict(os.environ, {"MILES_ENV_FILE": env_path,
                                         "MILES_REMOTE_PROVIDER": "groq"}):
                sortie = _run(cli, "/model nouveau-modele-test")
            self.assertIn("nouveau-modele-test", sortie)
            with open(env_path, encoding="utf-8") as fh:
                contenu = fh.read()
            self.assertIn("MILES_MODEL_GROQ=nouveau-modele-test", contenu)


if __name__ == "__main__":
    unittest.main()
