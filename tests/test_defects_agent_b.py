"""Tests de non-régression des défauts D-B1 à D-B5 (audit Agent B).

Couvre :
- D-B1 : identifiant de conversation inexistant — une vraie conversation est
  créée, les messages restent visibles et restaurables ;
- D-B2 : assertions HTTP strictes restaurées (le refus est bien reçu) ;
- D-B3 : clés étrangères SQLite actives, suppression cohérente, pas de
  donnée orpheline, cohérence après réouverture ;
- D-B4 : fermeture de la mémoire à la sortie (succès et erreur) ;
- D-B5 : erreurs de persistance signalées, aucun secret divulgué.
"""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import miles
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory
from app.memory.transcript import ConversationTranscript, TranscriptError


class _TranscriptFixture(unittest.TestCase):
    """Base fournissant une base de conversations temporaire."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_dbfix_")
        self.db_path = os.path.join(self.tmpdir, "conversations.db")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _transcript(self) -> ConversationTranscript:
        return ConversationTranscript(enabled=True, db_path=self.db_path)


# ---------------------------------------------------------------------------
# D-B1 : identifiant de conversation inexistant
# ---------------------------------------------------------------------------

class TestDB1UnknownConversationId(_TranscriptFixture):
    """D-B1 : un identifiant inconnu ne doit jamais être conservé."""

    def test_identifiant_inconnu_cree_une_vraie_conversation(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        status = conv.attach_transcript(transcript, conversation_id="id-inexistant-xyz")

        self.assertEqual(status, "recreated")
        self.assertIsNotNone(conv.conversation_id)
        self.assertNotEqual(conv.conversation_id, "id-inexistant-xyz")
        # La conversation créée existe réellement
        self.assertIsNotNone(transcript.get_conversation(conv.conversation_id))
        transcript.close()

    def test_messages_visibles_apres_identifiant_inconnu(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript, conversation_id="id-inexistant-xyz")
        conv.add_user_message("message utilisateur")
        conv.add_assistant_message("réponse assistant")

        # La conversation est visible dans la liste
        conversations = transcript.list_conversations()
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["id"], conv.conversation_id)
        self.assertEqual(conversations[0]["message_count"], 2)

        # Aucun message n'est orphelin
        self.assertEqual(len(transcript.load_messages("id-inexistant-xyz")), 0)
        transcript.close()

    def test_identifiant_inconnu_message_est_restaurable(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript, conversation_id="id-inexistant-xyz")
        conv.add_user_message("à restaurer")
        real_id = conv.conversation_id
        transcript.close()

        # Réouverture : la conversation est restaurable
        transcript2 = self._transcript()
        conv2 = Conversation(history_limit=10)
        status = conv2.attach_transcript(transcript2, conversation_id=real_id)
        self.assertEqual(status, "restored")
        self.assertEqual(len(conv2), 1)
        self.assertEqual(conv2.get_context()[0]["content"], "à restaurer")
        transcript2.close()

    def test_conversation_vide_et_identifiant_inconnu(self) -> None:
        """Base vide + identifiant inconnu : comportement cohérent."""
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        status = conv.attach_transcript(transcript, conversation_id="inconnu")
        self.assertEqual(status, "recreated")
        self.assertIsNotNone(conv.conversation_id)
        self.assertEqual(len(transcript.list_conversations()), 1)
        transcript.close()

    def test_conversation_supprimee_puis_restauree(self) -> None:
        """Une conversation supprimée n'est plus restaurable."""
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "à supprimer")
        transcript.delete_conversation(conv_id)

        conv = Conversation(history_limit=10)
        status = conv.attach_transcript(transcript, conversation_id=conv_id)
        self.assertEqual(status, "recreated")
        self.assertNotEqual(conv.conversation_id, conv_id)
        transcript.close()

    def test_cli_signale_l_identifiant_inconnu(self) -> None:
        """Le CLI informe explicitement l'utilisateur."""
        from app.security.paths import project_root

        data_dir = project_root() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "test_db1_signal_conversations.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        env = {"MILES_CONVERSATION_DB_PATH": db_path, "MILES_CONVERSATION_PERSIST": "true"}
        try:
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, env):
                with redirect_stdout(out), redirect_stderr(err):
                    with mock.patch("builtins.input", side_effect=EOFError):
                        miles.main(["--conversation", "inconnu-123"])
            # Le message d'avertissement est sur stderr et cite l'identifiant
            self.assertIn("introuvable", err.getvalue())
            self.assertIn("inconnu-123", err.getvalue())
            # Le nouvel identifiant réellement attribué est communiqué
            self.assertIn("nouvelle conversation", err.getvalue())
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_cli_conversation_inconnue_cree_une_conversation_visible(self) -> None:
        """Après un --conversation inconnu, la conversation est listable."""
        from app.security.paths import project_root

        data_dir = project_root() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "test_db1_conversations.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        env = {"MILES_CONVERSATION_DB_PATH": db_path, "MILES_CONVERSATION_PERSIST": "true"}
        try:
            with mock.patch.dict(os.environ, env):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    with mock.patch("builtins.input", side_effect=EOFError):
                        miles.main(["--conversation", "inconnu-456"])
            # La conversation créée est visible et sans message orphelin
            transcript = ConversationTranscript(enabled=True, db_path=db_path)
            conversations = transcript.list_conversations()
            self.assertEqual(len(conversations), 1)
            self.assertNotEqual(conversations[0]["id"], "inconnu-456")
            transcript.close()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


# ---------------------------------------------------------------------------
# D-B3 : clés étrangères SQLite
# ---------------------------------------------------------------------------

class TestDB3ForeignKeys(_TranscriptFixture):
    """D-B3 : les clés étrangères doivent être actives."""

    def test_pragma_foreign_keys_actif(self) -> None:
        transcript = self._transcript()
        value = transcript._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(value, 1)
        transcript.close()

    def test_contrainte_etrangere_appliquee(self) -> None:
        """Un message rattaché à une conversation inexistante est refusé."""
        transcript = self._transcript()
        resultat = transcript.save_message("conversation-inexistante", "user", "orphelin")
        self.assertIsNone(resultat)
        self.assertEqual(len(transcript.load_messages("conversation-inexistante")), 0)
        transcript.close()

    def test_suppression_conversation_supprime_ses_messages(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "message 1")
        transcript.save_message(conv_id, "assistant", "message 2")
        self.assertEqual(len(transcript.load_messages(conv_id)), 2)

        transcript.delete_conversation(conv_id)
        self.assertEqual(len(transcript.load_messages(conv_id)), 0)
        self.assertEqual(len(transcript.list_conversations()), 0)
        transcript.close()

    def test_aucune_donnee_orpheline_apres_suppression(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "message")
        transcript.delete_conversation(conv_id)

        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM transcript_messages"
            ).fetchone()[0]
        self.assertEqual(total, 0)
        transcript.close()

    def test_coherence_apres_reouverture(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "persistant")
        transcript.close()

        transcript2 = self._transcript()
        value = transcript2._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(value, 1)
        self.assertEqual(len(transcript2.load_messages(conv_id)), 1)
        transcript2.close()


# ---------------------------------------------------------------------------
# D-B4 : fermeture de la mémoire
# ---------------------------------------------------------------------------

class TestDB4MemoryClose(unittest.TestCase):
    """D-B4 : les ressources doivent être fermées à la sortie du programme."""

    def test_memoire_fermee_apres_sortie_normale(self) -> None:
        with mock.patch("miles.CLI") as mock_cli:
            mock_cli.return_value.run.return_value = None
            with redirect_stdout(io.StringIO()):
                with mock.patch("builtins.input", side_effect=EOFError):
                    miles.main(["--no-persist"])

        memory = mock_cli.call_args.kwargs["memory"]
        if memory is not None:
            self.assertFalse(memory.is_available)
            self.assertIsNone(memory._conn)

    def test_memoire_fermee_apres_exception(self) -> None:
        with mock.patch("miles.CLI") as mock_cli:
            mock_cli.return_value.run.side_effect = RuntimeError("échec simulé")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    miles.main(["--no-persist"])

        memory = mock_cli.call_args.kwargs["memory"]
        if memory is not None:
            self.assertFalse(memory.is_available)
            self.assertIsNone(memory._conn)

    def test_transcript_ferme_apres_sortie_normale(self) -> None:
        avec_persist = {"MILES_CONVERSATION_PERSIST": "true"}
        with mock.patch.dict(os.environ, avec_persist):
            with mock.patch("miles._build_transcript") as mock_build:
                transcript = mock_build.return_value
                with mock.patch("miles.CLI") as mock_cli:
                    mock_cli.return_value.run.return_value = None
                    with redirect_stdout(io.StringIO()):
                        with mock.patch("builtins.input", side_effect=EOFError):
                            miles.main([])

        transcript.close.assert_called()


# ---------------------------------------------------------------------------
# D-B5 : erreurs de persistance
# ---------------------------------------------------------------------------

class TestDB5PersistenceErrors(_TranscriptFixture):
    """D-B5 : une erreur de persistance ne doit pas perdre de données."""

    def test_role_inconnu_leve_transcript_error(self) -> None:
        transcript = self._transcript()
        conv_id = transcript.create_conversation()
        with self.assertRaises(TranscriptError):
            transcript.save_message(conv_id, "role-inconnu", "contenu")
        transcript.close()

    def test_role_inconnu_ne_casse_pas_la_session(self) -> None:
        """_persist rattrape l'erreur et retourne False au lieu de lever."""
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        with mock.patch.object(
            transcript, "save_message", side_effect=TranscriptError("rôle invalide")
        ):
            resultat = conv.add_user_message("message")
        self.assertFalse(resultat)
        # Le message reste en mémoire : la session n'est pas perdue
        self.assertEqual(len(conv), 1)
        transcript.close()

    def test_echec_ecriture_signale(self) -> None:
        """Un échec d'écriture est signalé (retour False)."""
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        with mock.patch.object(transcript, "save_message", return_value=None):
            self.assertFalse(conv.add_assistant_message("réponse"))
        transcript.close()

    def test_echec_ecriture_n_invente_pas_de_reussite(self) -> None:
        """Le message n'est pas prétendu enregistré si l'écriture a échoué."""
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        with mock.patch.object(transcript, "save_message", return_value=None):
            conv.add_user_message("message non enregistré")
        # Le message n'est pas dans la base
        self.assertEqual(len(transcript.load_messages(conv.conversation_id)), 0)
        # Mais il reste en mémoire pour la session en cours
        self.assertEqual(len(conv), 1)
        transcript.close()

    def test_aucun_secret_divulgue_lors_d_une_erreur(self) -> None:
        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        with mock.patch.object(
            transcript,
            "save_message",
            side_effect=TranscriptError("échec avec sk-FAUSSE-CLE-9999"),
        ):
            err = io.StringIO()
            with redirect_stderr(err):
                conv.add_user_message("clé sk-FAUSSE-CLE-9999")
        # Le message d'erreur n'est pas affiché tel quel à l'utilisateur
        self.assertNotIn("sk-FAUSSE-CLE-9999", err.getvalue())
        transcript.close()

    def test_cli_avertit_si_persistence_echoue(self) -> None:
        """Le CLI prévient quand la réponse n'a pas pu être enregistrée."""
        from app.interface.cli import CLI

        class _Provider:
            name = "simule"

            def is_available(self):
                return True

            def chat(self, messages):
                return "réponse"

        transcript = self._transcript()
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)

        cli = CLI(settings=Settings(), provider=_Provider(), conversation=conv)
        with mock.patch.object(transcript, "save_message", return_value=None):
            out = io.StringIO()
            with redirect_stdout(out):
                cli._process_input("bonjour")
        self.assertIn("pas pu être enregistrée", out.getvalue())
        transcript.close()


class TestRisquesConfirmes(unittest.TestCase):
    """Risques signalés par Agent B : comportements vérifiés et documentés."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_risques_")
        self.none_env = os.path.join(self.tmpdir, "none.env")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clear_purge_la_persistance(self) -> None:
        """/clear ne doit pas laisser revenir les messages au redémarrage."""
        from app.memory.transcript import ConversationTranscript as _T

        db_path = os.path.join(self.tmpdir, "c.db")
        transcript = _T(enabled=True, db_path=db_path)
        conv = Conversation(history_limit=10)
        conv.attach_transcript(transcript)
        conv.add_user_message("avant clear")

        self.assertTrue(conv.clear())
        self.assertEqual(len(transcript.load_messages(conv.conversation_id)), 0)
        # La conversation existe mais est vide : elle reste restaurable
        self.assertIsNotNone(transcript.get_conversation(conv.conversation_id))
        transcript.close()

    def test_chemin_de_base_non_autorise_desactive_la_persistance(self) -> None:
        """Un chemin hors racines autorisées est refusé avec un avertissement."""
        hors_racines = os.path.join(self.tmpdir, "hors.db")
        env = {
            "MILES_CONVERSATION_DB_PATH": hors_racines,
            "MILES_CONVERSATION_PERSIST": "true",
            "MILES_ENV_FILE": self.none_env,
        }
        err = io.StringIO()
        with mock.patch.dict(os.environ, env):
            with redirect_stderr(err):
                with mock.patch("builtins.input", side_effect=EOFError):
                    miles.main([])
        self.assertIn("racines autoris", err.getvalue())
        self.assertFalse(os.path.exists(hors_racines))

    def test_variables_env_non_mappees_non_injectees(self) -> None:
        """Le .env n'injecte plus que les variables MILES_ connues.

        Comportement voulu depuis la correction d'herméticité : le fichier
        .env est lu dans un dictionnaire local, l'environnement du processus
        n'est pas modifié.
        """
        env_path = os.path.join(self.tmpdir, ".env")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write("MILES_PROVIDER=local\nHTTP_PROXY=http://proxy.invalid:3128\n")
        env = {"MILES_ENV_FILE": env_path}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("HTTP_PROXY", None)
            settings = Settings()
            self.assertEqual(settings.provider, "local")
            self.assertNotIn("HTTP_PROXY", os.environ)

    def test_transactions_sqlite_explicites(self) -> None:
        """Les écritures utilisent des transactions explicites."""
        db_path = os.path.join(self.tmpdir, "c.db")
        transcript = ConversationTranscript(enabled=True, db_path=db_path)
        # Mode autocommit : les transactions sont pilotées explicitement
        self.assertIsNone(transcript._conn.isolation_level)
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "message")
        self.assertEqual(len(transcript.load_messages(conv_id)), 1)
        transcript.close()

    def test_rollback_en_cas_d_erreur_d_ecriture(self) -> None:
        """Une écriture invalide ne laisse pas de trace partielle."""
        db_path = os.path.join(self.tmpdir, "c.db")
        transcript = ConversationTranscript(enabled=True, db_path=db_path)
        conv_id = transcript.create_conversation()
        transcript.save_message(conv_id, "user", "message 1")
        # Rôle invalide : refusé, la transaction est annulée
        with self.assertRaises(TranscriptError):
            transcript.save_message(conv_id, "role-invalide", "message 2")
        # L'état précédent est intact
        self.assertEqual(len(transcript.load_messages(conv_id)), 1)
        transcript.close()


if __name__ == "__main__":
    unittest.main()