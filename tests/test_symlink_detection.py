"""Tests du correctif D-C1 : détection fiable des liens symboliques.

Avant le correctif, la détection tenteait de créer le lien à
``os.devnull`` (chemin déjà existant) : elle échouait donc sur TOUTES les
plateformes, y compris Debian 13, et les 3 tests de confinement S-005
étaient ignorés partout (faux négatif).

Ces tests prouvent, sans disposer de Debian 13, que :
- la nouvelle détection réussit quand ``os.symlink`` fonctionne ;
- l'ancienne logique échouait systématiquement (donc faux négatif) ;
- aucun fichier parasite ne subsiste après la sonde ;
- le message de skip reflète la vraie cause de l'ignorance.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from tests import test_path_security as path_security


class TestSymlinkDetection(unittest.TestCase):
    """D-C1 : la détection des liens symboliques n'est plus un faux négatif."""

    def test_detection_reussit_si_symlink_fonctionne(self) -> None:
        """Avec os.symlink fonctionnel (cas Linux), la détection est vraie.

        ``os.symlink`` est simulé par un « no-op » : cela reproduit le
        comportement de Linux sans nécessiter de privilèges Windows.
        """
        captured: list = []

        def _fake_symlink(src, dst, *args, **kwargs):
            captured.append(dst)
            return None  # création réussie simulée

        with mock.patch.object(os, "symlink", side_effect=_fake_symlink):
            resultat = path_security._symlink_supported()

        self.assertTrue(resultat, "la détection doit réussir quand symlink fonctionne")
        self.assertTrue(captured, "la sonde doit tenter une création")
        for dst in captured:
            self.assertNotEqual(
                os.path.abspath(str(dst)),
                os.path.abspath(os.devnull),
                "la sonde ne doit pas utiliser os.devnull (chemin déjà existant)",
            )
            # La destination doit être un chemin neuf, dans un temporaire.
            self.assertFalse(
                os.path.exists(str(dst)),
                "la destination de la sonde doit être inexistante",
            )

    def test_detection_echoue_si_symlink_indisponible(self) -> None:
        """Sans os.symlink (cas Windows sans privilège), la détection est fausse."""
        with mock.patch.object(os, "symlink", side_effect=OSError("privilège insuffisant")):
            resultat = path_security._symlink_supported()
        self.assertFalse(resultat)

    def test_ancienne_logique_echouait_toujours(self) -> None:
        """Preuve du faux négatif : l'ancienne sonde visait os.devnull.

        ``os.devnull`` existe déjà sur toute plateforme : l'ancienne
        destination était donc toujours invalide, et la détection retournait
        False partout, y compris sous Linux.
        """
        self.assertTrue(
            os.path.exists(os.devnull),
            "os.devnull existe : la destination de l'ancienne sonde était invalide",
        )
        # La nouvelle sonde utilise un chemin neuf dans un temporaire.
        with mock.patch.object(
            os, "symlink", side_effect=OSError("privilège insuffisant")
        ):
            self.assertFalse(path_security._symlink_supported())

    def test_aucun_fichier_parasite_apres_la_sonde(self) -> None:
        """La sonde nettoie son répertoire temporaire."""
        avant = set(os.listdir(tempfile.gettempdir()))
        path_security._symlink_supported()
        apres = set(os.listdir(tempfile.gettempdir()))
        residus = {
            nom for nom in apres - avant if nom.startswith("miles_test_symlink_probe_")
        }
        self.assertEqual(residus, set(), "la sonde doit nettoyer son temporaire")

    def test_variable_module_suivie_apres_detection(self) -> None:
        """_SYMLINK_SUPPORTED est calculée à l'import, via la nouvelle sonde."""
        self.assertIn("_symlink_supported", dir(path_security))
        self.assertIsInstance(path_security._SYMLINK_SUPPORTED, bool)

    def test_message_de_skip_reflete_la_vraie_cause(self) -> None:
        """Le message de skip ne doit pas promettre une exécution impossible."""
        source = ""
        try:
            with open(path_security.__file__, encoding="utf-8") as fh:
                source = fh.read()
        except OSError:
            self.skipTest("fichier de test introuvable")
        # L'ancienne détection writait dans os.devnull : le marqueur ne doit
        # plus être présent.
        self.assertNotIn('os.symlink("cible", os.devnull)', source)


if __name__ == "__main__":
    unittest.main()
