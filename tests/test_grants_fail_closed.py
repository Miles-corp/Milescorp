"""Tests fail-closed du contrat GrantChecker (S-E3-04, audit interne E3).

Un grant ne peut jamais être retourné sans identifiant d'acteur : l'absence
de preuve d'appartenance (actor_id None ou vide) vaut refus, pas autorisation.
"""

from __future__ import annotations

import unittest

from app.tools.grants import GrantRegistry


class TestGrantFailClosed(unittest.TestCase):
    def _registry_with_grant(self) -> GrantRegistry:
        registry = GrantRegistry()
        registry.issue(
            "session-legitime",
            "mission-1",
            ["action_list_files"],
        )
        return registry

    def test_none_actor_is_refused(self) -> None:
        registry = self._registry_with_grant()
        grant_id = registry.authorize(
            "action_list_files", {}, "mission-1", None
        )
        self.assertIsNone(grant_id)

    def test_empty_actor_is_refused(self) -> None:
        registry = self._registry_with_grant()
        grant_id = registry.authorize(
            "action_list_files", {}, "mission-1", ""
        )
        self.assertIsNone(grant_id)

    def test_none_context_is_refused(self) -> None:
        """S-E3-04b (audit B) : sans contexte de mission, aucun grant."""
        registry = self._registry_with_grant()
        grant_id = registry.authorize(
            "action_list_files", {}, None, "session-legitime"
        )
        self.assertIsNone(grant_id)

    def test_legitimate_actor_still_works(self) -> None:
        registry = self._registry_with_grant()
        grant_id = registry.authorize(
            "action_list_files", {}, "mission-1", "session-legitime"
        )
        self.assertIsNotNone(grant_id)
        self.assertTrue(registry.consume(grant_id))

    def test_wrong_actor_still_refused(self) -> None:
        registry = self._registry_with_grant()
        self.assertIsNone(
            registry.authorize(
                "action_list_files", {}, "mission-1", "session-autre"
            )
        )


if __name__ == "__main__":
    unittest.main()
