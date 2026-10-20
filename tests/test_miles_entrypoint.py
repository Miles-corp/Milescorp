"""Tests de non-régression S-001 : import de PersistentMemoryError dans miles.py.

Le chemin d'échec de l'initialisation de la mémoire persistante
(`except PersistentMemoryError` dans `miles.main`) ne doit plus provoquer de
NameError. Le comportement nominal de la mémoire persistante doit rester
inchangé.

Ces tests n'utilisent aucun fournisseur IA réel ni clé API.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

import miles
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.security.paths import project_root


class TestMilesMemoryErrorHandling(unittest.TestCase):
    """S-001 : la clause except PersistentMemoryError doit être résolvable."""

    def test_name_error_absent_quand_memoire_echoue(self) -> None:
        """Un échec d'initialisation mémoire est rattrapé, pas un NameError.

        Sans l'import correct de PersistentMemoryError, l'évaluation de la
        clause `except` lève NameError et le programme plante au lieu de
        poursuivre sans mémoire persistante.
        """
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"MILES_MEMORY_ENABLED": "true"}):
            with mock.patch(
                "miles.PersistentMemory",
                side_effect=PersistentMemoryError("échec simulé"),
            ):
                with mock.patch.object(miles.CLI, "run", return_value=None):
                    with redirect_stderr(stderr):
                        exit_code = miles.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("mémoire persistante non disponible", stderr.getvalue())

    def test_name_error_absent_avec_base_inaccessible(self) -> None:
        """Un chemin d'accès interdit produit un avertissement, pas un NameError."""
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"MILES_MEMORY_ENABLED": "true"}):
            with mock.patch(
                "miles.PersistentMemory",
                side_effect=PersistentMemoryError("chemin invalide"),
            ):
                with mock.patch.object(miles.CLI, "run", return_value=None):
                    with redirect_stderr(stderr):
                        exit_code = miles.main([])

        self.assertEqual(exit_code, 0)
        self.assertIn("mémoire persistante non disponible", stderr.getvalue())

    def test_memoire_active_transmise_au_cli(self) -> None:
        """Comportement nominal inchangé : la mémoire disponible est transmise.

        La base est créée dans le dossier data/ du projet : c'est l'une des
        racines autorisées (S-005).
        """
        tmpdir = tempfile.mkdtemp(
            prefix="miles_test_entrypoint_", dir=str(project_root() / "data")
        )
        try:
            env = {
                "MILES_MEMORY_ENABLED": "true",
                "MILES_MEMORY_DB_PATH": os.path.join(tmpdir, "memory.db"),
            }
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with redirect_stderr(io.StringIO()):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            memory = mock_cli.call_args.kwargs["memory"]
            self.assertIsInstance(memory, PersistentMemory)
            self.assertTrue(memory.is_available)
            memory.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_base_memoire_hors_racines_refusee(self) -> None:
        """S-005 : une base mémoire hors des racines autorisées est refusée."""
        tmpdir = tempfile.mkdtemp(prefix="miles_test_entrypoint_out_")
        try:
            env = {
                "MILES_MEMORY_ENABLED": "true",
                "MILES_MEMORY_DB_PATH": os.path.join(tmpdir, "memory.db"),
            }
            stderr = io.StringIO()
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with redirect_stderr(stderr):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            self.assertIsNone(mock_cli.call_args.kwargs["memory"])
            self.assertIn(
                "mémoire persistante non disponible", stderr.getvalue()
            )
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "memory.db")))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_memoire_desactivee_ne_demande_pas_de_base(self) -> None:
        """Mémoire désactivée : aucune base créée, memory=None transmis au CLI.

        Ce test couvre la configuration mémoire corrigée (MILES_MEMORY_ENABLED
        interprété correctement) : la désactivation doit être effective.
        """
        tmpdir = tempfile.mkdtemp(prefix="miles_test_entrypoint_")
        try:
            db_path = os.path.join(tmpdir, "memory.db")
            env = {
                "MILES_MEMORY_ENABLED": "false",
                "MILES_MEMORY_DB_PATH": db_path,
            }
            with mock.patch.dict(os.environ, env):
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with redirect_stderr(io.StringIO()):
                        exit_code = miles.main([])

            self.assertEqual(exit_code, 0)
            self.assertIsNone(mock_cli.call_args.kwargs["memory"])
            self.assertFalse(os.path.exists(db_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
