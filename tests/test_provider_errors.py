"""Tests de non-divulgation des erreurs fournisseur (R6).

Vérifient que :
- le message affiché à l'utilisateur ne contient ni clé API, ni corps de
  réponse du fournisseur, ni détail technique ;
- le diagnostic technique reste disponible dans les journaux locaux, mais
  expurgé de tout secret ;
- le code de sortie et la conservation de la session ne changent pas.
"""

from __future__ import annotations

import io
import logging
import unittest
from contextlib import redirect_stdout
from unittest import mock

from app.ai_providers.base import AIProviderError
from app.ai_providers.public_errors import public_provider_error, technical_detail
from app.config.settings import Settings
from app.interface.cli import CLI
from app.interface.web import public_provider_error as web_public_error


class _FailingProvider:
    """Fournisseur qui lève une exception contenant un faux secret."""

    name = "fournisseur-de-test"

    def __init__(self, message: str) -> None:
        self._message = message

    def is_available(self):
        return True

    def chat(self, messages):
        raise AIProviderError(self._message)


class TestPublicProviderError(unittest.TestCase):
    """R6 : classification des erreurs fournisseur."""

    def test_erreur_authentification(self) -> None:
        message = public_provider_error(
            AIProviderError("Erreur HTTP 401 du fournisseur distant : clé refusée")
        )
        self.assertIn("authentification", message.lower())
        self.assertNotIn("401", message)

    def test_erreur_quota(self) -> None:
        message = public_provider_error(
            AIProviderError("Erreur HTTP 429 : rate limit atteint")
        )
        self.assertIn("quota", message.lower())
        self.assertNotIn("429", message)

    def test_erreur_ressource_introuvable(self) -> None:
        message = public_provider_error(
            AIProviderError("Erreur HTTP 404 : modèle introuvable")
        )
        self.assertIn("introuvable", message.lower())
        self.assertNotIn("404", message)

    def test_erreur_delai(self) -> None:
        message = public_provider_error(
            AIProviderError("Délai d'attente dépassé (30s)")
        )
        self.assertIn("délai", message.lower())

    def test_erreur_reponse_invalide(self) -> None:
        message = public_provider_error(
            AIProviderError("Réponse invalide (non-JSON) du fournisseur distant")
        )
        self.assertIn("invalide", message.lower())

    def test_erreur_fournisseur_indisponible(self) -> None:
        message = public_provider_error(
            AIProviderError("Impossible de joindre le fournisseur distant")
        )
        self.assertIn("indisponible", message.lower())

    def test_erreur_generique(self) -> None:
        message = public_provider_error(AIProviderError("bruit quelconque"))
        self.assertIn("fournisseur", message.lower())

    def test_web_et_cli_exposent_le_meme_message(self) -> None:
        exc = AIProviderError("Erreur HTTP 401 : refus")
        self.assertEqual(public_provider_error(exc), web_public_error(exc))

    def test_aucun_secret_dans_le_message_public(self) -> None:
        exc = AIProviderError(
            "Erreur HTTP 401 : clé sk-FAUSSE-CLE-9999 et password=pwd-faux-1234"
        )
        message = public_provider_error(exc)
        self.assertNotIn("sk-FAUSSE-CLE-9999", message)
        self.assertNotIn("pwd-faux-1234", message)
        self.assertNotIn("401", message)


class TestTechnicalDetail(unittest.TestCase):
    """R6 : le diagnostic technique local est conservé mais expurgé."""

    def test_detail_technique_conserve_le_diagnostic(self) -> None:
        detail = technical_detail(
            AIProviderError("Erreur HTTP 500 du fournisseur distant")
        )
        self.assertIn("AIProviderError", detail)
        self.assertIn("500", detail)

    def test_detail_technique_expurge_les_secrets(self) -> None:
        detail = technical_detail(
            AIProviderError("échec avec sk-FAUSSE-CLE-9999 et password=pwd-faux-1234")
        )
        self.assertNotIn("sk-FAUSSE-CLE-9999", detail)
        self.assertNotIn("pwd-faux-1234", detail)
        self.assertIn("[REDACTED]", detail)


class TestCliProviderErrorDisplay(unittest.TestCase):
    """R6 : le terminal n'affiche plus de détail technique."""

    def _run(self, message: str) -> tuple[str, str]:
        from app.core.conversation import Conversation

        cli = CLI(
            settings=Settings(),
            provider=_FailingProvider(message),
            conversation=Conversation(history_limit=10),
        )
        out = io.StringIO()
        with redirect_stdout(out):
            cli._process_input("bonjour")
        return out.getvalue(), cli.conversation.get_context()

    def test_terminal_n_affiche_pas_le_detail_technique(self) -> None:
        sortie, _ = self._run(
            "Erreur HTTP 401 du fournisseur distant : sk-FAUSSE-CLE-9999"
        )
        self.assertNotIn("sk-FAUSSE-CLE-9999", sortie)
        self.assertNotIn("401", sortie)
        self.assertIn("Erreur du fournisseur IA", sortie)

    def test_session_preservee_apres_erreur_fournisseur(self) -> None:
        _, contexte = self._run("Erreur HTTP 500")
        self.assertEqual(len(contexte), 1)
        self.assertEqual(contexte[0]["role"], "user")
        self.assertEqual(contexte[0]["content"], "bonjour")

    def test_erreur_interne_ne_divulgue_pas_le_detail(self) -> None:
        from app.core.conversation import Conversation

        class _Boom:
            name = "boom"

            def is_available(self):
                return True

            def chat(self, messages):
                raise RuntimeError("défaillance interne sk-FAUSSE-CLE-9999")

        cli = CLI(
            settings=Settings(),
            provider=_Boom(),
            conversation=Conversation(history_limit=10),
        )
        out = io.StringIO()
        with redirect_stdout(out):
            cli._process_input("bonjour")
        self.assertNotIn("sk-FAUSSE-CLE-9999", out.getvalue())
        self.assertIn("Erreur interne du service", out.getvalue())

    def test_erreur_fournisseur_journalisee_sans_secret(self) -> None:
        from app.core.conversation import Conversation

        flux = io.StringIO()
        handler = logging.StreamHandler(flux)
        logger = logging.getLogger("miles.cli")
        anciens = list(logger.handlers)
        logger.handlers = [handler]
        try:
            cli = CLI(
                settings=Settings(),
                provider=_FailingProvider("échec sk-FAUSSE-CLE-9999"),
                conversation=Conversation(history_limit=10),
            )
            with redirect_stdout(io.StringIO()):
                cli._process_input("bonjour")
        finally:
            logger.handlers = anciens
        journal = flux.getvalue()
        self.assertNotIn("sk-FAUSSE-CLE-9999", journal)
        self.assertIn("[REDACTED]", journal)


if __name__ == "__main__":
    unittest.main()
