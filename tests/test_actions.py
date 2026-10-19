"""Tests des actions locales et du validateur de sécurité.

Ces tests n'exécutent aucune commande shell arbitraire et ne modifient
aucun fichier du système. Ils utilisent ActionValidator avec des actions simulées.
"""

from __future__ import annotations

import unittest

from app.security.validator import ActionValidator, ActionResult


class TestActionValidator(unittest.TestCase):
    """Tests du validateur d'actions locales."""

    def setUp(self) -> None:
        self.validator = ActionValidator(
            allowed_actions=["datetime", "workdir", "list_files"]
        )

    def test_allowed_action_datetime(self) -> None:
        result = self.validator.execute("datetime", {})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.output)
        self.assertIsNone(result.error)

    def test_allowed_action_workdir(self) -> None:
        result = self.validator.execute("workdir", {})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.output)

    def test_unknown_action_refused(self) -> None:
        result = self.validator.execute("supprimer_fichier", {})
        self.assertFalse(result.allowed)
        self.assertIn("non autorisée", result.reason)

    def test_empty_action_name_refused(self) -> None:
        result = self.validator.execute("", {})
        self.assertFalse(result.allowed)

    def test_is_allowed(self) -> None:
        self.assertTrue(self.validator.is_allowed("datetime"))
        self.assertFalse(self.validator.is_allowed("rm"))
        self.assertFalse(self.validator.is_allowed("shell"))

    def test_list_files_invalid_path(self) -> None:
        result = self.validator.execute("list_files", {"path": "/etc/../etc"})
        # L'action est autorisée mais le chemin est validé dans l'implémentation
        self.assertTrue(result.allowed)

    def test_invalid_arguments_type_error(self) -> None:
        # list_files attend un argument 'path' de type str ; passer un int provoque TypeError
        result = self.validator.execute("list_files", {"path": 123})
        self.assertTrue(result.allowed)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
