"""Tests de la politique de sécurité MILES.

Vérifie que :
- les permissions sont correctement vérifiées ;
- les paramètres interdits (shell, code, secrets) sont rejetés ;
- le niveau de risque détermine la nécessité d'une confirmation.
"""

from __future__ import annotations

import unittest

from app.tools.policy import ToolPolicy


class TestToolPolicy(unittest.TestCase):
    """Tests de la classe ToolPolicy."""

    def setUp(self) -> None:
        self.policy = ToolPolicy(granted_permissions={"lecture", "ecriture"})

    def test_has_permission_granted(self) -> None:
        self.assertTrue(self.policy.has_permission("lecture"))
        self.assertTrue(self.policy.has_permission("ecriture"))

    def test_has_permission_not_granted(self) -> None:
        self.assertFalse(self.policy.has_permission("suppression"))
        self.assertFalse(self.policy.has_permission("admin"))

    def test_has_all_permissions(self) -> None:
        self.assertTrue(
            self.policy.has_all_permissions(("lecture", "ecriture"))
        )
        self.assertFalse(
            self.policy.has_all_permissions(("lecture", "suppression"))
        )
        self.assertFalse(self.policy.has_all_permissions(("admin",)))

    def test_validate_no_shell_access_rejected(self) -> None:
        forbidden_params = [
            {"shell": "ls"},
            {"command": "rm -rf /"},
            {"cmd": "dir"},
            {"exec": "something"},
            {"eval": "1+1"},
            {"system": "shutdown"},
        ]
        for params in forbidden_params:
            with self.assertRaises(PermissionError):
                self.policy.validate_no_shell_access(params)

    def test_validate_no_shell_access_allowed(self) -> None:
        # Ne doit pas lever d'exception
        self.policy.validate_no_shell_access({"fichier": "test.txt"})
        self.policy.validate_no_shell_access({})

    def test_validate_no_code_execution_rejected(self) -> None:
        forbidden_params = [
            {"code": "print(1)"},
            {"script": "alert(1)"},
            {"python": "import os"},
            {"javascript": "eval('1')"},
            {"shell_code": "whoami"},
            {"source": "open('/etc/passwd')"},
        ]
        for params in forbidden_params:
            with self.assertRaises(PermissionError):
                self.policy.validate_no_code_execution(params)

    def test_validate_no_code_execution_allowed(self) -> None:
        self.policy.validate_no_code_execution({"message": "bonjour"})
        self.policy.validate_no_code_execution({})

    def test_validate_no_secret_access_rejected(self) -> None:
        forbidden_params = [
            {"password": "secret123"},
            {"secret": "ma_cle"},
            {"api_key": "sk-123"},
            {"token": "abc123"},
            {"private_key": "-----BEGIN"},
            {"credential": "user:pass"},
        ]
        for params in forbidden_params:
            with self.assertRaises(PermissionError):
                self.policy.validate_no_secret_access(params)

    def test_validate_no_secret_access_allowed(self) -> None:
        self.policy.validate_no_secret_access({"nom": "utilisateur"})
        self.policy.validate_no_secret_access({})

    def test_requires_human_confirmation(self) -> None:
        self.assertFalse(self.policy.requires_human_confirmation("LOW"))
        self.assertTrue(self.policy.requires_human_confirmation("MEDIUM"))
        self.assertTrue(self.policy.requires_human_confirmation("HIGH"))

    def test_is_risk_level_valid(self) -> None:
        self.assertTrue(self.policy.is_risk_level_valid("LOW"))
        self.assertTrue(self.policy.requires_human_confirmation("MEDIUM"))
        self.assertTrue(self.policy.is_risk_level_valid("HIGH"))
        self.assertFalse(self.policy.is_risk_level_valid("CRITIQUE"))


if __name__ == "__main__":
    unittest.main()
