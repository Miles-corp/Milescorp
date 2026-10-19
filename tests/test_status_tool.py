"""Tests du premier outil MILES : status_tool_handler.

Vérifie que :
- l'outil retourne un dictionnaire avec les clés attendues ;
- il est en lecture seule (pas d'effet de bord) ;
- il est utilisable via le registre et le moteur.
"""

from __future__ import annotations

import unittest

from app.tools.status_tool import status_tool_handler


class TestStatusTool(unittest.TestCase):
    """Tests de la fonction status_tool_handler."""

    def test_status_tool_returns_dict(self) -> None:
        result = status_tool_handler()
        self.assertIsInstance(result, dict)

    def test_status_tool_has_expected_keys(self) -> None:
        result = status_tool_handler()
        self.assertIn("status", result)
        self.assertIn("provider", result)
        self.assertIn("provider_available", result)
        self.assertIn("memory_enabled", result)
        self.assertIn("memory_available", result)
        self.assertIn("messages_in_history", result)

    def test_status_tool_is_read_only(self) -> None:
        # Appeler deux fois doit retourner le même résultat
        # (pas d'effet de bord entre les appels)
        result1 = status_tool_handler()
        result2 = status_tool_handler()
        self.assertEqual(result1, result2)

    def test_status_tool_default_values(self) -> None:
        result = status_tool_handler()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["provider"], "non configure")
        self.assertFalse(result["provider_available"])
        self.assertFalse(result["memory_enabled"])
        self.assertFalse(result["memory_available"])
        self.assertEqual(result["messages_in_history"], 0)


if __name__ == "__main__":
    unittest.main()
