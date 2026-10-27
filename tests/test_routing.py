"""Tests du routeur de demandes (Q1) — faux fournisseurs, zéro réseau.

Vérifie : désactivation par défaut, classification déterministe,
options /fast et /deep, affichage systématique du choix (DEC-005),
indisponibilité honnête du rôle approfondi, journal sans secret.
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
from app.routing import (
    APPROFONDI_ROLE,
    RAPIDE_ROLE,
    classifier,
    rendre_compte,
    router_actif,
)


class _CaptureProvider:
    """Faux fournisseur : capture le contexte envoyé, réponse fixe."""

    def __init__(self) -> None:
        self.name = "fournisseur-capture"
        self.dernier_contexte: list = []

    def chat(self, messages: list) -> str:
        self.dernier_contexte = list(messages)
        return "réponse-fake"

    def is_available(self) -> bool:
        return True


def _settings_json(config: dict) -> Settings:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        import json
        json.dump(config, fh)
        path = fh.name
    try:
        return Settings(config_path=path)
    finally:
        os.unlink(path)


class TestActivation(unittest.TestCase):
    def test_desactive_par_defaut(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "MILES_ROUTER"}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(router_actif())
        with patch.dict(os.environ, {"MILES_ROUTER": "1"}):
            self.assertTrue(router_actif())

    def test_aucune_ligne_routeur_si_desactive(self) -> None:
        cli = CLI(settings=Settings(), provider=_CaptureProvider())
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli._process_input("bonjour simple")
        self.assertNotIn("[routeur", sortie.getvalue())

    def test_ligne_routeur_si_active(self) -> None:
        with patch.dict(os.environ, {"MILES_ROUTER": "1"}):
            cli = CLI(settings=Settings(), provider=_CaptureProvider())
            sortie = io.StringIO()
            with redirect_stdout(sortie):
                cli._process_input("bonjour simple")
        self.assertIn("[routeur : rapide -> fournisseur-capture", sortie.getvalue())


class TestClassification(unittest.TestCase):
    def test_defaut_rapide(self) -> None:
        d = classifier("bonjour")
        self.assertEqual(d["choice"], RAPIDE_ROLE)
        self.assertEqual(d["reason_code"], "defaut")

    def test_motcle_approfondi(self) -> None:
        for texte in ("analyse ce code", "compare les deux stratégies", "audite la sécurité"):
            self.assertEqual(classifier(texte)["choice"], APPROFONDI_ROLE, texte)

    def test_motcle_rapide(self) -> None:
        self.assertEqual(classifier("résume ceci")["choice"], RAPIDE_ROLE)

    def test_longueur(self) -> None:
        self.assertEqual(classifier("mot " * 150)["choice"], APPROFONDI_ROLE)

    def test_option_fast(self) -> None:
        d = classifier("/fast analyse ce code")
        self.assertEqual(d["choice"], RAPIDE_ROLE)  # l'option prime
        self.assertNotIn("/fast", d["clean"])

    def test_option_deep(self) -> None:
        d = classifier("/deep bonjour")
        self.assertEqual(d["choice"], APPROFONDI_ROLE)
        self.assertNotIn("/deep", d["clean"])


class TestCompteRenduHonnête(unittest.TestCase):
    def test_rapide_avec_cible_configurée(self) -> None:
        s = _settings_json({"router_rapide": "flash-local"})
        ligne = rendre_compte(classifier("bonjour"), "actif", s)
        self.assertEqual(ligne, "[routeur : rapide -> flash-local (défaut)]")

    def test_rapide_sans_cible_utilise_fournisseur_actif(self) -> None:
        s = Settings()
        ligne = rendre_compte(classifier("bonjour"), "actif", s)
        self.assertIn("-> actif", ligne)

    def test_approfondi_non_disponible_le_dit(self) -> None:
        s = Settings()
        ligne = rendre_compte(classifier("/deep bonjour"), "actif", s)
        self.assertIn("non disponible", ligne)
        self.assertIn("ne sera présentée comme approfondie", ligne)

    def test_approfondi_configuré_affiché(self) -> None:
        s = _settings_json({"router_approfondi": "pro-long"})
        ligne = rendre_compte(classifier("/deep bonjour"), "actif", s)
        self.assertIn("[routeur : approfondi -> pro-long", ligne)


class TestJournal(unittest.TestCase):
    def test_choix_journalise_sans_secret(self) -> None:
        cli = CLI(settings=Settings(), provider=_CaptureProvider())
        with patch.dict(os.environ, {"MILES_ROUTER": "1"}):
            with self.assertLogs("miles.routing", level="INFO") as captures:
                sortie = io.StringIO()
                with redirect_stdout(sortie):
                    cli._process_input("analyse ce dossier")
        journal = "\n".join(captures.output)
        self.assertIn("classement 'approfondi'", journal)
        self.assertNotIn("cle-api-super-secrete", journal)

    def test_fournisseur_reçoit_le_texte_nettoyé(self) -> None:
        provider = _CaptureProvider()
        cli = CLI(settings=Settings(), provider=provider)
        with patch.dict(os.environ, {"MILES_ROUTER": "1"}):
            with redirect_stdout(io.StringIO()):
                cli._process_input("/deep analyse rapide")
        dernier = provider.dernier_contexte[-1]["content"]
        self.assertNotIn("/deep", dernier)
        self.assertIn("analyse rapide", dernier)


if __name__ == "__main__":
    unittest.main()
