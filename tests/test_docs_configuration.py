"""Tests de non-divergence entre la documentation et le code (R3).

Ces tests garantissent que la section « Sources de configuration et
variables reconnues » de ``docs/installation/INSTALL.md`` reste alignée sur
l'implémentation réelle de ``app/config/settings.py``.

Ils vérifient également :
- la priorité réelle des sources de configuration ;
- le traitement des variables présentes dans le ``.env`` mais non reconnues ;
- la procédure de configuration d'un proxy HTTP/HTTPS.
"""

from __future__ import annotations

import inspect
import os
import re
import shutil
import tempfile
import unittest
import urllib.request
from unittest import mock

from app.config import settings as settings_module
from app.config.settings import Settings

INSTALL_PATH = "docs/installation/INSTALL.md"


def _recognized_variables() -> list[str]:
    """Extraire les variables MILES_* réellement lues par le code.

    Sont prises en compte :
    - les variables du dictionnaire ``env_mapping`` (17) ;
    - les variables de chemin de fichier lues directement dans l'environnement
      (``MILES_ENV_FILE``, ``MILES_CONFIG``).
    """
    source = inspect.getsource(settings_module)
    return sorted(set(re.findall(r"MILES_[A-Z_]+", source)))


def _mapping_variables() -> list[str]:
    """Extraire les variables du seul dictionnaire ``env_mapping``."""
    source = inspect.getsource(settings_module)
    block = re.search(r"env_mapping = \{(.*?)\n        \}", source, re.S)
    assert block is not None, "env_mapping introuvable dans app/config/settings.py"
    return re.findall(r'"(MILES_[A-Z_]+)"', block.group(1))


class TestDocumentedVariablesMatchCode(unittest.TestCase):
    """R3 : la documentation doit refléter le code réel."""

    def setUp(self) -> None:
        self.variables = _recognized_variables()
        with open(INSTALL_PATH, encoding="utf-8") as fh:
            self.install = fh.read()

    def test_nombre_de_variables_reconnues(self) -> None:
        # 28 variables de configuration + 2 variables de chemin de fichier.
        self.assertEqual(len(self.variables), 30)
        self.assertEqual(len(_mapping_variables()), 28)
        # Les deux variables de chemin de fichier sont bien reconnues.
        self.assertIn("MILES_ENV_FILE", self.variables)
        self.assertIn("MILES_CONFIG", self.variables)

    def test_toute_variable_documentee_est_reconnue(self) -> None:
        documentees = set(re.findall(r"MILES_[A-Z_]+", self.install))
        inconnues = documentees - set(self.variables)
        self.assertEqual(
            inconnues,
            set(),
            f"Variables documentées mais non reconnues par le code : {sorted(inconnues)}",
        )

    def test_toute_variable_reconnue_est_documentee(self) -> None:
        documentees = set(re.findall(r"MILES_[A-Z_]+", self.install))
        manquantes = set(self.variables) - documentees
        self.assertEqual(
            manquantes,
            set(),
            f"Variables reconnues mais non documentées : {sorted(manquantes)}",
        )

    def test_variables_de_chemin_documentees_separement(self) -> None:
        """D-C2 : les variables de chemin doivent être distinguées des variables
        lues depuis le fichier `.env`."""
        self.assertIn("### Variables de chemin de fichier", self.install)
        # Elles ne doivent pas figurer dans le tableau des variables du .env
        bloc_env = self.install.split("### Variables de chemin de fichier")[0]
        # La section des variables lues depuis le .env est celle du tableau
        # "Variables reconnues" jusqu'a la section des variables de chemin
        debut_tableau = bloc_env.find("### Variables reconnues")
        fin_tableau = bloc_env.find("### Variables de chemin de fichier")
        if debut_tableau >= 0 and fin_tableau >= 0:
            tableau = bloc_env[debut_tableau:fin_tableau]
            self.assertNotIn("MILES_ENV_FILE", tableau)
            self.assertNotIn("MILES_CONFIG", tableau)

    def test_variables_de_chemin_exclusives_environnement_processus(self) -> None:
        """La documentation doit dire que ces deux variables sont lues
        exclusivement depuis l'environnement du processus."""
        for mention in (
            "exclusivement",
            "jamais",
        ):
            self.assertIn(mention, self.install)
        section = self.install.split("### Variables de chemin de fichier")[1][:1200]
        self.assertIn("environnement du processus", section)

    def test_sources_de_configuration_documentationnees(self) -> None:
        for mention in (
            "MILES_ENV_FILE",
            "MILES_CONFIG",
            "config/config.json",
            "HTTP_PROXY",
            "HTTPS_PROXY",
        ):
            self.assertIn(mention, self.install)

    def test_priorite_documentationnee(self) -> None:
        """L'ordre de priorité documenté doit être explicite."""
        for mention in (
            "Variables d'environnement du processus",
            "Fichier `.env`",
            "Fichier JSON",
            "Valeurs par défaut",
        ):
            self.assertIn(mention, self.install)


class TestConfigurationPriority(unittest.TestCase):
    """R3 : la priorité réelle des sources de configuration."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_docs_")
        self.env_path = os.path.join(self.tmpdir, ".env")
        self.json_path = os.path.join(self.tmpdir, "config.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_env(self, content: str) -> None:
        with open(self.env_path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def _write_json(self, payload: dict) -> None:
        import json

        with open(self.json_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_processus_prime_sur_env_et_json(self) -> None:
        self._write_env("MILES_PROVIDER=local\n")
        self._write_json({"provider": "remote", "history_limit": 7})
        env = {
            "MILES_ENV_FILE": self.env_path,
            "MILES_PROVIDER": "remote",
        }
        with mock.patch.dict(os.environ, env):
            settings = Settings(config_path=self.json_path)
            self.assertEqual(settings.provider, "remote")
            self.assertEqual(settings.get("history_limit"), 7)

    def test_env_prime_sur_json(self) -> None:
        self._write_env("MILES_PROVIDER=local\nMILES_HISTORY_LIMIT=5\n")
        self._write_json({"provider": "remote", "history_limit": 7})
        env = {"MILES_ENV_FILE": self.env_path}
        with mock.patch.dict(os.environ, env):
            settings = Settings(config_path=self.json_path)
            self.assertEqual(settings.provider, "local")
            self.assertEqual(settings.get("history_limit"), 5)

    def test_json_prime_sur_defauts(self) -> None:
        self._write_json({"history_limit": 9})
        env = {"MILES_ENV_FILE": os.path.join(self.tmpdir, "absent.env")}
        with mock.patch.dict(os.environ, env):
            settings = Settings(config_path=self.json_path)
            self.assertEqual(settings.get("history_limit"), 9)

    def test_defauts_si_aucune_source(self) -> None:
        env = {"MILES_ENV_FILE": os.path.join(self.tmpdir, "absent.env")}
        with mock.patch.dict(os.environ, env):
            settings = Settings(config_path=os.path.join(self.tmpdir, "absent.json"))
            self.assertEqual(settings.provider, "remote")
            self.assertEqual(settings.get("history_limit"), 10)

    def test_miles_config_dans_env_ignore(self) -> None:
        """D-C2 : `MILES_CONFIG` écrit dans le `.env` est sans effet."""
        import json as _json

        autre = os.path.join(self.tmpdir, "autre.json")
        with open(autre, "w", encoding="utf-8") as fh:
            _json.dump({"history_limit": 42}, fh)
        self._write_env("MILES_CONFIG=%s\n" % autre.replace("\\", "/"))
        env = {"MILES_ENV_FILE": self.env_path}
        with mock.patch.dict(os.environ, env):
            settings = Settings()
            # Le .env est lu, mais MILES_CONFIG ne l'est pas :
            # le JSON par défaut est utilisé, pas celui du .env.
            self.assertEqual(settings.get("history_limit"), 10)

    def test_miles_env_file_dans_env_ignore(self) -> None:
        """D-C2 : `MILES_ENV_FILE` écrit dans le `.env` est sans effet.

        Le fichier réellement lu est celui désigné par la variable
        d'environnement du processus, pas celui désigné par le `.env`.
        """
        secondaire = os.path.join(self.tmpdir, "secondaire.env")
        with open(secondaire, "w", encoding="utf-8") as fh:
            fh.write("MILES_PROVIDER=remote\n")
        self._write_env(
            "MILES_PROVIDER=local\nMILES_ENV_FILE=%s\n"
            % secondaire.replace("\\", "/")
        )
        env = {"MILES_ENV_FILE": self.env_path}
        with mock.patch.dict(os.environ, env):
            settings = Settings()
            # Le .env lu est celui de l'environnement du processus,
            # donc MILES_PROVIDER vaut "local" et non "remote".
            self.assertEqual(settings.provider, "local")

    def test_variable_non_reconnue_ignoree(self) -> None:
        """Une variable non MILES_* du .env n'est ni lue ni injectée."""
        self._write_env("MILES_PROVIDER=local\nHTTP_PROXY=http://proxy.invalid:3128\n")
        env = {"MILES_ENV_FILE": self.env_path}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("HTTP_PROXY", None)
            settings = Settings()
            self.assertEqual(settings.provider, "local")
            self.assertNotIn("HTTP_PROXY", os.environ)

    def test_proxy_du_processus_est_utilise_par_urllib(self) -> None:
        """Le proxy défini dans l'environnement du processus est pris en compte."""
        env = {"HTTP_PROXY": "http://proxy.exemple:3128"}
        with mock.patch.dict(os.environ, env):
            proxies = urllib.request.getproxies()
        self.assertEqual(proxies.get("http"), "http://proxy.exemple:3128")


if __name__ == "__main__":
    unittest.main()
