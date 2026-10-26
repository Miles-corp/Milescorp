#!/usr/bin/env python3
"""MILES — Assistant personnel intelligent. Point d'entrée du programme."""

import sys
import argparse

from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.interface.cli import CLI
from app.interface.web import MilesWebServer, WebApp
from app.interface.web_auth import (
    WebAuthenticator,
    WebCredentialStore,
    generate_access_token,
)
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.memory.transcript import ConversationTranscript
from app.orchestration.models import ExecutionLimits
from app.orchestration.runner import MissionRunner
from app.orchestration.store import MissionStore
from app.security.paths import PathSecurityError, resolve_authorized_path
from app.tools.grants import GrantRegistry, default_session_id
from app.tools.service import ToolService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miles",
        description="MILES — Assistant personnel intelligent (prototype)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Chemin vers le fichier de configuration JSON (par défaut: config/config.json ou variables d'environnement)",
    )
    parser.add_argument(
        "--provider",
        choices=["remote", "local"],
        default=None,
        help="Fournisseur IA à utiliser (remplace la configuration)",
    )
    parser.add_argument(
        "--conversation",
        default=None,
        metavar="ID",
        help="Restaurer une conversation précise (identifiant affiché par --list-conversations)",
    )
    parser.add_argument(
        "--new-conversation",
        action="store_true",
        help="Démarrer une nouvelle conversation au lieu de restaurer la dernière",
    )
    parser.add_argument(
        "--list-conversations",
        action="store_true",
        help="Lister les conversations enregistrées puis quitter",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Ne pas enregistrer la conversation sur disque (mode éphémère)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Démarrer l'interface web locale (au lieu du terminal)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Port d'écoute de l'interface web (défaut: 8080)",
    )
    return parser


def _build_provider(settings: Settings):
    """Instancier le fournisseur IA configuré, ou None si inconnu."""
    if settings.provider == "remote":
        return RemoteProvider(
            base_url=settings.get("remote_base_url"),
            model=settings.get("remote_model"),
            api_key=settings.get("remote_api_key"),
            timeout=settings.get("remote_timeout", 30),
        )
    if settings.provider == "local":
        return LocalProvider(
            base_url=settings.get("local_base_url"),
            model=settings.get("local_model"),
            api_key=settings.get("local_api_key"),
            timeout=settings.get("local_timeout", 60),
        )
    return None


def _build_transcript(settings: Settings) -> ConversationTranscript | None:
    """Instancier le transcripteur de conversation si la persistance est active."""
    if not settings.conversation_persist:
        return None
    try:
        # Le chemin de la base est confiné aux racines autorisées
        # (répertoire du projet et dossier data/), comme pour la mémoire.
        db_path = resolve_authorized_path(settings.conversation_db_path)
    except PathSecurityError as exc:
        print(
            f"Avertissement : persistance des conversations désactivée : {exc}",
            file=sys.stderr,
        )
        return None
    return ConversationTranscript(enabled=True, db_path=str(db_path))


def _build_mission_store(settings: Settings) -> MissionStore | None:
    """Instancier le stockage des missions si la persistance est active."""
    if not settings.mission_persist:
        return None
    try:
        db_path = resolve_authorized_path(settings.mission_db_path)
    except PathSecurityError as exc:
        print(
            f"Avertissement : persistance des missions désactivée : {exc}",
            file=sys.stderr,
        )
        return None
    return MissionStore(enabled=True, db_path=str(db_path))


def _build_web_authenticator(settings: Settings) -> tuple[WebAuthenticator, str]:
    """Construire l'authentificateur de l'interface web.

    Si aucun identifiant n'est configuré, un jeton d'accès est généré et
    **affiché une seule fois** à l'utilisateur : la possession de ce jeton
    est requise pour toute requête. Rien n'est écrit sur disque.

    Returns:
        Le couple ``(authentificateur, jeton à afficher)``. Le jeton est
        vide si l'authentification était déjà configurée.
    """
    authenticator = WebAuthenticator.from_settings(settings)
    if authenticator.is_configured:
        return authenticator, ""
    token = generate_access_token()
    return WebAuthenticator(WebCredentialStore({"local": token})), token


def _list_conversations(transcript: ConversationTranscript | None) -> int:
    """Afficher les conversations enregistrées. Retourner le code de sortie."""
    if transcript is None or not transcript.is_available:
        print("Aucune conversation enregistrée (persistance désactivée).")
        return 0
    conversations = transcript.list_conversations(limit=50)
    if not conversations:
        print("Aucune conversation enregistrée.")
        return 0
    print("Conversations enregistrées :")
    for conv in conversations:
        print(
            f"  {conv['id']}  {conv['message_count']:>4} message(s)  "
            f"{conv['updated_at']}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings(config_path=args.config)
    except Exception as exc:  # noqa: BLE001 — erreur de configuration fatale
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        print("Consultez config/config.json.example et .env.example.", file=sys.stderr)
        return 1

    if args.provider is not None:
        settings.provider = args.provider

    transcript = None if args.no_persist else _build_transcript(settings)

    if args.list_conversations:
        return _list_conversations(transcript)

    provider = _build_provider(settings)

    # Service d'outils : registre alimenté, permissions accordées par
    # l'application. Le même service est partagé entre le CLI et l'interface
    # web : aucune duplication de la logique métier.
    #
    # Les autorisations (grants) sont liées à la session courante et à la
    # mission : elles expirent, sont bornées en nombre d'usages et ne
    # peuvent pas être rejouées dans un autre contexte.
    session_id = default_session_id("miles")
    grant_registry = GrantRegistry()
    tool_service = ToolService(grant_checker=grant_registry)

    memory = None
    if settings.memory_enabled:
        try:
            # Le chemin de la base mémoire est confiné aux racines
            # autorisées (répertoire du projet et dossier data/). Un chemin
            # relatif est résolu par rapport à la racine du projet.
            db_path = resolve_authorized_path(settings.memory_db_path)
            memory = PersistentMemory(
                enabled=True,
                db_path=str(db_path),
                max_memories_in_context=settings.memory_max_memories_in_context,
                max_content_length=settings.memory_max_content_length,
            )
        except (PathSecurityError, PersistentMemoryError) as exc:
            print(f"Avertissement : mémoire persistante non disponible : {exc}", file=sys.stderr)
        else:
            if memory is not None and not memory.is_available:
                print("Avertissement : mémoire persistante non disponible.", file=sys.stderr)

    conversation = Conversation(
        history_limit=settings.get("history_limit", 10),
    )

    # Orchestrateur de missions : même service d'outils, mêmes autorisations.
    mission_runner = None
    mission_store = None
    if settings.mission_enabled:
        mission_store = _build_mission_store(settings)
        mission_runner = MissionRunner(
            tool_service,
            provider=provider,
            store=mission_store,
            limits=ExecutionLimits(
                max_steps=settings.mission_max_steps,
                max_attempts_per_step=settings.mission_max_attempts,
                max_duration_seconds=float(settings.mission_max_duration_seconds),
            ),
            grant_registry=grant_registry,
            session_id=session_id,
        )

    # Restauration de la conversation : par défaut la dernière, sinon celle
    # demandée explicitement, sinon une nouvelle.
    restored = 0
    if transcript is not None and transcript.is_available:
        if args.conversation:
            status = conversation.attach_transcript(
                transcript, conversation_id=args.conversation
            )
            if status == "recreated":
                print(
                    f"Avertissement : conversation '{args.conversation}' "
                    "introuvable. Une nouvelle conversation a été créée : "
                    f"{conversation.conversation_id}.",
                    file=sys.stderr,
                )
            elif status == "restored":
                restored = len(conversation)
        elif args.new_conversation:
            conversation.attach_transcript(transcript)
        else:
            last_id = transcript.get_last_conversation_id()
            if last_id:
                conversation.attach_transcript(transcript, conversation_id=last_id)
                restored = len(conversation)
            else:
                # Première utilisation : on crée la première conversation.
                conversation.attach_transcript(transcript)

    if args.web:
        # Interface web locale : elle exige une authentification par jeton.
        authenticator, displayed_token = _build_web_authenticator(settings)
        web_app = WebApp(
            settings=settings,
            provider=provider,
            conversation=conversation,
            memory=memory,
            tool_service=tool_service,
            mission_runner=mission_runner,
            authenticator=authenticator,
        )
        server = MilesWebServer(web_app, port=args.web_port)
        if displayed_token:
            print("=" * 72)
            print("Jeton d'accès de l'interface web (affiché une seule fois) :")
            print(f"  {displayed_token}")
            print(
                "Saisissez ce jeton dans la page de connexion. "
                "Sans lui, aucune route sensible n'est accessible."
            )
            print("=" * 72)
        try:
            server.start()
        except KeyboardInterrupt:
            print("\nArrêt de l'interface web.")
            return 0
        finally:
            server.stop()
            if memory is not None:
                memory.close()
            if transcript is not None:
                transcript.close()
            if mission_store is not None:
                mission_store.close()
        return 0

    cli = CLI(
        settings=settings,
        provider=provider,
        conversation=conversation,
        memory=memory,
        tool_service=tool_service,
        mission_runner=mission_runner,
        session_id=session_id,
    )
    if restored:
        cli.set_restored_message_count(restored)

    try:
        cli.run()
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur. Au revoir !")
        return 0
    except EOFError:
        print("\nFin de saisie. Au revoir !")
        return 0
    finally:
        # Libération des ressources dans tous les cas (sortie normale,
        # exception, interruption). La mémoire est fermée après la
        # conversation : elle n'est plus utilisée à ce stade.
        if transcript is not None:
            transcript.close()
        if mission_store is not None:
            mission_store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
