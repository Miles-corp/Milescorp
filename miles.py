#!/usr/bin/env python3
"""MILES — Assistant personnel intelligent. Point d'entrée du programme."""

import sys
import argparse
import os

from app.ai_providers.local import LocalProvider
from app.ai_providers.remote import RemoteProvider
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.interface.cli import CLI
from app.interface.web import (
    LAN_HOST_ENV,
    LOCAL_ONLY_HOST,
    MilesWebServer,
    WebApp,
    WebServerSecurityError,
    assert_listen_host,
)
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
    parser.add_argument(
        "--web-lan",
        action="store_true",
        help=(
            "Exposer l'interface web sur une adresse privée du réseau local "
            f"(exige un jeton porteur configuré et {LAN_HOST_ENV})"
        ),
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Assistant de configuration : enregistrer le fournisseur et sa clé API dans .env (saisie masquée, aucun affichage de secret)",
    )
    parser.add_argument(
        "--link",
        metavar="PROVIDER",
        default=None,
        help="Lier un compte OAuth (ex. google) pour réduire les étapes de configuration (flux authorization code, serveur de rappel local)",
    )
    return parser


def _build_provider(settings: Settings):
    """Instancier le fournisseur IA configuré, ou None si inconnu.

    Multi-IA (mission) : si MILES_REMOTE_PROVIDER est défini (une
    commande /provider <x> l'écrit), le registre construit l'adaptateur
    NATIF du fournisseur (groq/openai compat, anthropic, gemini).
    Sinon : voie rétrocompatible historique INCHANGÉE à partir de
    MILES_REMOTE_* — l'installation existante continue de fonctionner.
    Un échec de construction n'est jamais silencieux : avertissement en
    err, puis aucun fournisseur (pas de repli caché sur un autre).
    """
    if settings.provider == "local":
        return LocalProvider(
            base_url=settings.get("local_base_url"),
            model=settings.get("local_model"),
            api_key=settings.get("local_api_key"),
            timeout=settings.get("local_timeout", 60),
        )
    # --- Multi-IA : fournisseur distant choisi explicitement
    from app.ai_providers.registry import build_provider, est_soutenu
    from app.config.provider_config import cle_pour, modele_fournisseur, fournisseur_actif

    nom = fournisseur_actif(defaut=None)
    if nom and est_soutenu(nom):
        modele = modele_fournisseur(nom) or settings.get("remote_model")
        try:
            return build_provider(
                nom,
                model=modele or "",
                api_key=cle_pour(nom) or settings.get("remote_api_key"),
                base_url=settings.get("remote_base_url") or None,
                timeout=int(settings.get("remote_timeout", 30)),
            )
        except ValueError as exc:
            print(
                f"Avertissement : fournisseur {nom} inutilisable ({exc}).",
                file=sys.stderr,
            )
            return None
    # --- Rétrocompatibilité : historique inchangé (MILES_REMOTE_*)
    return RemoteProvider(
        base_url=settings.get("remote_base_url"),
        model=settings.get("remote_model"),
        api_key=settings.get("remote_api_key"),
        timeout=settings.get("remote_timeout", 30),
    )


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


def _lan_refusal_reason(settings: Settings) -> str | None:
    """Motiver un refus d'écoute réseau, ou ``None`` si elle est autorisée.

    L'ouverture au réseau local est un choix explicite qui exige **deux**
    conditions, vérifiées avant toute liaison :

    - un jeton porteur **persistant** (``MILES_WEB_AUTH_TOKEN``) : un jeton
      éphémère, affiché une fois puis perdu au redémarrage, ne convient pas
      à un service joignable par le réseau ;
    - une adresse privée explicite, jamais « toutes les interfaces ».

    Le refus est prononcé au démarrage : MILES ne démarre pas à moitié
    exposé.
    """
    if not WebAuthenticator.from_settings(settings).is_configured:
        return (
            "option --web-lan refusée : aucun jeton porteur n'est configuré "
            "(MILES_WEB_AUTH_TOKEN). Sur le réseau local, MILES exige une "
            "authentification persistante, pas un jeton éphémère."
        )
    host = os.environ.get(LAN_HOST_ENV, "").strip()
    if not host:
        return (
            f"option --web-lan refusée : {LAN_HOST_ENV} doit nommer une adresse "
            "privée explicite (ex. 192.168.1.42). 0.0.0.0 n'est jamais accepté."
        )
    try:
        assert_listen_host(host, allow_lan=True)
    except WebServerSecurityError as exc:
        return f"option --web-lan refusée : {exc}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.web_lan and not args.web:
        print("Erreur : --web-lan n'a de sens qu'avec --web.", file=sys.stderr)
        return 1

    # L'assistant de configuration est exécutable même avec une configuration
    # défaillante : il écrit le `.env`, il ne le lit pas via Settings.
    if args.setup:
        from app.config.setup import run_setup

        return run_setup(
            env_path=os.environ.get("MILES_ENV_FILE", ".env"),
        )

    if args.link is not None:
        from app.config.oauth import link_account

        return link_account(
            args.link,
            env_path=os.environ.get("MILES_ENV_FILE", ".env"),
        )

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
    tool_service = ToolService(
        grant_checker=grant_registry,
        # Permissions de l'application : lecture système + écriture de note
        # (S3). L'écriture reste bornée à data/notes et exige la confirmation
        # humaine (outils MEDIUM) — la permission ne supprime pas le jeton.
        granted_permissions={"lecture_systeme", "ecriture_note"},
    )

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
                max_tool_calls=settings.mission_max_tool_calls,
                max_interactions=settings.mission_max_interactions,
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
        # Ouverture réseau : refusée au démarrage tant que les deux conditions
        # ne sont pas réunies (jeton persistant + adresse privée explicite).
        lan_host: str | None = None
        if args.web_lan:
            refusal = _lan_refusal_reason(settings)
            if refusal is not None:
                print(f"Erreur : {refusal}", file=sys.stderr)
                return 1
            lan_host = os.environ.get(LAN_HOST_ENV, "").strip()

        # Interface web : elle exige une authentification par jeton.
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
        server = MilesWebServer(
            web_app,
            host=lan_host or LOCAL_ONLY_HOST,
            port=args.web_port,
            allow_lan=bool(lan_host),
        )
        if lan_host:
            print(
                f"Attention : interface web exposée sur {lan_host}:{args.web_port} "
                "(mode LAN). Tout client du réseau local doit présenter le jeton."
            )
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
        if memory is not None:
            memory.close()
        if transcript is not None:
            transcript.close()
        if mission_store is not None:
            mission_store.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
