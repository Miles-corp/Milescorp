"""Interface terminal de MILES.

Boucle de saisie/affichage, gestion des commandes intégrées,
indication de chargement et traitement propre de Ctrl+C / fin de saisie.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.public_errors import public_provider_error, technical_detail
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.orchestration.runner import MissionRunner
from app.security.validator import ActionValidator, ActionResult
from app.tools.grants import default_session_id
from app.tools.service import ToolService

logger = logging.getLogger("miles.cli")
if not logger.handlers:
    # Handler neutre : l'application reste libre de configurer la
    # journalisation. N'écrit rien par défaut.
    logger.addHandler(logging.NullHandler())

HELP_TEXT = """\nCommandes disponibles :
  /help        Afficher l'aide
  /quit ou /q  Quitter le programme
  /clear       Effacer l'historique de la conversation
  /provider    Afficher le fournisseur IA courant
  /status      Afficher l'état du programme
  /remember    Enregistrer un souvenir explicite (usage: /remember <texte>)
  /memory      Lister les souvenirs persistants
  /forget      Supprimer un souvenir (usage: /forget <id>)
  /conversations Lister les conversations enregistrées
  /new         Démarrer une nouvelle conversation
  /tools       Lister les outils disponibles
  /tool        Exécuter un outil (usage: /tool <id> [cle=valeur ...])
  /mission     Lancer une mission (usage: /mission <objectif>)
  /missions    Lister les missions
  /mission-status Consulter une mission (usage: /mission-status <id>)
  /mission-answer Répondre à une demande (usage: /mission-answer <id> <texte>)
  /mission-cancel Arrêter une mission (usage: /mission-cancel <id>)
  /mission-resume Reprendre une mission (usage: /mission-resume <id>)
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
        tool_service: ToolService | None = None,
        mission_runner: MissionRunner | None = None,
        session_id: str | None = None,
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
        self.tool_service = tool_service
        self.mission_runner = mission_runner
        # Identité de session : le jeton de confirmation d'un outil sensible
        # n'est valable que dans cette session (correctif du défaut relevé
        # par le rapport de la Phase 5).
        self.session_id = session_id or default_session_id("cli")
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
        elif cmd == "/tools":
            self._handle_tools_command()
        elif cmd == "/tool":
            self._handle_tool_command(args)
        elif cmd == "/mission":
            self._handle_mission_command(args)
        elif cmd == "/missions":
            self._handle_missions_command()
        elif cmd == "/mission-status":
            self._handle_mission_status_command(args)
        elif cmd == "/mission-answer":
            self._handle_mission_answer_command(args)
        elif cmd == "/mission-cancel":
            self._handle_mission_cancel_command(args)
        elif cmd == "/mission-resume":
            self._handle_mission_resume_command(args)
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

    # --- Outils ---

    def _handle_tools_command(self) -> None:
        """Lister les outils disponibles (catalogue, sans exécution)."""
        if self.tool_service is None:
            print("Aucun service d'outils disponible.")
            return
        catalogue = self.tool_service.list_tools()
        if not catalogue:
            print("Aucun outil enregistré.")
            return
        print("Outils disponibles :")
        for tool in catalogue:
            confirmation = (
                " (confirmation requise)"
                if tool["requires_confirmation"]
                else ""
            )
            print(f"  {tool['id']}  [risque {tool['risk_level']}]{confirmation}")
            print(f"      {tool['description']}")

    def _handle_tool_command(self, args: list[str]) -> None:
        """Exécuter un outil via le service partagé.

        La validation, les permissions, la confirmation et les délais sont
        entièrement gérés par le moteur : cette méthode ne fait qu'acheminer
        la demande et présenter le résultat.
        """
        if self.tool_service is None:
            print("Aucun service d'outils disponible.")
            return
        if not args:
            print("Usage : /tool <id> [cle=valeur ...]")
            return

        tool_id = args[0]
        parameters = self._parse_tool_parameters(args[1:])
        if parameters is None:
            return

        result = self.tool_service.request_tool(
            tool_id=tool_id,
            parameters=parameters,
            actor_id=self.session_id,
        )

        if result.confirmation_required:
            token = result.confirmation_token
            print(f"Confirmation humaine requise pour l'outil '{tool_id}'.")
            try:
                answer = input("Confirmer ? (o/N) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAction annulée.")
                return
            if answer not in ("o", "oui", "y", "yes"):
                print("Action annulée.")
                return
            result = self.tool_service.request_tool(
                tool_id=tool_id,
                parameters=parameters,
                user_confirmed=True,
                confirmation_token=token,
                actor_id=self.session_id,
            )

        if not result.success:
            print(f"[Outil refusé ou en échec] {tool_id} : {result.error_message}")
            return
        print(f"[Outil exécuté] {tool_id}")
        if result.data is not None:
            print(result.data)

    @staticmethod
    def _parse_tool_parameters(args: list[str]) -> Optional[dict[str, str]]:
        """Analyser les arguments `cle=valeur` d'une commande d'outil.

        Retourne None si un argument est mal formé (message affiché).
        """
        parameters: dict[str, str] = {}
        for arg in args:
            if "=" not in arg:
                print(f"Argument invalide : '{arg}'. Format attendu : cle=valeur")
                return None
            key, value = arg.split("=", 1)
            key = key.strip()
            if not key:
                print(f"Argument invalide : '{arg}'. La clé ne peut pas être vide.")
                return None
            parameters[key] = value
        return parameters

    # --- Missions ---

    def _handle_mission_command(self, args: list[str]) -> None:
        """Lancer une mission depuis un objectif en langage naturel."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        if not args:
            print("Usage : /mission <objectif>")
            return

        objective = " ".join(args)
        # Une mission identique déjà en cours n'est pas relancée : un double
        # appel ne doit pas produire deux exécutions.
        mission = self.mission_runner.find_running(objective)
        if mission is None:
            mission = self.mission_runner.create(
                objective, owner_session_id=self.session_id
            )
        mission = self.mission_runner.run(mission.mission_id)
        self._drive_mission(mission)

    def _mission_interaction_limit(self) -> int:
        """Plafond d'échanges utilisateur appliqué à une mission.

        La valeur provient de l'orchestrateur (et donc des réglages
        applicatifs) ; en son absence, la valeur historique (5) est
        employée.
        """
        runner = self.mission_runner
        limits = getattr(runner, "limits", None)
        value = getattr(limits, "max_interactions", None)
        if isinstance(value, int) and value > 0:
            return value
        return 5

    def _drive_mission(self, mission: Any) -> None:
        """Conduire une mission jusqu'à son terme ou jusqu'à un refus.

        Les demandes adressées à l'utilisateur (clarification, autorisation)
        sont posées dans le terminal. Le nombre d'échanges est borné : une
        boucle de questions ne peut pas bloquer le programme. La borne
        provient de l'orchestrateur (source unique de vérité) : c'est le
        MÊME plafond global que celui appliqué au web.
        """
        interactions = 0
        max_interactions = self._mission_interaction_limit()
        while (
            mission is not None
            and mission.pending is not None
            and interactions < max_interactions
        ):
            interactions += 1
            pending = mission.pending
            print()
            print(pending.question)
            try:
                answer = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nMission laissée en attente.")
                return
            if pending.kind == "authorization":
                approved = answer.lower() in ("o", "oui", "y", "yes", "ok")
                mission = self.mission_runner.authorize(
                    mission.mission_id,
                    approved=approved,
                    requester_session_id=self.session_id,
                    # Le jeton d'approbation lie la décision à CETTE
                    # demande précise (mission, périmètre, expiration).
                    approval_token=pending.approval_token,
                )
            else:
                mission = self.mission_runner.answer(
                    mission.mission_id, answer, requester_session_id=self.session_id
                )

        if mission is not None:
            print()
            print(mission.report)

    def _handle_missions_command(self) -> None:
        """Lister les missions connues."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        missions = self.mission_runner.list_missions(limit=20)
        if not missions:
            print("Aucune mission.")
            return
        print("Missions :")
        for mission in missions:
            print(
                f"  {mission['mission_id']}  {mission['state']:<22}  "
                f"{mission['objective']}"
            )

    def _handle_mission_status_command(self, args: list[str]) -> None:
        """Afficher l'état détaillé d'une mission."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        if not args:
            print("Usage : /mission-status <id>")
            return
        mission = self.mission_runner.get(args[0])
        if mission is None:
            print(f"Mission inconnue : {args[0]}")
            return
        print(f"Mission {mission.mission_id} — état : {mission.state.value}")
        print(f"Objectif : {mission.objective}")
        if mission.pending is not None:
            print(f"Demande en attente ({mission.pending.kind}) : {mission.pending.question}")
        if mission.plan is not None:
            print("Plan :")
            for step in mission.plan.steps:
                print(f"  {step.step_id} [{step.tool_id}] {step.status.value} : {step.objective}")
        if mission.facts:
            print("Faits observés :")
            for fact in mission.facts:
                print(f"  - {fact}")
        if mission.errors:
            print("Erreurs :")
            for error in mission.errors:
                print(f"  - {error}")
        if mission.unfinished:
            print("Étapes non terminées :")
            for item in mission.unfinished:
                print(f"  - {item}")

    def _handle_mission_answer_command(self, args: list[str]) -> None:
        """Répondre à une demande en attente (clarification ou autorisation)."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        if len(args) < 2:
            print("Usage : /mission-answer <id> <texte>")
            return
        mission = self.mission_runner.get(args[0])
        if mission is None:
            print(f"Mission inconnue : {args[0]}")
            return
        if mission.pending is None:
            print("Cette mission n'a aucune demande en attente.")
            return
        mission = self.mission_runner.answer(args[0], " ".join(args[1:]))
        self._drive_mission(mission)

    def _handle_mission_cancel_command(self, args: list[str]) -> None:
        """Demander l'arrêt d'une mission."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        if not args:
            print("Usage : /mission-cancel <id>")
            return
        if self.mission_runner.cancel(args[0]):
            print(f"Mission {args[0]} arrêtée.")
        else:
            print(f"Mission {args[0]} introuvable ou déjà terminée.")

    def _handle_mission_resume_command(self, args: list[str]) -> None:
        """Reprendre une mission interrompue."""
        if self.mission_runner is None:
            print("Orchestrateur de missions indisponible.")
            return
        if not args:
            print("Usage : /mission-resume <id>")
            return
        mission = self.mission_runner.resume(args[0])
        if mission is None:
            print(f"Mission inconnue : {args[0]}")
            return
        self._drive_mission(mission)

    def propose_action(self, action_name: str, arguments: dict[str, Any]) -> None:
        """Proposer une action, la valider et l'exécuter si autorisée.

        Note : chemin historique conservé pour compatibilité. Les nouveaux
        usages passent par le service d'outils (commande /tool).
        """
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
