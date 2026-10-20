"""Test de non-régression : résultat volumineux (buffer de tube Windows).

Un résultat d'outil plus volumineux que le tampon du tube (8 Kio sous
Windows) bloquait l'exécution : l'enfant attendait l'écriture dans le
tube, le parent attendait la fin du processus, et le délai d'attente
expirait à tort.

Ce test vérifie qu'un résultat de 40 Kio est transmis sans délai.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from app.security.paths import project_root
from app.tools.grants import GrantRegistry
from app.tools.service import ToolService


class TestLargeResult(unittest.TestCase):
    """Un résultat volumineux ne doit pas expirer."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(
            prefix="miles_gros_resultat_", dir=str(project_root())
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_lecture_d_un_fichier_volumineux(self) -> None:
        grants = GrantRegistry()
        service = ToolService(grant_checker=grants)
        grants.issue(
            session_id="s",
            mission_id="m",
            tool_ids={"action_read_file"},
            allowed_roots=[self.tmpdir],
        )
        chemin = os.path.join(self.tmpdir, "gros.txt")
        with open(chemin, "w", encoding="utf-8") as fh:
            fh.write("a" * 40000)

        result = service.request_tool(
            "action_read_file",
            {"path": chemin, "max_bytes": 40000},
            context_id="m",
            actor_id="s",
        )
        self.assertTrue(result.success, result.error_message)
        self.assertEqual(len(result.data), 40000)

    def test_resultat_volumineux_au_dela_du_tampon(self) -> None:
        """Le texte intégral (40 Kio) est bien transmis au parent."""
        grants = GrantRegistry()
        service = ToolService(grant_checker=grants)
        grants.issue(
            session_id="s",
            mission_id="m",
            tool_ids={"action_read_file"},
            allowed_roots=[self.tmpdir],
        )
        chemin = os.path.join(self.tmpdir, "gros.txt")
        with open(chemin, "w", encoding="utf-8") as fh:
            fh.write("b" * 40000)

        result = service.request_tool(
            "action_read_file",
            {"path": chemin, "max_bytes": 40000},
            context_id="m",
            actor_id="s",
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.data), 8192)


if __name__ == "__main__":
    unittest.main()
