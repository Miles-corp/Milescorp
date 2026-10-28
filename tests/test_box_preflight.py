"""Tests du préflight boîtier (Q3) — sorties simulées, zéro effet réel.

Le script de diagnostic doit : collecter les indicateurs depuis des sources
fournies par les tests (aucun /proc ni sous-commande réel dans ces tests),
produire un rapport formaté, et ne jamais dépendre du réseau.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)
import box_preflight as bp  # noqa: E402


class TestCollecteSimulee(unittest.TestCase):
    def test_collecte_avec_sources_simulees(self) -> None:
        mem = {"MemTotal": "8192000 kB", "MemAvailable": "4096000 kB"}
        with patch.object(bp, "_meminfo", return_value=mem), \
             patch.object(bp, "_cpu", return_value={"cœurs": 4, "modèle": "TestCPU"}), \
             patch.object(bp, "_disque", return_value={"total_Go": 100.0, "libre_Go": 50.0, "utilisé_%": 50.0}), \
             patch.object(bp, "_gpu", return_value="GPU simulé"), \
             patch.object(bp, "_audio", return_value={"capture (arecord -l)": None, "lecture (aplay -l)": None}), \
             patch.object(bp, "_ports_ecoutes", return_value=["8080", "8443"]), \
             patch.object(bp, "_lecture_fichier", return_value=None):
            rapport = bp.collecter()
        self.assertEqual(rapport["ram"]["totale"], "8192000 kB")
        self.assertEqual(rapport["cpu"]["cœurs"], 4)
        self.assertEqual(rapport["gpu"], "GPU simulé")
        self.assertEqual(rapport["ports_en_ecoute"], ["8080", "8443"])

    def test_formater_contient_sections_et_gardefou(self) -> None:
        rapport = {
            "systeme": {"OS": "Linux test"},
            "gpu": "RTX simulé",
            "ports_en_ecoute": ["22"],
        }
        texte = bp.formater(rapport)
        self.assertIn("[systeme]", texte)
        self.assertIn("OS : Linux test", texte)
        self.assertIn("RTX simulé", texte)
        self.assertIn("Aucun fichier modifié", texte)
        self.assertIn("aucun réseau", texte)

    def test_sous_commande_absente_renvoie_none(self) -> None:
        # Commande inexistante : FileNotFoundError capturé, jamais de crash.
        self.assertIsNone(bp._sous_commande(["commande-absente-xyz"]))

    def test_lecture_fichier_inexistant_renvoie_none(self) -> None:
        self.assertIsNone(bp._lecture_fichier("/chemin/absolu/inexistant"))

    def test_ports_simules_tries_numeriquement(self) -> None:
        faux = (
            "  sl  local_address rem_address   st\n"
            "   0: 0100007F:1F90 00000000:0000 0A\n"   # 8080 LISTEN
            "   1: 0100007F:0016 00000000:0000 0A\n"   # 22 LISTEN
        )
        with patch.object(bp, "_lecture_fichier", return_value=faux):
            self.assertEqual(bp._ports_ecoutes(), ["22", "8080"])

    def test_main_imprime_sans_effet(self) -> None:
        with patch.object(bp, "collecter", return_value={"systeme": {"OS": "sim"}}):
            sortie = io.StringIO()
            with redirect_stdout(sortie):
                code = bp.main()
        self.assertEqual(code, 0)
        self.assertIn("PREFLIGHT", sortie.getvalue())

    def test_aucun_reseau_dans_le_code(self) -> None:
        # Garde statique : le module ne doit PAS importer de bibliothèque réseau.
        with open(bp.__file__, encoding="utf-8") as fh:
            source = fh.read()
        for interdit in ("socket", "urllib", "requests", "http.client"):
            self.assertNotIn(f"import {interdit}", source)

    def test_collecte_sur_windows_sans_os_release(self) -> None:
        # Regress : freedesktop_os_release() absent sous Windows -> pas de crash.
        with patch("platform.freedesktop_os_release",
                   side_effect=FileNotFoundError("/etc/os-release")), \
             patch.object(bp, "_meminfo", return_value={}), \
             patch.object(bp, "_cpu", return_value={"cœurs": 1, "modèle": "?"}), \
             patch.object(bp, "_disque", return_value={}), \
             patch.object(bp, "_gpu", return_value=None), \
             patch.object(bp, "_audio", return_value={}), \
             patch.object(bp, "_ports_ecoutes", return_value=[]):
            rapport = bp.collecter()
        self.assertIn("systeme", rapport)


if __name__ == "__main__":
    unittest.main()
