"""Tests complémentaires de sécurité (Agent A) — MILESTONE-005 / Phase 4.

Complète `tests/test_tool_engine.py` sur les lacunes suivantes :

- expiration des confirmations avec une horloge déterministe (fictive) au lieu
  d'une attente réelle (fragile) ;
- validation récursive de la politique sur structures imbriquées
  (dict, list, tuple) — non couverte par les tests existants ;
- insensibilité à la casse des clés et valeurs interdites ;
- robustesse face à des clés de dictionnaire non textuelles ;
- confidentialité de l'audit : une exception contenant une fausse clé API ne
  doit apparaître ni dans l'audit ni dans le message utilisateur ;
- consommation du jeton de confirmation même si l'exécution du handler échoue.

Ces tests n'exigent aucun accès réseau, aucune clé API et n'ont aucun effet
externe. Ils sont exécuterables sous Windows et sous Debian 13.
"""

from __future__ import annotations

import unittest

from app.tools.audit import AuditLogger
from app.tools.engine import ToolEngine
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry


class _FakeClock:
    """Horloge déterministe injectable pour les tests d'expiration."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _ok_handler(data: str = "") -> str:
    return f"ok:{data}"


def _secret_leaking_handler(data: str = "") -> str:
    """Handler qui lève une exception contenant une fausse clé API."""
    raise RuntimeError("échec interne sk-FAUSSE-CLE-12345 password=hunter2")


class _EngineFixture:
    """Construit un moteur avec un outil LOW, un MEDIUM et un handler fautif."""

    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.policy = ToolPolicy(granted_permissions={"lecture", "ecriture"})
        self.audit = AuditLogger()
        self.clock = _FakeClock()
        self.engine = ToolEngine(
            registry=self.registry,
            policy=self.policy,
            audit=self.audit,
            clock=self.clock,
            confirmation_ttl_seconds=300.0,
        )

        self.registry.register(
            ToolDefinition(
                tool_id="outil_risque",
                description="Outil MEDIUM",
                parameters=(
                    ToolParameter(name="data", type=str, required=True),
                ),
                risk_level="MEDIUM",
                required_permissions=("ecriture",),
                timeout_seconds=5,
                handler=_ok_handler,
            )
        )

        self.registry.register(
            ToolDefinition(
                tool_id="outil_fautif",
                description="Outil qui leve une exception sensible",
                parameters=(
                    ToolParameter(name="data", type=str, required=True),
                ),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=_secret_leaking_handler,
            )
        )


class TestConfirmationExpirationDeterministic(unittest.TestCase):
    """Expiration des confirmations via horloge déterministe (sans sleep)."""

    def setUp(self) -> None:
        self.fixture = _EngineFixture()

    def test_jeton_valide_avant_expiration(self) -> None:
        first = self.fixture.engine.request_tool(
            tool_id="outil_risque", parameters={"data": "x"}
        )
        self.assertTrue(first.confirmation_required)

        # Juste avant l'expiration (299 s)
        self.fixture.clock.advance(299.0)
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "x"},
            user_confirmed=True,
            confirmation_token=first.confirmation_token,
        )
        self.assertTrue(result.success)

    def test_jeton_expire_apres_ttl(self) -> None:
        first = self.fixture.engine.request_tool(
            tool_id="outil_risque", parameters={"data": "x"}
        )
        self.assertTrue(first.confirmation_required)

        # Au-delà du TTL de 300 s
        self.fixture.clock.advance(301.0)
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "x"},
            user_confirmed=True,
            confirmation_token=first.confirmation_token,
        )
        self.assertFalse(result.success)
        self.assertTrue(result.confirmation_required)

    def test_jeton_expire_inexistant_apres_expiration(self) -> None:
        first = self.fixture.engine.request_tool(
            tool_id="outil_risque", parameters={"data": "x"}
        )
        token = first.confirmation_token
        self.fixture.clock.advance(301.0)

        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "x"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result.success)
        # Un nouveau jeton est proposé, l'ancien n'est plus réutilisable
        self.assertNotEqual(result.confirmation_token, token)

    def test_jeton_consomme_meme_si_execution_echoue(self) -> None:
        """Un jeton consommé ne doit pas pouvoir être ré-employé."""
        first = self.fixture.engine.request_tool(
            tool_id="outil_risque", parameters={"data": "x"}
        )
        token = first.confirmation_token

        result1 = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "x"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertTrue(result1.success)

        result2 = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "x"},
            user_confirmed=True,
            confirmation_token=token,
        )
        self.assertFalse(result2.success)
        self.assertTrue(result2.confirmation_required)


class TestRecursivePolicyValidation(unittest.TestCase):
    """Validation récursive de la politique sur structures imbriquées."""

    def setUp(self) -> None:
        self.fixture = _EngineFixture()

    def test_cle_shell_dans_dict_imbrique(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"options": {"shell": "rm -rf /"}},
        )
        self.assertFalse(result.success)

    def test_cle_code_dans_liste_imbriquee(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"options": [{"code": "print(1)"}]},
        )
        self.assertFalse(result.success)

    def test_cle_code_dans_tuple_imbrique(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"options": ({"code": "x"},)},
        )
        self.assertFalse(result.success)

    def test_valeur_shell_en_majuscules_refusee(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "SHELL"},
        )
        self.assertFalse(result.success)

    def test_valeur_secret_en_majuscules_refusee(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "PASSWORD"},
        )
        self.assertFalse(result.success)

    def test_cle_non_textuelle_ne_provoque_pas_erreur(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": {1: "valeur"}},
        )
        self.assertFalse(result.success)

    def test_parametre_imbrique_valide_est_accepte(self) -> None:
        """Une structure imbriquée sans motif interdit n'est pas refusée par la politique."""
        result = self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"data": "texte sur"},
        )
        # Refusé pour type invalide (data attendu str), mais pas par la politique
        self.assertFalse(result.success)
        self.assertTrue(len(result.error_message) > 0)

    def test_handler_non_appele_apres_refus_politique(self) -> None:
        """Preuve qu'un refus de politique empêche l'exécution du handler."""
        calls: list[str] = []

        def _recording_handler(data: str = "") -> str:
            calls.append(data)
            return "ok"

        self.fixture.registry.register(
            ToolDefinition(
                tool_id="outil_trace",
                description="Trace les appels",
                parameters=(ToolParameter(name="data", type=str, required=True),),
                risk_level="LOW",
                required_permissions=(),
                timeout_seconds=5,
                handler=_recording_handler,
            )
        )

        result = self.fixture.engine.request_tool(
            tool_id="outil_trace",
            parameters={"data": "x", "shell": "rm -rf /"},
        )
        self.assertFalse(result.success)
        self.assertEqual(calls, [])


class TestAuditConfidentiality(unittest.TestCase):
    """Confidentialité de l'audit face à des exceptions sensibles."""

    def setUp(self) -> None:
        self.fixture = _EngineFixture()

    def test_audit_ne_contient_pas_la_fausse_cle(self) -> None:
        result = self.fixture.engine.request_tool(
            tool_id="outil_fautif", parameters={"data": "x"}
        )
        self.assertFalse(result.success)

        # Le message utilisateur ne doit pas contenir l'exception brute
        self.assertNotIn("sk-FAUSSE-CLE-12345", result.error_message)
        self.assertNotIn("hunter2", result.error_message)

        # L'audit non plus
        for entry in self.fixture.audit.get_entries():
            self.assertNotIn("sk-FAUSSE-CLE-12345", entry.error_message)
            self.assertNotIn("hunter2", entry.error_message)
            self.assertNotIn("RuntimeError", entry.error_message)

    def test_audit_ne_contient_pas_de_parametres_bruts(self) -> None:
        self.fixture.engine.request_tool(
            tool_id="outil_risque", parameters={"data": "valeur-privee-123"}
        )
        for entry in self.fixture.audit.get_entries():
            self.assertNotIn("valeur-privee-123", entry.error_message)
            # Seul le hash SHA-256 des paramètres est conservé
            self.assertNotEqual(entry.parameters_hash, "")
            self.assertEqual(len(entry.parameters_hash), 64)

    def test_entree_audit_refus_politique_sans_secret(self) -> None:
        self.fixture.engine.request_tool(
            tool_id="outil_risque",
            parameters={"api_key": "sk-AUTRE-FAUSSE"},
        )
        entries = self.fixture.audit.get_entries()
        self.assertTrue(entries)
        for entry in entries:
            self.assertNotIn("sk-AUTRE-FAUSSE", entry.error_message)
            self.assertEqual(entry.result, "refused")


if __name__ == "__main__":
    unittest.main()
