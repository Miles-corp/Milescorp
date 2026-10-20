"""Interface terminal de MILES.

Boucle de saisie/affichage, gestion des commandes intégrées,
indication de chargement et traitement propre de Ctrl+C / fin de saisie.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.public_errors import public_provider_error, technical_detail
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.security.validator import ActionValidator, ActionResult

logger = logging.getLogger("miles.cli")
if not logger.handlers:
    # Handler neutre : l'application reste libre de configurer la
    # journalisation. N'écrit rien par défaut.
    logger.addHandler(logging.NullHandler())

HELP_TEXT = """\nCommandes disponibles :
  /help        Afficher cette aide
  /quit ou /q  Quitter le programme
  /clear       Effacer l'historique de la conversation
  /provider    Afficher le fournisseur IA courant
  /status      Afficher l'état du programme
  /remember    Enregistrer un souvenir explicite (usage: /remember <texte>)
  /memory      Lister les souvenirs persistants
  /forget      Supprimer un souvenir (usage: /forget <id>)
  /conversations Lister les conversations enregistrées
  /new         Démarrer une nouvelle conversation
Tapez votre message pour discuter avec l'assistant.
"""


class CLI:
    """Interface en ligne de commande pour MILES."""

    def __init__(
        self,
        settings: Any,
        provider: AIProvider | None = None,
        conversation: Conversation | None = None,
        validator: ActionValidator | None = None,
        memory: PersistentMemory | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        if conversation is None:
            conversation = Conversation(
                history_limit=settings.get("history_limit", 10)
            )
        self.conversation = conversation
        self.validator = validator or ActionValidator()
        self.memory = memory
        self._restored_message_count = 0
        self._running = True

    def run(self) -> None:
        """Lancer la boucle principale de l'interface terminal."""
        self._print_welcome()

        while self._running:
            try:
                user_input = self._read_input()
            except EOFError:
                # Fin de saisie (Ctrl+D) : message explicite, sortie propre.
                print("\nFin de saisie. Au revoir !")
                self._running = False
                break
            except KeyboardInterrupt:
                print("\nInterruption par l'utilisateur. Au revoir !")
                self._running = False
                break

            if not user_input or not user_input.strip():
                continue

            self._process_input(user_input.strip())

    def set_restored_message_count(self, count: int) -> None:
        """Indiquer le nombre de messages restaurés au démarrage."""
        self._restored_message_count = count

    def _print_welcome(self) -> None:
        provider_name = self.provider.name if self.provider else "non configuré"
        print("=" * 50)
        print(" MILES — Assistant personnel intelligent (prototype)")
        print("=" * 50)
        print(f"Fournisseur IA : {provider_name}")
        if self._restored_message_count:
            print(
                f"Conversation restaurée : {self._restored_message_count} message(s)."
            )
        if self.conversation.is_persistent:
            print(f"Conversation enregistrée sous l'identifiant {self.conversation.conversation_id}.")
        print("Tapez /help pour l'aide, /quit pour sortir.")
        print("=" * 50)

    def _read_input(self) -> str:
        try:
            return input("\n> ")
        except EOFError:
            raise
        except KeyboardInterrupt:
            raise

    def _process_input(self, text: str) -> None:
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Vérifier si le fournisseur est configuré
        if self.provider is None:
            print("Erreur : aucun fournisseur IA configuré.")
            print("Définissez MILES_PROVIDER=remote ou local et les paramètres associés.")
            return

        self.conversation.add_user_message(text)
        context = self.conversation.get_context()

        print("...", end="", flush=True)
        try:
            response = self.provider.chat(context)
        except AIProviderError as exc:
            # Message public : aucun détail technique ni secret affiché.
            # Le détail technique est conservé dans les journaux locaux,
            # expurgé de tout secret.
            logger.error(
                "Echec de l'appel au fournisseur IA : %s", technical_detail(exc)
            )
            print(f"\n{public_provider_error(exc)}")
            print("La conversation est conservée. Vous pouvez réessayer ou changer de fournisseur.")
            # Ne pas retirer le message utilisateur de l'historique : la session est préservée
            return
        except Exception as exc:  # noqa: BLE001 — ne pas faire planter l'interface
            logger.error("Erreur interne : %s", technical_detail(exc))
            print("\nErreur interne du service.")
            return

        print(f"\r{response}")
        if not self.conversation.add_assistant_message(response):
            print(
                "\nAvertissement : la réponse n'a pas pu être enregistrée "
                "dans l'historique persistant."
            )

    def _handle_command(self, text: str) -> None:
        cmd = text.lower().split()[0] if text.split() else ""
        args = text.split()[1:] if len(text.split()) > 1 else []

        if cmd in ("/quit", "/q", "/exit"):
            print("Au revoir !")
            self._running = False
        elif cmd == "/help":
            print(HELP_TEXT)
        elif cmd == "/clear":
            if self.conversation.clear():
                print("Historique effacé.")
            else:
                print(
                    "Historique effacé en mémoire, mais la suppression de "
                    "l'historique persisté a échoué."
                )
        elif cmd == "/provider":
            name = self.provider.name if self.provider else "non configuré"
            print(f"Fournisseur courant : {name}")
        elif cmd == "/status":
            provider_name = self.provider.name if self.provider else "non configuré"
            available = self.provider.is_available() if self.provider else False
            print(f"Fournisseur : {provider_name}")
            print(f"Disponible : {'oui' if available else 'non'}")
            print(f"Messages dans l'historique : {len(self.conversation)}")
            if self.conversation.is_persistent:
                print(f"Conversation persistée : {self.conversation.conversation_id}")
            else:
                print("Conversation persistée : non")
            if self.memory is not None:
                print(
                    f"Mémoire persistante : {'activée' if self.memory.is_available else 'désactivée/indisponible'}"
                )
        elif cmd == "/conversations":
            transcript = self.conversation.transcript
            if transcript is None or not transcript.is_available:
                print("Aucune conversation enregistrée (persistance désactivée).")
                return
            conversations = transcript.list_conversations(limit=20)
            if not conversations:
                print("Aucune conversation enregistrée.")
                return
            print("Conversations enregistrées :")
            for conv in conversations:
                marker = " (courante)" if conv["id"] == self.conversation.conversation_id else ""
                print(
                    f"  {conv['id']}  {conv['message_count']:>4} message(s){marker}"
                )
        elif cmd == "/new":
            if not self.conversation.is_persistent:
                print("Persistance désactivée : la conversation reste éphémère.")
                return
            new_id = self.conversation.new_conversation()
            if new_id:
                print(f"Nouvelle conversation : {new_id}")
            else:
                print("Impossible de créer une nouvelle conversation.")
        elif cmd == "/remember":
            if self.memory is None or not self.memory.is_available:
                print("Mémoire persistante indisponible ou désactivée.")
                return
            if not args:
                print("Usage : /remember <texte du souvenir>")
                return
            content = " ".join(args)
            try:
                mem_id = self.memory.add_memory(content)
                print(f"Souvenir enregistré (id {mem_id}).")
            except PersistentMemoryError as exc:
                print(f"Erreur : {exc}")
        elif cmd == "/memory":
            if self.memory is None or not self.memory.is_available:
                print("Mémoire persistante indisponible ou désactivée.")
                return
            memories = self.memory.list_memories()
            if not memories:
                print("Aucun souvenir enregistré.")
                return
            print("Souvenirs persistants :")
            for m in memories:
                print(f"  [{m['id']}] {m['content']} (catégorie: {m['category']}, importance: {m['importance']})")
        elif cmd == "/forget":
            if self.memory is None or not self.memory.is_available:
                print("Mémoire persistante indisponible ou désactivée.")
                return
            if not args:
                print("Usage : /forget <id du souvenir>")
                return
            try:
                memory_id = int(args[0])
            except ValueError:
                print("L'identifiant doit être un nombre.")
                return
            if self.memory.delete_memory(memory_id):
                print(f"Souvenir {memory_id} supprimé.")
            else:
                print(f"Aucun souvenir avec l'id {memory_id}.")
        else:
            print(f"Commande inconnue : {cmd}. Tapez /help pour l'aide.")

    def propose_action(self, action_name: str, arguments: dict[str, Any]) -> None:
        """Proposer une action, la valider et l'exécuter si autorisée."""
        result: ActionResult = self.validator.execute(action_name, arguments)
        if not result.allowed:
            print(f"[Action refusée] {action_name} : {result.reason}")
            return
        if result.error:
            print(f"[Erreur d'exécution] {action_name} : {result.error}")
            return
        print(f"[Action exécutée] {action_name}")
        if result.output is not None:
            print(result.output)
