"""Tests de non-régression S-005 : confinement des chemins aux racines autorisées.

Les racines autorisées sont le répertoire du projet et son dossier de données
``data/``.

Les tests de liens symboliques sont ignorés sous Windows : la création d'un
lien symbolique y requiert un privilège (mode Développeur ou Administrateur)
qui n'est pas disponible sur un poste standard. Ils s'exécutent sous
Debian 13. La résolution canonique elle-même est portable et testée partout.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.security.paths import (
    PathSecurityError,
    canonical_path,
    default_allowed_roots,
    is_within,
    project_root,
    resolve_authorized_path,
)
from app.security.validator import ActionValidator

# Création d'un lien symbolique : possible nativement sous Linux.
# Sous Windows, os.symlink peut échouer (privilège insuffisant).
try:
    os.symlink("cible", os.devnull)
    _SYMLINK_SUPPORTED = True
except (OSError, NotImplementedError, AttributeError):
    _SYMLINK_SUPPORTED = False


class TestAllowedRoots(unittest.TestCase):
    """Racines autorisées et résolution canonique."""

    def test_racine_du_projet_contient_le_package_app(self) -> None:
        root = project_root()
        self.assertTrue((root / "app").is_dir())

    def test_racines_par_defaut_projet_et_data(self) -> None:
        roots = default_allowed_roots()
        self.assertEqual(len(roots), 2)
        self.assertIn(project_root(), roots)
        self.assertIn(project_root() / "data", roots)

    def test_prefixe_similaire_non_confondu(self) -> None:
        """/data-secret ne doit pas être considéré comme contenu dans /data."""
        root = Path("/data")
        self.assertFalse(is_within(Path("/data-secret"), root))
        self.assertTrue(is_within(Path("/data"), root))
        self.assertTrue(is_within(Path("/data/x"), root))

    def test_chemin_absolu_dans_le_projet_autorise(self) -> None:
        resolved = resolve_authorized_path(str(project_root() / "app"))
        self.assertTrue(resolved.is_dir())

    def test_chemin_absolu_hors_racines_refuse(self) -> None:
        with self.assertRaises(PathSecurityError):
            resolve_authorized_path("/etc")

    def test_chemin_absolu_temporaire_hors_racines_refuse(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="miles_test_paths_")
        try:
            with self.assertRaises(PathSecurityError):
                resolve_authorized_path(tmpdir)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_traversee_ou_dossier_refusee(self) -> None:
        """Une traversée '..' sortant de la racine est refusée."""
        traversal = os.path.join(str(project_root()), "..", "..", "etc")
        with self.assertRaises(PathSecurityError):
            resolve_authorized_path(traversal)

    def test_traversee_interne_autorisee(self) -> None:
        """Une traversée '..' restant dans la racine est autorisée."""
        inside = os.path.join(str(project_root()), "app", "..", "config")
        resolved = resolve_authorized_path(inside)
        self.assertTrue(resolved.is_dir())

    def test_chemin_relatif_resolu_par_racine_projet(self) -> None:
        resolved = resolve_authorized_path("data")
        self.assertEqual(resolved, canonical_path(project_root() / "data"))

    def test_canonical_path_resout_les_point_points(self) -> None:
        raw = os.path.join(str(project_root()), "app", "..", "app")
        self.assertEqual(canonical_path(raw), canonical_path(project_root() / "app"))


class TestSymlinkConfinement(unittest.TestCase):
    """Les liens symboliques ne doivent pas permettre de sortir des racines.

    Ces tests sont ignorés sous Windows lorsque la création de lien
    symbolique n'est pas permise (privilège insuffisant). Ils s'exécutent
    sous Debian 13.
    """

    def setUp(self) -> None:
        if not _SYMLINK_SUPPORTED:
            self.skipTest(
                "Création de lien symbolique non permise sur cette plateforme "
                "(Windows requiert un privilège). Test exécuté sous Debian 13."
            )
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_symlink_")
        self.outside = os.path.join(self.tmpdir, "outside")
        os.makedirs(self.outside, exist_ok=True)
        with open(os.path.join(self.outside, "secret.txt"), "w", encoding="utf-8") as fh:
            fh.write("donnee sensible")
        self.link = os.path.join(str(project_root()), "data", "_test_lien_sortant")
        self.internal = os.path.join(str(project_root()), "data", "_test_lien_interne")
        try:
            os.symlink(self.outside, self.link)
        except OSError:
            self.skipTest("Privilège insuffisant pour créer un lien symbolique.")
        os.makedirs(self.internal, exist_ok=True)

    def tearDown(self) -> None:
        for path in (getattr(self, "link", None), getattr(self, "internal", None)):
            if path and os.path.islink(path):
                os.unlink(path)
            elif path and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_lien_symbolique_sortant_refuse(self) -> None:
        """Un lien vers un dossier extérieur doit être refusé."""
        with self.assertRaises(PathSecurityError):
            resolve_authorized_path(self.link)

    def test_lien_symbolique_sortant_refuse_par_list_files(self) -> None:
        validator = ActionValidator()
        result = validator.execute("list_files", {"path": self.link})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.output)
        self.assertIn("refus", result.output.lower())

    def test_lien_symbolique_interne_accepte(self) -> None:
        """Un lien vers un dossier autorisé doit rester utilisable."""
        resolved = resolve_authorized_path(self.internal)
        self.assertTrue(resolved.is_dir())


class TestListFilesConfinement(unittest.TestCase):
    """list_files ne doit sortir d'aucune racine autorisée."""

    def setUp(self) -> None:
        self.validator = ActionValidator()

    def test_liste_du_repertoire_du_projet(self) -> None:
        result = self.validator.execute("list_files", {"path": str(project_root())})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.output)
        self.assertIn("app", result.output)

    def test_liste_du_dossier_data(self) -> None:
        result = self.validator.execute("list_files", {"path": "data"})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.output)

    def test_chemin_absolu_hors_racines_refuse(self) -> None:
        result = self.validator.execute("list_files", {"path": "/etc"})
        self.assertTrue(result.allowed)
        self.assertIn("refus", (result.output or "").lower())

    def test_traversee_refusee(self) -> None:
        result = self.validator.execute(
            "list_files", {"path": os.path.join(str(project_root()), "..", "..")}
        )
        self.assertTrue(result.allowed)
        self.assertIn("refus", (result.output or "").lower())

    def test_chemin_inexistant_autorise_mais_signale(self) -> None:
        """Un chemin autorisé mais inexistant garde un message explicite."""
        result = self.validator.execute(
            "list_files", {"path": os.path.join(str(project_root()), "dossier_absent_xyz")}
        )
        self.assertTrue(result.allowed)
        self.assertIn("n'existe pas", (result.output or ""))


class TestMemoryDbPathConfinement(unittest.TestCase):
    """Le chemin de la base mémoire est confiné aux racines autorisées."""

    def test_chemin_memoire_par_defaut_dans_data(self) -> None:
        resolved = resolve_authorized_path("data/memory.db")
        self.assertEqual(resolved.parent, canonical_path(project_root() / "data"))

    def test_chemin_memoire_absolu_hors_racines_refuse(self) -> None:
        tmpdir = tempfile.mkdtemp(prefix="miles_test_dbpath_")
        try:
            with self.assertRaises(PathSecurityError):
                resolve_authorized_path(os.path.join(tmpdir, "memory.db"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_chemin_memoire_traversee_refuse(self) -> None:
        with self.assertRaises(PathSecurityError):
            resolve_authorized_path(
                os.path.join(str(project_root()), "..", "..", "memory.db")
            )


if __name__ == "__main__":
    unittest.main()
