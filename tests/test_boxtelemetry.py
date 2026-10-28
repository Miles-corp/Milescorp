"""Tests du backend box (étape 1) — sorties simulées, zéro effet réel."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

_PATH = pathlib.Path(__file__).resolve().parent.parent / (
    "hardware/packages/backend-box/boxtelemetry.py"
)
_spec = importlib.util.spec_from_file_location("boxtelemetry", _PATH)
bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bt)


class TestCollecte(unittest.TestCase):
    def test_collecte_sans_hwmon_rend_non_disponible(self) -> None:
        with patch.object(bt, "lire_hwmmon", return_value={"temperatures": [], "ventilos": []}), \
             patch.object(bt, "lire_cpu", return_value={"charge": [0.1], "uptime_s": 10.0}):
            r = bt.collecter()
        self.assertEqual(r["temperatures"], [{"etat": "non disponible"}])
        self.assertEqual(r["ventilos"], [{"etat": "non disponible"}])
        self.assertEqual(r["cpu"]["charge"], [0.1])

    def test_reseau_interdit_dans_le_code(self) -> None:
        source = _PATH.read_text(encoding="utf-8")
        for interdit in ("import socket", "urllib.request", "urlopen("):
            self.assertNotIn(interdit, source)

    def test_hwmmon_sans_sys_rend_structure_vide(self) -> None:
        # Sur Windows (pas de /sys) : structure vide, jamais de crash.
        # Sous Linux, /sys/class/hwmon est lu en lecture seule.
        r = bt.lire_hwmmon()
        self.assertIsInstance(r["temperatures"], list)
        self.assertIsInstance(r["ventilos"], list)

    def test_collecte_est_deterministe_et_sans_secret(self) -> None:
        with patch.object(bt, "lire_hwmmon", return_value={"temperatures": [], "ventilos": []}), \
             patch.object(bt, "lire_cpu", return_value={"charge": None, "uptime_s": None}):
            r = bt.collecter()
        self.assertIn("source", r)
        self.assertNotIn("cle", repr(r).lower())


class TestInjection(unittest.TestCase):
    def test_etat_injection_aucun(self) -> None:
        with patch.object(bt, "STATE_FILE", "/chemin/inexistant/box_state.json"):
            self.assertEqual(bt._etat_injection()["etat"], "aucun")

    def test_verification_cle(self) -> None:
        with patch.dict(os.environ, {"MILES_BOX_KEY": "partagee-locale"}):
            self.assertTrue(bt._verifier_cle(None, json.dumps({"cle": "partagee-locale"}).encode()))
            self.assertFalse(bt._verifier_cle(None, json.dumps({"cle": "fausse"}).encode()))
            self.assertFalse(bt._verifier_cle(None, b"pas-du-json"))
            self.assertFalse(bt._verifier_cle(None, json.dumps({"autre": 1}).encode()))
        with patch.dict(os.environ, {"MILES_BOX_KEY": ""}):
            # sans clé configurée : aucune injection acceptée (fail-closed)
            self.assertFalse(bt._verifier_cle(None, json.dumps({"cle": ""}).encode()))

    def test_verification_cle_resiste_aux_corps_inattendus(self) -> None:
        """Aucun corps ne doit provoquer d'exception (ni 500, ni fuite)."""
        with patch.dict(os.environ, {"MILES_BOX_KEY": "partagee-locale"}):
            for corps in (
                b"[]",                       # liste, pas un objet
                b"null",                     # null
                b"\"chaine\"",                # chaine nue
                json.dumps({"cle": 123}).encode(),      # cle non textuelle
                json.dumps({"cle": None}).encode(),
                json.dumps({"cle": ["a"]}).encode(),
                b"",                         # corps vide
            ):
                with self.subTest(corps=corps):
                    self.assertFalse(bt._verifier_cle(None, corps))

    def test_verification_cle_accepte_les_caracteres_non_ascii(self) -> None:
        """La comparaison porte sur des octets : l'Unicode ne doit pas lever."""
        cle = "clé-partagée-éàü"
        with patch.dict(os.environ, {"MILES_BOX_KEY": cle}):
            self.assertTrue(
                bt._verifier_cle(None, json.dumps({"cle": cle}, ensure_ascii=False).encode("utf-8"))
            )
            self.assertFalse(
                bt._verifier_cle(None, json.dumps({"cle": "clé-partagée"}, ensure_ascii=False).encode("utf-8"))
            )


class TestMain(unittest.TestCase):
    def test_refus_lan_sans_cle(self) -> None:
        with patch.dict(os.environ, {"MILES_BOX_HOST": "192.168.1.10", "MILES_BOX_KEY": ""}, clear=False):
            code = bt.main()
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
