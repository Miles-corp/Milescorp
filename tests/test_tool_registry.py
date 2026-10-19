"""Tests du registre d'outils MILES.

Vérifie que :
- un outil peut être enregistré et récupéré ;
- un outil inconnu retourne None ;
- la liste des outils est correcte ;
- un outil peut être retiré du registre.
"""

from __future__ import annotations

import unittest

from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry


def _sample_handler() -> str:
    return "ok"


class TestToolRegistry(unittest.TestCase):
    """Tests de la classe ToolRegistry."""

    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.tool = ToolDefinition(
            tool_id="test_tool",
            description="Outil de test",
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=10,
            handler=_sample_handler,
        )

    def test_register_and_get_tool(self) -> None:
        self.registry.register(self.tool)
        retrieved = self.registry.get_tool("test_tool")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.tool_id, "test_tool")
        self.assertEqual(retrieved.description, "Outil de test")

    def test_get_unknown_tool_returns_none(self) -> None:
        self.assertIsNone(self.registry.get_tool("inconnu"))

    def test_list_tools(self) -> None:
        self.registry.register(self.tool)
        self.registry.register(
            ToolDefinition(
                tool_id="autre_outil",
                description="Autre",
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=_sample_handler,
            )
        )
        tools = self.registry.list_tools()
        self.assertIn("autre_outil", tools)
        self.assertIn("test_tool", tools)
        self.assertEqual(len(tools), 2)

    def test_is_registered(self) -> None:
        self.assertFalse(self.registry.is_registered("test_tool"))
        self.registry.register(self.tool)
        self.assertTrue(self.registry.is_registered("test_tool"))

    def test_unregister(self) -> None:
        self.registry.register(self.tool)
        self.assertTrue(self.registry.unregister("test_tool"))
        self.assertFalse(self.registry.is_registered("test_tool"))
        self.assertFalse(self.registry.unregister("inexistant"))

    def test_invalid_risk_level_raises(self) -> None:
        with self.assertRaises(ValueError):
            ToolDefinition(
                tool_id="mauvais",
                description="x",
                risk_level="CRITIQUE",  # type: ignore[arg-type]
                required_permissions=(),
                timeout_seconds=5,
                handler=_sample_handler,
            )


if __name__ == "__main__":
    unittest.main()
