"""Génération des archives de téléchargement : ce qui part, ce qui ne part pas.

Le script d'archive est le dernier rempart avant publication : une erreur ici
expédie des secrets ou des binaires de compilation à l'utilisateur.

Régression corrigée (2026-10-28) : la comparaison des motifs se faisait sur le
chemin complet avec des `/`, alors que Windows construit des `\\`. Résultat,
`.pio/` et `__pycache__/` **entraient** dans les archives. Les tests ci-dessous
vérifient les deux séparateurs, et l'absence réelle de ces fichiers dans une
archive produite.
"""

from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "scripts"))
import build_release as br  # noqa: E402


class TestExclusions(unittest.TestCase):
    def test_secrets_jamais_archives(self) -> None:
        for nom in (".env", "pc-miles/.env", "pc-miles\\.env", "data/auth.json"):
            with self.subTest(nom=nom):
                self.assertTrue(br.exclure(nom))

    def test_modele_env_reste_archive(self) -> None:
        """`.env.example` est un exemple : il doit partir, lui."""
        for nom in (".env.example", "pc-miles/.env.example", "pc-miles\\.env.example"):
            with self.subTest(nom=nom):
                self.assertFalse(br.exclure(nom))

    def test_artefacts_de_build_exclus(self) -> None:
        """Régression : `.pio` et `__pycache__`, quel que soit le séparateur."""
        for nom in (
            ".pio",
            ".pio/build/project.checksum",
            "esp32-s3/.pio/build/firmware.bin",
            "esp32-s3\\.pio\\build\\firmware.bin",
            "__pycache__",
            "backend-box/__pycache__/x.pyc",
            "backend-box\\__pycache__\\x.pyc",
        ):
            with self.subTest(nom=nom):
                self.assertTrue(br.exclure(nom))

    def test_etat_local_et_cles_exclus(self) -> None:
        for nom in ("box_state.json", "box/server.pem", "box/tls.key", "pio.ini.local"):
            with self.subTest(nom=nom):
                self.assertTrue(br.exclure(nom))

    def test_fichiers_ordinaires_conserves(self) -> None:
        for nom in (
            "pc-miles/install.sh",
            "esp32-s3/src/main.cpp",
            "esp32-s3/platformio.ini",
            "backend-box/boxtelemetry.py",
            "pc-miles/README.md",
        ):
            with self.subTest(nom=nom):
                self.assertFalse(br.exclure(nom))


class TestArchiveProduite(unittest.TestCase):
    """Archive réelle d'un faux paquet : on regarde ce qui entre dedans."""

    def test_archive_exclut_secrets_et_build(self) -> None:
        with tempfile.TemporaryDirectory(prefix="miles_release_") as tmp:
            base = Path(tmp)
            paquetier = base / "packages"
            paquet = paquetier / "demo"
            (paquet / "src").mkdir(parents=True)
            (paquet / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
            (paquet / ".env.example").write_text("CLE=\n", encoding="utf-8")
            (paquet / ".env").write_text("CLE=secret-reel\n", encoding="utf-8")
            (paquet / "box_state.json").write_text("{}", encoding="utf-8")
            (paquet / "serveur.pem").write_text("cle-privee", encoding="utf-8")
            cache = paquet / "__pycache__"
            cache.mkdir()
            (cache / "main.cpython-312.pyc").write_bytes(b"\x00\x01")
            pio = paquet / ".pio" / "build"
            pio.mkdir(parents=True)
            (pio / "firmware.bin").write_bytes(b"\x7fELF")

            releases = base / "releases"
            with patch.object(br, "RELEASES", releases):
                archive = br.construire_archive("demo", paquet)

            self.assertTrue(archive.is_file())
            with tarfile.open(archive) as tar:
                noms = tar.getnames()
            joints = "\n".join(noms)

            self.assertIn("demo/src/main.py", joints)
            self.assertIn("demo/.env.example", joints)
            for interdit in ("demo/.env\n", "box_state.json", "serveur.pem",
                             "__pycache__", ".pio"):
                with self.subTest(interdit=interdit):
                    self.assertNotIn(interdit, joints)
            # Et aucun contenu de secret ne fuit par un autre chemin.
            with tarfile.open(archive) as tar:
                for membre in tar.getmembers():
                    if membre.isfile():
                        contenu = tar.extractfile(membre)
                        donnees = contenu.read() if contenu else b""
                        self.assertNotIn(b"secret-reel", donnees)


if __name__ == "__main__":
    unittest.main()
