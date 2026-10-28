"""Garde-fou des exemples `.env` livrés : ils doivent être utilisables tels quels.

Un `.env.example` est un mode d'emploi : l'utilisateur le copie (`cp .env.example
.env`) puis démarre MILES. Si l'exemple contient une valeur refusée par
`Settings`, l'installation échoue au premier lancement, avec une erreur qui ne
désigne pas le fichier fautif.

Ces tests garantissent trois choses :

- chaque exemple livré se charge sans erreur par `Settings` ;
- aucun exemple n'utilise un nom de variable inconnu du code (une faute de
  frappe dans un nom est silencieuse : la variable est simplement ignorée) ;
- un exemple de paquet ne dérive pas de celui de la racine (DEC-016) : toute
  variable de la racine doit y figurer.

Aucun secret n'est lu ni écrit : ces fichiers ne contiennent que des valeurs
d'exemple.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config.settings import Settings

RACINE = Path(__file__).resolve().parent.parent
_IGNORES = {".git", ".venv", "venv", "env", "node_modules", "releases", "__pycache__"}
#: Extensions de code qui consomment réellement des variables d'environnement.
_CODE = {".py", ".js", ".sh", ".cpp", ".ini"}


def _exemples() -> list[Path]:
    """Tous les exemples `.env` livrés dans le dépôt, hors dossiers techniques."""
    trouves = []
    for chemin in sorted(RACINE.rglob(".env.example")):
        if any(partie in _IGNORES for partie in chemin.relative_to(RACINE).parts):
            continue
        trouves.append(chemin)
    return trouves


def _noms(chemin: Path) -> list[str]:
    """Noms de variables déclarés dans un exemple (lignes ``NOM=``)."""
    noms = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        noms.append(ligne.split("=", 1)[0].strip())
    return noms


def _noms_utilises() -> set[str]:
    """Noms ``MILES_*`` cités par du code du projet (source unique de vérité).

    Un nom absent de tout code est ignoré en silence : l'utilisateur le
    renseigne, rien ne le lit, et le symptôme est incompréhensible. Les tests
    sont exclus volontairement : un nom lu seulement par un test ne sert à rien
    en production.
    """
    noms: set[str] = set()
    for chemin in RACINE.rglob("*"):
        if not chemin.is_file() or chemin.suffix not in _CODE:
            continue
        parties = chemin.relative_to(RACINE).parts
        if any(partie in _IGNORES for partie in parties) or "tests" in parties:
            continue
        try:
            contenu = chemin.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        noms.update(re.findall(r"MILES_[A-Z0-9_]+", contenu))
    return noms


class _EnvironnementNeuf:
    """Contexte : environnement débarrassé des variables MILES_* du poste.

    Sans cela, un `.env` renseigné sur la machine de développement masquerait
    le contenu réellement livré et le test ne prouverait rien.
    """

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin

    def __enter__(self) -> None:
        for nom in [c for c in os.environ if c.startswith("MILES_")]:
            del os.environ[nom]
        os.environ["MILES_ENV_FILE"] = str(self.chemin)

    def __exit__(self, *_exc: object) -> None:
        for nom in [c for c in os.environ if c.startswith("MILES_")]:
            del os.environ[nom]


class TestExemplesEnv(unittest.TestCase):
    def test_au_moins_un_exemple_livre(self) -> None:
        self.assertGreaterEqual(len(_exemples()), 1)

    def test_chaque_exemple_se_charge_sans_erreur(self) -> None:
        """Un exemple refusé par Settings ferait échouer toute installation."""
        for exemple in _exemples():
            relatif = exemple.relative_to(RACINE)
            with self.subTest(exemple=str(relatif)):
                with patch.dict(os.environ, {}, clear=False):
                    with _EnvironnementNeuf(exemple):
                        try:
                            settings = Settings()
                        except Exception as exc:  # noqa: BLE001 - message explicite
                            self.fail(
                                f"{relatif} est refusé par Settings : "
                                f"{type(exc).__name__}: {exc}"
                            )
                self.assertIn(settings.provider, ("remote", "local"))

    def test_aucun_nom_de_variable_inconnu(self) -> None:
        """Une variable mal nommée est ignorée en silence : on la refuse ici."""
        reconnus = _noms_utilises()
        self.assertIn("MILES_REMOTE_API_KEY", reconnus)  # le code est bien lu
        self.assertIn("MILES_BOX_KEY", reconnus)  # lu par le backend boîtier
        for exemple in _exemples():
            relatif = exemple.relative_to(RACINE)
            for nom in _noms(exemple):
                with self.subTest(exemple=str(relatif), variable=nom):
                    self.assertIn(nom, reconnus)

    def test_pas_de_derive_depuis_l_exemple_de_la_racine(self) -> None:
        """DEC-016 : l'exemple d'un paquet ne peut pas oublier la racine."""
        racine = RACINE / ".env.example"
        self.assertTrue(racine.is_file())
        attendus = set(_noms(racine))
        for exemple in _exemples():
            if exemple == racine:
                continue
            relatif = exemple.relative_to(RACINE)
            manquants = sorted(attendus - set(_noms(exemple)))
            with self.subTest(exemple=str(relatif)):
                self.assertEqual(
                    manquants,
                    [],
                    f"{relatif} oublie des variables de la racine : {manquants}",
                )

    def test_pas_de_valeur_de_secret_dans_les_exemples(self) -> None:
        """Aucun exemple ne doit porter une valeur pour un champ secret."""
        for exemple in _exemples():
            relatif = exemple.relative_to(RACINE)
            for ligne in exemple.read_text(encoding="utf-8").splitlines():
                ligne = ligne.strip()
                for secret in ("MILES_REMOTE_API_KEY=", "MILES_LOCAL_API_KEY="):
                    if ligne.startswith(secret):
                        with self.subTest(exemple=str(relatif), ligne=ligne):
                            self.assertEqual(
                                ligne.split("=", 1)[1], "", "valeur de clé présente"
                            )


if __name__ == "__main__":
    unittest.main()
