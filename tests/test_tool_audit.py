"""Tests du journal d'audit MILES.

Vérifie que :
- une entrée peut être ajoutée et récupérée ;
- le journal peut être vidé ;
- aucun secret n'est stocké dans les entrées.
"""

from __future__ import annotations

import unittest

from app.tools.audit import AuditLogger


class TestAuditLogger(unittest.TestCase):
    """Tests de la classe AuditLogger."""

    def setUp(self) -> None:
        self.audit = AuditLogger()

    def test_record_and_get_entries(self) -> None:
        self.audit.record(
            tool_id="status_read",
            user_confirmed=True,
            permission_granted=True,
            result="success",
        )
        entries = self.audit.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].tool_id, "status_read")
        self.assertTrue(entries[0].user_confirmed)
        self.assertTrue(entries[0].permission_granted)
        self.assertEqual(entries[0].result, "success")

    def test_multiple_entries(self) -> None:
        self.audit.record(
            tool_id="outil_a", user_confirmed=False, permission_granted=False,
            result="refused", error_message="Outil inconnu",
        )
        self.audit.record(
            tool_id="outil_b", user_confirmed=True, permission_granted=True,
            result="success",
        )
        self.assertEqual(len(self.audit.get_entries()), 2)

    def test_clear(self) -> None:
        self.audit.record(
            tool_id="test", user_confirmed=True, permission_granted=True,
            result="success",
        )
        self.assertEqual(len(self.audit.get_entries()), 1)
        self.audit.clear()
        self.assertEqual(len(self.audit.get_entries()), 0)

    def test_no_secret_in_audit(self) -> None:
        # Aucun secret ne doit apparaître dans les entrées d'audit
        self.audit.record(
            tool_id="status_read",
            user_confirmed=True,
            permission_granted=True,
            result="success",
            error_message="",
            parameters_hash="abc123",
        )
        entry = self.audit.get_entries()[0]
        self.assertNotIn("sk-", entry.error_message)
        self.assertNotIn("password", entry.error_message.lower())
        self.assertNotIn("api_key", entry.error_message.lower())
        self.assertNotIn("secret", entry.error_message.lower())
        self.assertNotIn("token", entry.error_message.lower())


if __name__ == "__main__":
    unittest.main()
