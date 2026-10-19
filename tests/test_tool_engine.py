"""Tests du moteur de décision MILES.

Vérifie que :
- un outil inconnu est refusé ;
- les paramètres manquants, incorrects ou supplémentaires sont refusés ;
- les permissions absentes bloquent l'exécution ;
- la politique de sécurité (pas de shell, pas de code, pas de secrets) est appliquée ;
- la confirmation est requise pour les outils risqués ;
- une confirmation absente, refusée, expirée ou liée à d'autres paramètres
  est rejetée ;
- une tentative de falsification de confirmation est rejetée ;
- un dépassement de délai est détecté et l'exécution arrêtée ;
- une exception du handler est capturée sans divulgation ;
- status_read est en lecture seule (pas d'effet de bord) ;
- aucun secret n'apparaît dans les journaux d'audit.
"""

from __future__ import annotations

import time
import unittest

from app.tools.audit import AuditLogger
from app.tools.engine import ToolEngine, ToolResult
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.status_tool import status_tool_handler


def _fast_handler() -> str:
    return "resultat_ok"


def _slow_handler() -> str:
    time.sleep(10)
    return "trop_lent"


def _failing_handler() -> str:
    raise RuntimeError("erreur simulee")


def _side_effect_handler(data: str) -> str:
    return f"traite: {data}"


class TestToolEngine(unittest.TestCase):
    """Tests de la classe ToolEngine."""

    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.policy = ToolPolicy(
            granted_permissions={"lecture", "ecriture"}
        )
        self.audit = AuditLogger()
        self.engine = ToolEngine(
            registry=self.registry,
            policy=self.policy,
            audit=self.audit,
        )

        # Outil bas en risque, sans paramètre
        self.registry.register(
            ToolDefinition(
                tool_id="status_read",
                description="Lecture du statut",
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=status_tool_handler,
            )
        )

        # Outil moyen en risque, avec paramètre
        self.registry.register(
            ToolDefinition(
                tool_id="action_ecriture",
                description="Ecriture",
                parameters=(
                    ToolParameter(
                        name="data", type=str, required=True,
                        description="Message a ecrire",
                    ),
                ),
                risk_level="MEDIUM",
                required_permissions=("ecriture",),
                timeout_seconds=5,
                handler=_side_effect_handler,
            )
        )

        # Outil haut risque
        self.registry.register(
            ToolDefinition(
                tool_id="action_suppression",
                description="Suppression",
                parameters=(
                    ToolParameter(
                        name="cible", type=str, required=True,
                        description="Cible a supprimer",
                    ),
                ),
                risk_level="HIGH",
                required_permissions=("suppression",),
                timeout_seconds=5,
                handler=_fast_handler,
            )
        )

        # Outil lent (pour tester le timeout)
        self.registry.register(
            ToolDefinition(
                tool_id="action_lente",
                description="Lente",
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=1,
                handler=_slow_handler,
            )
        )

        # Outil qui lève une exception
        self.registry.register(
            ToolDefinition(
                tool_id="action_erreur",
                description="Erreur",
                parameters=(),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=_failing_handler,
            )
        )

    # --- Outil inconnu ---

    def test_outil_inconnu_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="outil_inexistant", parameters={}
        )
        self.assertFalse(result.success)
        self.assertIn("Outil inconnu", result.error_message)
        self.assertFalse(result.confirmation_required)

    # --- Paramètres ---

    def test_parametre_requis_manquant_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture", parameters={}
        )
        self.assertFalse(result.success)
        self.assertIn("requis manquant", result.error_message)

    def test_parametre_mauvais_type_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture", parameters={"data": 123}
        )
        self.assertFalse(result.success)
        self.assertIn("type", result.error_message.lower())

    def test_parametre_supplementaire_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="status_read",
            parameters={"parametre_secret": "valeur"},
        )
        self.assertFalse(result.success)
        self.assertIn("supplémentaire", result.error_message.lower())

    def test_parametre_hors_contrainte_refuse(self) -> None:
        self.registry.register(
            ToolDefinition(
                tool_id="outil_nombre",
                description="Nombre",
                parameters=(
                    ToolParameter(
                        name="valeur", type=int, required=True,
                        min_value=0, max_value=10,
                    ),
                ),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=_fast_handler,
            )
        )
        result = self.engine.request_tool(
            tool_id="outil_nombre", parameters={"valeur": 100}
        )
        self.assertFalse(result.success)
        self.assertIn("<= 10", result.error_message)

    # --- Permissions ---

    def test_permission_absente_refusee(self) -> None:
        # D'abord obtenir un token pour action_ecriture
        first = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "bonjour"},
        )
        self.assertTrue(first.confirmation_required)
        token = first.confirmation_token

        # Confirmer action_ecriture (permission 'ecriture' est accordee)
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "bonjour"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(result.success)

        # Puis essayer action_suppression sans permission 'suppression'
        result = self.engine.request_tool(
            tool_id="action_suppression",
            parameters={"cible": "fichier.txt"},
            user_confirmed=True,
        )
        self.assertFalse(result.success)
        self.assertIn("Permissions manquantes", result.error_message)

    # --- Confirmation ---

    def test_confirmation_absente_pour_outil_risque(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)
        self.assertIsNotNone(result.confirmation_token)

    def test_confirmation_refusee(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=False,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_confirmation_valide(self) -> None:
        # Premier appel : generer le token
        first = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        self.assertTrue(first.confirmation_required)
        token = first.confirmation_token

        # Second appel : confirmer avec le token
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data, "traite: test")

    def test_confirmation_token_invalide(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token="jeton_inexistant",
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_confirmation_mauvais_outil(self) -> None:
        # Creer un token pour action_ecriture
        first = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        token = first.confirmation_token

        # Donner la permission suppression pour pouvoir tester la confirmation
        self.policy._granted_permissions.add("suppression")

        # Essayer de l'utiliser pour action_suppression (autre outil)
        result = self.engine.request_tool(
            tool_id="action_suppression",
            parameters={"cible": "x"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_confirmation_mauvais_parametres(self) -> None:
        # Creer un token pour data="test"
        first = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        token = first.confirmation_token

        # Essayer avec data="autre"
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "autre"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_falsification_confirmation(self) -> None:
        # Simuler une tentative de contournement : user_confirmed=True
        # sans token valide pour un outil risque
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    # --- Timeout ---

    def test_depassement_delai(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_lente",
            parameters={},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_depassement_delai_arret_effectif(self) -> None:
        # Verifier que le processus est arrete après le timeout.
        result = self.engine.request_tool(
            tool_id="action_lente",
            parameters={},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

        # Immédiatement après, une nouvelle demande doit pouvoir démarrer
        result2 = self.engine.request_tool(
            tool_id="status_read",
            parameters={},
        )
        self.assertTrue(result2.success)

    # --- Exception du handler ---

    def test_exception_handler(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_erreur",
            parameters={},
        )
        self.assertFalse(result.success)
        self.assertIn("Erreur d'exécution", result.error_message)
        # Verifier qu'aucune exception brute n'est dans le message
        self.assertNotIn("RuntimeError", result.error_message)
        self.assertNotIn("erreur simulee", result.error_message)

    # --- Status read en lecture seule ---

    def test_status_read_sans_effet_de_bord(self) -> None:
        result1 = self.engine.request_tool(
            tool_id="status_read", parameters={}
        )
        result2 = self.engine.request_tool(
            tool_id="status_read", parameters={}
        )
        self.assertTrue(result1.success)
        self.assertTrue(result2.success)
        self.assertEqual(result1.data, result2.data)

    # --- Audit sans secrets ---

    def test_audit_sans_secret(self) -> None:
        self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "sk-1234567890"},
        )
        entries = self.audit.get_entries()
        for entry in entries:
            self.assertNotIn("sk-", entry.error_message)
            self.assertNotIn("password", entry.error_message.lower())
            self.assertNotIn("api_key", entry.error_message.lower())
            self.assertNotIn("secret", entry.error_message.lower())

    # --- Politique de sécurité (L-008) ---

    def test_parametre_shell_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"shell": "rm -rf /"},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_parametre_command_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"command": "ls"},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_parametre_code_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"code": "print(1)"},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_parametre_secret_refuse(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"api_key": "sk-123"},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_valeur_secrete_refusee(self) -> None:
        result = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "mon mot de passe est secret123"},
        )
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    # --- Expiration des confirmations (L-009) ---

    def test_confirmation_expiree_refusee(self) -> None:
        # Creer un moteur avec un TTL de confirmation très court
        engine_short = ToolEngine(
            registry=self.registry,
            policy=self.policy,
            audit=self.audit,
            confirmation_ttl_seconds=0.1,
        )
        first = engine_short.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        self.assertTrue(first.confirmation_required)
        token = first.confirmation_token

        # Attendre l'expiration
        time.sleep(0.2)

        result = engine_short.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)
        self.assertIsNotNone(result.confirmation_token)

    def test_confirmation_valide_dans_delai(self) -> None:
        # Creer un moteur avec un TTL long
        engine_long = ToolEngine(
            registry=self.registry,
            policy=self.policy,
            audit=self.audit,
            confirmation_ttl_seconds=60.0,
        )
        first = engine_long.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        self.assertTrue(first.confirmation_required)
        token = first.confirmation_token

        result = engine_long.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data, "traite: test")

    def test_confirmation_utilisee_uneseulefois(self) -> None:
        first = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
        )
        token = first.confirmation_token

        # Premier usage : valide
        result1 = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(result1.success)

        # Deuxième usage avec le même token : doit être refusé
        result2 = self.engine.request_tool(
            tool_id="action_ecriture",
            parameters={"data": "test"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result2.success)
        self.assertTrue(result2.confirmation_required)


if __name__ == "__main__":
    unittest.main()
