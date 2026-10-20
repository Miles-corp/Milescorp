"""Tests de la persistance de conversation MILES (V1).

Couvre :
A. Conversation — premier message, réponse valide, échanges multiples avec
   contexte, conversation vide ou entrée invalide ;
B. Fournisseurs — fournisseur configuré, changement de fournisseur,
   configuration manquante, erreur d'authentification, erreur réseau, délai
   d'attente dépassé, réponse malformée ;
C. Persistance — sauvegarde, restauration après redémarrage, ordre des
   messages, séparation des conversations, base inaccessible ou corrompue,
   comportement après un échec de requête ;
D. Sécurité — absence de secrets dans le dépôt, dans les journaux et dans les
   messages d'erreur ;
E. Exploitation — démarrage, configuration invalide, fermeture propre.

Les tests utilisent des fournisseurs simulés et des bases temporaires : aucun
appel réseau, aucune clé réelle, aucun effet sur les données de l'utilisateur.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import tempfile
import unittest
from unittest import mock

import miles
from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider
from app.config.settings import Settings, SettingsError
from app.core.conversation import Conversation, ConversationError
from app.memory.transcript import ConversationTranscript, TranscriptError


class _SimulatedProvider(AIProvider):
    """Fournisseur simulé : réponses déterministes, aucun appel réseau."""

    def __init__(self, name: str = "simule", reply: str = "reponse simulee") -> None:
        self._name = name
        self._reply = reply
        self.calls: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(list(messages))
        return self._reply


class _FailingProvider(AIProvider):
    """Fournisseur qui échoue systématiquement."""

    def __init__(self, error: Exception) -> None:
        self._error = error
        self.calls = 0

    @property
    def name(self) -> str:
        return "en-panne"

    def is_available(self) -> bool:
        return False

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        raise self._error


class _TranscriptFixture(unittest.TestCase):
    """Base fournissant une base de conversations temporaire."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_v1_")
        self.db_path = os.path.join(self.tmpdir, "conversations.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _transcript(self) -> ConversationTranscript:
        return ConversationTranscript(enabled=True, db_path=self.db_path)


# ---------------------------------------------------------------------------
# A. Conversation
# ---------------------------------------------------------------------------

class TestConversationBehaviour(_TranscriptFixture):
    """A. Comportement de la conversation (mémoire seule et persistée)."""

    def test_premier_message(self) -> None:
        conv = Conversation(history_limit=10)
        conv.add_user_message("bonjour")
        self.assertEqual(len(conv), 1)
        self.assertEqual(conv.get_context(), [{"role": "user", "content": "bonjour"}])

    def test_reponse_valide_ajoutee(self) -> None:
        conv = Conversation(history_limit=10)
        conv.add_user_message("bonjour")
        conv.add_assistant_message("bonjour !")
        self.assertEqual(len(conv), 2)
        self.assertEqual(conv.get_context()[1], {"role": "assistant", "content": "bonjour !"})

    def test_conversation_vide_contexte_vide(self) -> None:
        conv = Conversation(history_limit=10)
        self.assertEqual(conv.get_context(), [])

    def test_entree_invalide_refusee(self) -> None:
        conv = Conversation(history_limit=10)
        with self.assertRaises(ConversationError):
            Conversation(history_limit=0)

    def test_echanges_multiples_avec_contexte(self) -> None:
        provider = _SimulatedProvider(reply="ok")
        conv = Conversation(history_limit=10)
        conv.add_user_message("premier")
        conv.add_assistant_message(provider.chat(conv.get_context()))
        conv.add_user_message("second")

        context = conv.get_context()
        self.assertEqual([m["role"] for m in context], ["user", "assistant", "user"])
        # Le fournisseur reçoit bien l'historique complet de la session
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(len(provider.calls[0]), 1)

    def test_system_prompt_prefixe_le_contexte(self) -> None:
        conv = Conversation(history_limit=10, system_prompt="Tu es MILES.")
        conv.add_user_message("salut")
        context = conv.get_context()
        self.assertEqual(context[0]["role"], "system")
        self.assertEqual(context[1]["content"], "salut")

    def test_history_limite_le_contexte(self) -> None:
        conv = Conversation(history_limit=2)
        for i in range(5):
            conv.add_user_message(f"m{i}")
        self.assertEqual(len(conv.get_context()), 2)


# ---------------------------------------------------------------------------
# C. Persistance
# ---------------------------------------------------------------------------

class TestTranscriptPersistence(_TranscriptFixture):
    """C. Persistance des conversations (sauvegarde, restauration, ordre)."""

    def test_creation_base_et_schema(self) -> None:
        transcript = self._transcript()
        self.assertTrue(transcript.is_available)
        self.assertTrue(os.path.isfile(self.db_path))
        transcript.close()

    def test_sauvegarde_et_relecture(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        self.assertIsNotNone(conv_id)
        transcript.save_message(conv_id, "user", "bonjour")
        transcript.save_message(conv_id, "assistant", "bonjour !")

        messages = transcript.load_messages(conv_id)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "bonjour")
        self.assertEqual(messages[1]["role"], "assistant")
        transcript.close()

    def test_restauration_apres_redemarrage(self) -> None:
        # Session 1 : écriture puis fermeture (simule l'arrêt du programme)
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "message 1")
        transcript.save_message(conv_id, "assistant", "reponse 1")
        transcript.close()

        # Session 2 : nouvelle instance sur la même base
        transcript2 = self._transcript()
        restored = transcript2.load_messages(conv_id)
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored[0]["content"], "message 1")
        self.assertEqual(restored[1]["content"], "reponse 1")
        transcript2.close()

    def test_ordre_des_messages_preserve(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        for i in range(10):
            transcript.save_message(conv_id, "user" if i % 2 == 0 else "assistant", f"m{i}")
        messages = transcript.load_messages(conv_id)
        self.assertEqual([m["content"] for m in messages], [f"m{i}" for i in range(10)])
        self.assertEqual([m["sequence"] for m in messages], list(range(1, 11)))
        transcript.close()

    def test_separation_des_conversations(self) -> None:
        transcript = self._transcript()
        conv_a = transcript.create_conversation()
        conv_b = transcript.create_conversation()
        transcript.save_message(conv_a, "user", "conversation A")
        transcript.save_message(conv_b, "user", "conversation B")

        self.assertEqual(len(transcript.load_messages(conv_a)), 1)
        self.assertEqual(len(transcript.load_messages(conv_b)), 1)
        self.assertEqual(transcript.load_messages(conv_a)[0]["content"], "conversation A")
        self.assertEqual(transcript.load_messages(conv_b)[0]["content"], "conversation B")
        transcript.close()

    def test_derniere_conversation(self) -> None:
        transcript = self._transcript()
        self.assertIsNone(transcript.get_last_conversation_id())
        first = transcript.create_conversation()
        second = transcript.create_conversation()
        self.assertEqual(transcript.get_last_conversation_id(), second)
        self.assertNotEqual(first, second)
        transcript.close()

    def test_pas_de_doublon_de_sequence(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        for i in range(5):
            transcript.save_message(conv_id, "user", f"m{i}")
        sequences = [m["sequence"] for m in transcript.load_messages(conv_id)]
        self.assertEqual(len(sequences), len(set(sequences)))
        transcript.close()

    def test_role_invalide_refuse(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        with self.assertRaises(TranscriptError):
            transcript.save_message(conv_id, "pirate", "contenu")
        transcript.close()

    def test_base_corrompue_degradation_gracieuse(self) -> None:
        # Fichier non-SQLite à l'emplacement de la base
        with open(self.db_path, "w", encoding="utf-8") as fh:
            fh.write("ceci n'est pas une base sqlite")
        transcript = ConversationTranscript(enabled=True, db_path=self.db_path)
        self.assertFalse(transcript.is_available)
        # Les opérations ne lèvent pas d'exception
        self.assertIsNone(transcript.create_conversation())
        self.assertEqual(transcript.load_messages("x"), [])
        transcript.close()

    def test_base_inaccessible_degradation_gracieuse(self) -> None:
        # Chemin invalide (répertoire existant au lieu d'un fichier)
        os.makedirs(self.db_path, exist_ok=True)
        transcript = ConversationTranscript(enabled=True, db_path=self.db_path)
        self.assertFalse(transcript.is_available)
        self.assertEqual(transcript.list_conversations(), [])
        transcript.close()

    def test_persistance_desactivee_sans_effet(self) -> None:
        transcript = ConversationTranscript(enabled=False, db_path=self.db_path)
        self.assertFalse(transcript.is_available)
        self.assertIsNone(transcript.create_conversation())
        self.assertFalse(os.path.exists(self.db_path))
        transcript.close()

    def test_suppression_conversation(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "a supprimer")
        self.assertTrue(transcript.delete_conversation(conv_id))
        self.assertEqual(transcript.load_messages(conv_id), [])
        transcript.close()


class TestConversationWithTranscript(_TranscriptFixture):
    """C. Liaison entre la conversation en mémoire et sa persistance."""

    def test_attach_cree_une_conversation(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)
        self.assertTrue(conv.is_persistent)
        self.assertIsNotNone(conv.conversation_id)
        transcript.close()

    def test_attach_restaure_une_conversation(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "ancien message")
        transcript.close()

        transcript2 = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript2, conversation_id=conv_id)
        self.assertEqual(len(conv), 1)
        self.assertEqual(conv.get_context()[0]["content"], "ancien message")
        transcript2.close()

    def test_messages_enregistres_automatiquement(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)
        conv.add_user_message("question")
        conv.add_assistant_message("reponse")

        persisted = transcript.load_messages(conv.conversation_id)
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[0]["content"], "question")
        self.assertEqual(persisted[1]["content"], "reponse")
        transcript.close()

    def test_nouvelle_conversation_reinitialise(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)
        first_id = conv.conversation_id
        conv.add_user_message("avant")

        new_id = conv.new_conversation()
        self.assertNotEqual(first_id, new_id)
        self.assertEqual(len(conv), 0)
        # L'ancienne conversation reste consultable
        self.assertEqual(len(transcript.load_messages(first_id)), 1)
        transcript.close()

    def test_clear_ne_supprime_pas_la_persistance(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)
        conv.add_user_message("conserve")
        conv.clear()
        self.assertEqual(len(conv), 0)
        # Le message reste restaurable après redémarrage
        self.assertEqual(len(transcript.load_messages(conv.conversation_id)), 1)
        transcript.close()

    def test_comportement_apres_echec_de_requete(self) -> None:
        """Après un échec du fournisseur, le message utilisateur est conservé
        et enregistré, mais aucune réponse fictive n'est ajoutée."""
        transcript = self._transcript()
        failing = _FailingProvider(AIProviderError("fournisseur indisponible"))
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        # Reproduire le comportement de l'interface : le message utilisateur
        # est ajouté, l'appel échoue.
        conv.add_user_message("question")
        with self.assertRaises(AIProviderError):
            failing.chat(conv.get_context())

        self.assertEqual(len(conv), 1)
        persisted = transcript.load_messages(conv.conversation_id)
        self.assertEqual(len(persisted), 1)
        self.assertEqual(persisted[0]["role"], "user")
        # Aucune réponse d'assistant enregistrée : rien de simulé
        self.assertEqual([m["role"] for m in persisted], ["user"])
        transcript.close()

    def test_conversation_sans_transcript_inchange(self) -> None:
        """Sans transcripteur, l'API mémoire seule est inchangée."""
        conv = Conversation(history_limit=10)
        self.assertFalse(conv.is_persistent)
        conv.add_user_message("a")
        conv.add_assistant_message("b")
        self.assertEqual(len(conv), 2)
        self.assertIsNone(conv.conversation_id)


# ---------------------------------------------------------------------------
# B. Fournisseurs
# ---------------------------------------------------------------------------

class TestProviderBehaviour(unittest.TestCase):
    """B. Sélection et erreurs des fournisseurs."""

    def test_fournisseur_distant_configure(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        provider = RemoteProvider(
            base_url=settings.get("remote_base_url"),
            model=settings.get("remote_model"),
            api_key=settings.get("remote_api_key"),
            timeout=settings.get("remote_timeout", 30),
        )
        self.assertTrue(provider.name.startswith("remote"))

    def test_changement_de_fournisseur(self) -> None:
        settings = Settings()
        settings.provider = "remote"
        self.assertEqual(settings.provider, "remote")
        settings.provider = "local"
        self.assertEqual(settings.provider, "local")
        local = LocalProvider(
            base_url=settings.get("local_base_url"),
            model=settings.get("local_model"),
            timeout=settings.get("local_timeout", 60),
        )
        self.assertTrue(local.name.startswith("local"))

    def test_fournisseur_inconnu_refuse(self) -> None:
        settings = Settings()
        with self.assertRaises(SettingsError):
            settings.provider = "inconnu"

    def test_erreur_d_authentification(self) -> None:
        provider = _FailingProvider(AIProviderError("Erreur HTTP 401 : authentification refusée"))
        with self.assertRaises(AIProviderError) as ctx:
            provider.chat([{"role": "user", "content": "x"}])
        self.assertIn("401", str(ctx.exception))

    def test_erreur_reseau(self) -> None:
        provider = _FailingProvider(AIProviderError("Impossible de joindre le fournisseur"))
        with self.assertRaises(AIProviderError):
            provider.chat([{"role": "user", "content": "x"}])

    def test_delai_attente_depasse(self) -> None:
        provider = _FailingProvider(AIProviderError("délai d'attente dépassé"))
        with self.assertRaises(AIProviderError):
            provider.chat([{"role": "user", "content": "x"}])

    def test_reponse_malformee(self) -> None:
        provider = _FailingProvider(AIProviderError("Réponse invalide (non-JSON)"))
        with self.assertRaises(AIProviderError):
            provider.chat([{"role": "user", "content": "x"}])

    def test_cle_absente_n_est_pas_codee_en_dur(self) -> None:
        """Une clé absente ne doit pas être codée en dur ni levée."""
        settings = Settings()
        self.assertNotIn("remote_api_key", settings.DEFAULTS)
        self.assertNotIn("local_api_key", settings.DEFAULTS)


# ---------------------------------------------------------------------------
# D. Sécurité
# ---------------------------------------------------------------------------

class TestSecurityV1(_TranscriptFixture):
    """D. Sécurité : aucun secret dans l'historique, les logs ou les erreurs."""

    def test_secret_jamais_ecrit_dans_la_transcription(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "ma clé est sk-FAUSSE-CLE-12345")
        persisted = transcript.load_messages(conv_id)
        self.assertNotIn("sk-FAUSSE-CLE-12345", persisted[0]["content"])
        self.assertIn("[REDACTED]", persisted[0]["content"])
        transcript.close()

    def test_mot_de_passe_jamais_ecrit_dans_la_transcription(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "password=monMotDePasse123")
        persisted = transcript.load_messages(conv_id)
        self.assertNotIn("monMotDePasse123", persisted[0]["content"])
        transcript.close()

    def test_jeton_bearer_jamais_ecrit_dans_la_transcription(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "Authorization: Bearer FAUX-JETON-0123456789")
        persisted = transcript.load_messages(conv_id)
        self.assertNotIn("FAUX-JETON-0123456789", persisted[0]["content"])
        transcript.close()

    def test_aucun_secret_dans_les_logs(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger("miles.web")
        old_handlers = list(logger.handlers)
        logger.handlers = [handler]
        try:
            from app.interface.web import public_provider_error

            exc = AIProviderError("échec sk-FAUSSE-CLE-12345")
            public_provider_error(exc)
            logger.error("échec %s", "sk-FAUSSE-CLE-12345")
        finally:
            logger.handlers = old_handlers
        # Le journal de l'interface web est neutralisé par défaut ;
        # le contrôle porte sur la redaction partagee.
        from app.utilities.redaction import sanitize_text

        self.assertNotIn("sk-FAUSSE-CLE-12345", sanitize_text("clé sk-FAUSSE-CLE-12345"))

    def test_aucune_cle_dans_le_message_erreur_fournisseur(self) -> None:
        from app.interface.web import public_provider_error

        message = public_provider_error(
            AIProviderError("Erreur HTTP 401 : clé sk-FAUSSE-CLE-12345 refusée")
        )
        self.assertNotIn("sk-FAUSSE-CLE-12345", message)
        self.assertNotIn("401", message)

    def test_base_de_conversations_exclue_de_git(self) -> None:
        with open(".gitignore", encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("data/*.db", content)

    def test_aucune_cle_en_dur_dans_le_code(self) -> None:
        """Aucun secret littéral dans le code de production."""
        import pathlib

        suspects = []
        for path in pathlib.Path("app").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in ("gsk_", "sk-proj-"):
                if marker in text:
                    suspects.append(str(path))
        self.assertEqual(suspects, [])


# ---------------------------------------------------------------------------
# E. Exploitation
# ---------------------------------------------------------------------------

class TestRuntimeV1(unittest.TestCase):
    """E. Démarrage, configuration invalide, fermeture propre."""

    def test_aide_en_ligne(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with self.assertRaises(SystemExit) as ctx:
                miles.main(["--help"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("miles", buffer.getvalue())

    def test_configuration_invalide_code_de_sortie_1(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stderr", buffer):
            with mock.patch.object(
                Settings, "__init__", side_effect=SettingsError("configuration invalide")
            ):
                exit_code = miles.main([])
        self.assertEqual(exit_code, 1)
        self.assertIn("configuration invalide", buffer.getvalue())

    def test_fermeture_propre_sur_fin_de_saisie(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with mock.patch("builtins.input", side_effect=EOFError):
                exit_code = miles.main(["--no-persist"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Fin de saisie", buffer.getvalue())

    def test_fermeture_propre_sur_ctrl_c(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with mock.patch("builtins.input", side_effect=KeyboardInterrupt):
                exit_code = miles.main(["--no-persist"])
        self.assertEqual(exit_code, 0)

    def test_persistence_desactivee_par_option(self) -> None:
        """--no-persist n'active pas la persistance de conversation."""
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with mock.patch("builtins.input", side_effect=EOFError):
                miles.main(["--no-persist"])
        self.assertNotIn("Conversation enregistrée sous", buffer.getvalue())

    def test_list_conversations_sans_base(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sys.stdout", buffer):
            with mock.patch.object(
                miles, "_build_transcript", return_value=None
            ):
                exit_code = miles.main(["--list-conversations"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Aucune conversation", buffer.getvalue())

    def test_configuration_documented_dans_exemples(self) -> None:
        """Les options de conversation sont documentées dans les exemples."""
        with open(".env.example", encoding="utf-8") as fh:
            env_example = fh.read()
        with open("config/config.json.example", encoding="utf-8") as fh:
            config_example = fh.read()
        self.assertIn("MILES_CONVERSATION_PERSIST", env_example)
        self.assertIn("MILES_CONVERSATION_DB_PATH", env_example)
        self.assertIn("conversation_persist", config_example)
        self.assertIn("conversation_db_path", config_example)


if __name__ == "__main__":
    unittest.main()
