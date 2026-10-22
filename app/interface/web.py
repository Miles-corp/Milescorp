"""Interface web minimale de MILES (stdlib http.server).

Sépare clairement :
- le serveur web (ici) ;
- la logique applicative (WebApp) ;
- les fournisseurs IA (injectés via WebApp).

Par défaut, le serveur écoute uniquement sur 127.0.0.1.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable, Optional

from app.ai_providers.base import AIProvider, AIProviderError
from app.ai_providers.public_errors import public_provider_error as _public_provider_error
from app.config.settings import Settings
from app.core.conversation import Conversation
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.orchestration.models import Mission, MissionState
from app.orchestration.runner import (
    REASON_EXPIRED_APPROVAL_TOKEN,
    REASON_INTERACTION_BUDGET_EXCEEDED,
    REASON_INVALID_APPROVAL_TOKEN,
    REASON_MISSING_APPROVAL_TOKEN,
    REASON_MISSION_FINISHED,
    REASON_MISSION_NOT_FOUND,
    REASON_MISSION_NOT_OWNED,
    REASON_NO_PENDING_AUTHORIZATION,
    REASON_SESSION_MISMATCH,
    MissionAuthorizationError,
    MissionRunner,
)
from app.tools.grants import default_session_id
from app.tools.service import ToolService
from app.interface.web_auth import (
    CSRF_HEADER,
    SESSION_HEADER,
    OriginPolicy,
    WebAuthError,
    WebAuthenticator,
    WebSession,
)
from app.utilities.redaction import REDACTED, sanitize_text

logger = logging.getLogger("miles.web")
if not logger.handlers:
    # Handler neutre : l'application reste libre de configurer la
    # journalisation. Évite la sortie "No handlers could be found" et
    # n'écrit rien sur stderr par défaut.
    logger.addHandler(logging.NullHandler())

__all__ = [
    "REDACTED",
    "sanitize_text",
    "public_provider_error",
    "LOCAL_ONLY_HOST",
    "MAX_BODY_BYTES",
    "WebServerSecurityError",
    "RequestBodyError",
    "assert_local_host",
    "WebApp",
    "MilesHandler",
    "MilesWebServer",
]

# Adresse d'écoute du serveur web. Elle est imposée par le code et n'est
# pas configurable : le service MILES doit rester strictement local, jamais
# joignable depuis le réseau local ou Internet.
LOCAL_ONLY_HOST = "127.0.0.1"

# Taille maximale du corps d'une requête HTTP, en octets (64 KiB).
# Au-delà, la requête est refusée avec HTTP 413 sans que les données
# annoncées soient lues ou allouées. Le corps n'est JAMAIS lu au-delà de
# cette limite : c'est une invariant de sécurité (un client ne peut pas
# forcer le serveur à consommer de la mémoire en annonçant une taille).
MAX_BODY_BYTES = 65536

# Code de refus : la mission est encore en cours de traitement, l'action
# demandée n'a pas été appliquée (le client peut réessayer).
REASON_MISSION_BUSY = "mission_busy"


class WebServerSecurityError(Exception):
    """Refus de démarrer le serveur web sur une adresse non locale."""


class RequestBodyError(Exception):
    """Corps de requête HTTP invalide (en-tête ou taille).

    Le statut HTTP à renvoyer au client est porté par l'exception.
    """

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def assert_local_host(host: str) -> str:
    """Vérifier qu'une adresse d'écoute est strictement locale.

    Seule l'adresse 127.0.0.1 est acceptée. Toute autre adresse est
    refusée explicitement, y compris 0.0.0.0, :: et les adresses du
    réseau local.
    """
    if not isinstance(host, str):
        raise WebServerSecurityError(
            f"Adresse d'écoute invalide : {host!r}. Le serveur web MILES "
            f"n'écoute que sur {LOCAL_ONLY_HOST}."
        )
    if host != LOCAL_ONLY_HOST:
        raise WebServerSecurityError(
            f"Adresse d'écoute refusée : {host!r}. Le serveur web MILES est "
            f"strictement local et n'écoute que sur {LOCAL_ONLY_HOST}."
        )
    return host

# Motifs de secrets : définis dans app/utilities/redaction.py (source unique
# de vérité, partagée avec la persistance des conversations).
# La classification publique des erreurs fournisseur est définie dans
# app/ai_providers/public_errors.py (source unique, partagée avec le CLI).


def public_provider_error(exc: Exception) -> str:
    """Retourner un message public sûr pour une erreur de fournisseur.

    Ré-exporté depuis ``app.ai_providers.public_errors`` afin que l'interface
    terminal et l'interface web exposent exactement le même message.
    """
    return _public_provider_error(exc)


class WebApp:
    """Logique applicative exposée par l'interface web.

    Dépend uniquement des composants métier de MILES (fournisseurs,
    conversation, mémoire persistante, configuration). Aucun accès shell
    arbitraire n'est permis.
    """

    def __init__(
        self,
        settings: Settings,
        provider: Optional[AIProvider] = None,
        conversation: Optional[Conversation] = None,
        memory: Optional[PersistentMemory] = None,
        tool_service: Optional[ToolService] = None,
        mission_runner: Optional[MissionRunner] = None,
        session_id: Optional[str] = None,
        authenticator: Optional[WebAuthenticator] = None,
        allowed_origins: Optional[Iterable[str]] = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.conversation = conversation or Conversation(
            history_limit=settings.get("history_limit", 10)
        )
        self.memory = memory
        # Même service d'outils que le CLI : aucune duplication de la
        # logique métier (validation, permissions, confirmation, audit).
        self.tool_service = tool_service
        self.mission_runner = mission_runner
        # Identité technique de l'application (utilisée hors interface web,
        # par exemple par un intégrateur). Elle n'est **jamais** utilisée
        # comme identité d'un client web : chaque client dispose de sa
        # propre session authentifiée.
        self.session_id = session_id or default_session_id("web")
        # Authentification : si aucun identifiant n'est configuré,
        # l'interface web est fermée (les routes sensibles répondent 403).
        self.authenticator = authenticator or WebAuthenticator.from_settings(
            settings
        )
        origins = allowed_origins
        if origins is None:
            raw = str(settings.get("web_allowed_origins", "") or "")
            origins = [o.strip() for o in raw.split(",") if o.strip()]
        self.origin_policy = OriginPolicy(origins)
        self._mission_threads: dict[str, threading.Thread] = {}
        self._mission_lock = threading.Lock()

    # --- Outils ---

    def list_tools(self) -> dict[str, Any]:
        """Retourner le catalogue des outils disponibles."""
        if self.tool_service is None:
            return {"tools": [], "error": "Aucun service d'outils disponible."}
        return {"tools": self.tool_service.list_tools()}

    def run_tool(self, data: dict[str, Any], session: WebSession) -> dict[str, Any]:
        """Exécuter un outil via le service partagé (même moteur que le CLI).

        Le client peut transmettre ``confirmation_token`` et
        ``user_confirmed`` pour confirmer une action à effet externe. Le
        jeton n'est valide que pour la session qui l'a reçu : une autre
        session ne peut pas le rejouer.
        """
        if self.tool_service is None:
            return {"error": "Aucun service d'outils disponible."}

        tool_id = data.get("tool", data.get("tool_id", ""))
        if not isinstance(tool_id, str) or not tool_id.strip():
            return {"error": "Identifiant d'outil manquant."}

        raw_parameters = data.get("parameters", {})
        if raw_parameters is None:
            raw_parameters = {}
        if not isinstance(raw_parameters, dict):
            return {"error": "Paramètres invalides."}
        parameters = {str(k): v for k, v in raw_parameters.items()}

        user_confirmed = bool(data.get("user_confirmed", False))
        confirmation_token = data.get("confirmation_token")
        if confirmation_token is not None and not isinstance(confirmation_token, str):
            return {"error": "Jeton de confirmation invalide."}

        result = self.tool_service.request_tool(
            tool_id=tool_id.strip(),
            parameters=parameters,
            user_confirmed=user_confirmed,
            confirmation_token=confirmation_token,
            # Acteur = session authentifiée du client : le jeton de
            # confirmation est lié à ce client et à lui seul.
            actor_id=session.session_id,
        )
        return self.tool_service.describe_result(result)

    # --- Missions ---

    def list_missions(self, session: WebSession) -> dict[str, Any]:
        """Retourner la liste des missions de l'utilisateur connecté."""
        if self.mission_runner is None:
            return {"missions": [], "error": "Orchestrateur indisponible."}
        return {
            "missions": self.mission_runner.list_missions(
                limit=50, owner_user_id=session.user_id
            )
        }

    def mission_detail(self, mission_id: str, session: WebSession) -> dict[str, Any]:
        """Retourner l'état détaillé d'une mission de l'utilisateur."""
        if self.mission_runner is None:
            return {"error": "Orchestrateur indisponible."}
        mission = self.mission_runner.get(
            mission_id, owner_user_id=session.user_id
        )
        if mission is None:
            return {"error": f"Mission inconnue : {mission_id}"}
        return self._mission_payload(mission)

    def create_mission(self, objective: Any, session: WebSession) -> dict[str, Any]:
        """Créer une mission et lancer son exécution en arrière-plan.

        Une mission identique déjà en cours n'est pas relancée : un double
        clic ou une requête répétée ne produit pas deux exécutions.
        """
        if self.mission_runner is None:
            return {"error": "Orchestrateur indisponible."}
        if not isinstance(objective, str) or not objective.strip():
            return {"error": "Objectif de mission manquant."}

        existing = self.mission_runner.find_running(objective.strip())
        if existing is not None and existing.owner_user_id == session.user_id:
            payload = self._mission_payload(existing)
            payload["already_running"] = True
            return payload

        try:
            mission = self.mission_runner.create(
                objective.strip(),
                owner_user_id=session.user_id,
                owner_session_id=session.session_id,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        self._start_mission_thread(mission.mission_id, self.mission_runner.run)
        return self._mission_payload(mission)

    def authorize_mission(
        self, mission_id: str, data: dict[str, Any], session: WebSession
    ) -> dict[str, Any]:
        """Accorder ou refuser l'autorisation demandée par une mission.

        Le demandeur doit être l'utilisateur propriétaire de la mission et
        présenter le jeton d'approbation de la demande en attente. Une
        simple valeur booléenne fournie par le client ne suffit pas.

        La réponse n'est **positive** que si l'autorisation a réellement été
        acceptée : le jeton est validé de façon synchrone, avant le
        lancement du fil d'exécution (défaut D1-bis). Sans cette
        validation, le serveur répondait 200 « approved » alors que la
        validation échouait dans le fil, que l'autorisation n'était pas
        accordée et que la mission restait en attente.
        """
        if self.mission_runner is None:
            return {"error": "Orchestrateur indisponible."}
        mission = self.mission_runner.get(mission_id)
        if mission is None:
            return {
                "error": f"Mission inconnue : {mission_id}",
                "reason": REASON_MISSION_NOT_FOUND,
            }
        if mission.state.is_terminal:
            return {
                "error": "La mission est deja terminee.",
                "reason": REASON_MISSION_FINISHED,
            }
        if mission.pending is None or mission.pending.kind != "authorization":
            return {
                "error": "Aucune autorisation en attente pour cette mission.",
                "reason": REASON_NO_PENDING_AUTHORIZATION,
            }
        if (
            mission.owner_user_id
            and mission.owner_user_id != session.user_id
        ):
            return {
                "error": "Cette mission appartient a un autre utilisateur.",
                "reason": REASON_MISSION_NOT_OWNED,
            }

        approval_token = data.get("approval_token")
        if not isinstance(approval_token, str) or not approval_token:
            return {
                "error": "Jeton d'autorisation manquant.",
                "reason": REASON_MISSING_APPROVAL_TOKEN,
            }

        approved = bool(data.get("approved", False))

        # Validation SYNCHRONE du jeton, de l'expiration et de la session
        # (défaut D1-bis) : l'autorisation n'est annoncée comme accordée
        # que si elle l'a réellement été. Les messages d'erreur ne
        # contiennent ni jeton, ni identifiant de session, ni secret.
        try:
            self.mission_runner.check_authorization(
                mission_id,
                approval_token=approval_token,
                requester_user_id=session.user_id,
                requester_session_id=session.session_id,
            )
        except MissionAuthorizationError as exc:
            return {"error": str(exc), "reason": exc.reason}

        try:
            started = self._start_mission_thread(
                mission_id,
                lambda mid: self.mission_runner.authorize(
                    mid,
                    approved=approved,
                    requester_user_id=session.user_id,
                    requester_session_id=session.session_id,
                    approval_token=approval_token,
                ),
            )
        except MissionAuthorizationError as exc:
            return {"error": str(exc), "reason": exc.reason}
        if not started:
            # Une autre action est encore en cours pour cette mission :
            # l'autorisation n'a pas ete appliquee. Le dire explicitement
            # plutot que d'annoncer un succes (defaut D1-bis).
            return {
                "error": (
                    "La mission est encore en cours de traitement : "
                    "l'autorisation n'a pas ete appliquee, reessayez."
                ),
                "reason": REASON_MISSION_BUSY,
            }
        return {"mission_id": mission_id, "approved": approved, "started": True}

    def answer_mission(
        self, mission_id: str, data: dict[str, Any], session: WebSession
    ) -> dict[str, Any]:
        """Transmettre une réponse à une demande en attente.

        La réponse n'est **positive** que si elle a réellement été traitée :
        la demande en attente est validée de façon synchrone (identité,
        propriété de la mission, état, expiration, session), avant le
        lancement du fil d'exécution (défaut D1-bis appliqué à cette
        route). Sans cette validation, le serveur répondait « answered »
        alors que la réponse était refusée dans le fil.

        Le **contrat** de la route est inchangé : le client transmet une
        réponse texte ; aucun jeton n'est exigé.
        """
        if self.mission_runner is None:
            return {"error": "Orchestrateur indisponible."}
        mission = self.mission_runner.get(
            mission_id, owner_user_id=session.user_id
        )
        if mission is None:
            return {
                "error": f"Mission inconnue : {mission_id}",
                "reason": REASON_MISSION_NOT_FOUND,
            }
        answer = data.get("answer", "")
        if not isinstance(answer, str) or not answer.strip():
            return {"error": "Réponse vide."}

        # Validation SYNCHRONE de la demande en attente : identité, session,
        # propriété de la mission, état courant, expiration, budget. Les
        # messages ne contiennent ni jeton, ni identifiant de session, ni
        # secret.
        try:
            self.mission_runner.check_answer(
                mission_id,
                requester_user_id=session.user_id,
                requester_session_id=session.session_id,
            )
        except MissionAuthorizationError as exc:
            return {"error": str(exc), "reason": exc.reason}

        try:
            started = self._start_mission_thread(
                mission_id,
                lambda mid: self.mission_runner.answer(
                    mid,
                    answer.strip(),
                    requester_user_id=session.user_id,
                    requester_session_id=session.session_id,
                ),
            )
        except MissionAuthorizationError as exc:
            return {"error": str(exc), "reason": exc.reason}
        if not started:
            return {
                "error": (
                    "La mission est encore en cours de traitement : "
                    "la reponse n'a pas ete enregistree, reessayez."
                ),
                "reason": REASON_MISSION_BUSY,
            }
        return {"mission_id": mission_id, "answered": True, "started": True}

    def cancel_mission(self, mission_id: str, session: WebSession) -> dict[str, Any]:
        """Demander l'arrêt d'une mission."""
        if self.mission_runner is None:
            return {"error": "Orchestrateur indisponible."}
        mission = self.mission_runner.get(
            mission_id, owner_user_id=session.user_id
        )
        if mission is None:
            return {"error": f"Mission {mission_id} introuvable ou déjà terminée."}
        cancelled = self.mission_runner.cancel(mission_id)
        if not cancelled:
            return {"error": f"Mission {mission_id} introuvable ou déjà terminée."}
        return {"mission_id": mission_id, "cancelled": True}

    def _start_mission_thread(self, mission_id: str, action: Any) -> bool:
        """Lancer une action de mission dans un fil d'exécution séparé.

        Le fil est un démon : il n'empêche pas l'arrêt du programme. Une
        mission déjà en cours d'exécution n'est pas relancée.

        Returns:
            True si l'action a été lancée, False si une autre action est
            encore en cours pour cette mission : l'action est alors
            **ignorée** et l'appelant doit le signaler (une réponse
            « started » serait un mensonge, défaut D1-bis).
        """
        with self._mission_lock:
            existing = self._mission_threads.get(mission_id)
            if existing is not None and existing.is_alive():
                return False

            def _target() -> None:
                try:
                    action(mission_id)
                except Exception:  # noqa: BLE001 — un échec ne doit pas tuer le serveur
                    logger.error(
                        "Erreur interne pendant l'execution de la mission %s.",
                        mission_id,
                    )

            thread = threading.Thread(
                target=_target, name=f"mission-{mission_id}", daemon=True
            )
            self._mission_threads[mission_id] = thread
            thread.start()
            return True

    @staticmethod
    def _mission_payload(mission: Mission) -> dict[str, Any]:
        """Construire la charge utile d'une mission pour le client web."""
        steps = []
        if mission.plan is not None:
            for step in mission.plan.steps:
                steps.append(
                    {
                        "step_id": step.step_id,
                        "objective": step.objective,
                        "tool": step.tool_id,
                        "status": step.status.value,
                        "attempts": step.attempts,
                        "error": sanitize_text(step.error),
                        "note": sanitize_text(step.note),
                    }
                )
        pending = None
        if mission.pending is not None:
            pending = {
                "kind": mission.pending.kind,
                "question": sanitize_text(mission.pending.question),
                "tool_ids": list(mission.pending.tool_ids),
                "allowed_roots": list(mission.pending.allowed_roots),
                # Jeton d'approbation : propre à cette demande et à ce
                # client (la charge utile n'est servie qu'au propriétaire
                # de la mission).
                "approval_token": mission.pending.approval_token,
                "expires_at": mission.pending.expires_at,
            }
        return {
            "mission_id": mission.mission_id,
            "objective": sanitize_text(mission.objective),
            "state": mission.state.value,
            "planner": mission.planner,
            "planner_note": sanitize_text(mission.planner_note),
            "steps": steps,
            "facts": [sanitize_text(f) for f in mission.facts],
            "errors": [sanitize_text(e) for e in mission.errors],
            "unfinished": [sanitize_text(u) for u in mission.unfinished],
            "budget": {
                "executed_seconds": round(mission.budget.executed_seconds, 2),
                "steps_executed": mission.budget.steps_executed,
                "tool_calls": mission.budget.tool_calls,
                "interactions": mission.budget.interactions,
                "stop_reason": mission.budget.stop_reason,
                "stop_detail": sanitize_text(mission.budget.stop_detail),
            },
            "pending": pending,
            "report": sanitize_text(mission.report),
            "created_at": mission.created_at,
            "updated_at": mission.updated_at,
        }

    # --- Fournisseur ---

    def provider_state(self) -> dict[str, Any]:
        """Retourner l'état du fournisseur IA."""
        name = self.provider.name if self.provider else "non configuré"
        available = False
        if self.provider is not None:
            try:
                available = self.provider.is_available()
            except Exception:  # noqa: BLE001 — ne pas faire tomber le serveur
                available = False
        return {
            "name": name,
            "available": available,
            "provider": self.settings.provider,
        }

    # --- Conversation ---

    def send_message(self, text: str) -> dict[str, Any]:
        """Envoyer un message à l'IA et retourner la réponse ou l'erreur."""
        if self.provider is None:
            return {
                "error": "Aucun fournisseur IA configuré.",
                "provider": self.settings.provider,
            }

        self.conversation.add_user_message(text)
        context = self.conversation.get_context()

        try:
            response = self.provider.chat(context)
        except AIProviderError as exc:
            # La conversation est conservée : le message utilisateur reste.
            # Le détail technique reste interne et assaini de tout secret.
            logger.error(
                "Échec de l'appel au fournisseur IA : %s", sanitize_text(exc)
            )
            return {
                "error": public_provider_error(exc),
                "provider": self.settings.provider,
                "context_preserved": True,
            }
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            # Aucune trace brute n'est journalisée : la trace d'appels
            # contiendrait le message d'origine de l'exception, donc
            # potentiellement un secret de format inconnu. Seul le nom de
            # la classe et le message assaini sont conservés.
            logger.error(
                "Erreur interne lors de l'appel au fournisseur IA (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {
                "error": "Erreur interne du service.",
                "provider": self.settings.provider,
                "context_preserved": True,
            }

        self.conversation.add_assistant_message(response)
        return {
            "response": response,
            "provider": self.settings.provider,
            "context_preserved": True,
        }

    # --- Mémoire persistante ---

    def memory_state(self) -> dict[str, Any]:
        """Retourner l'état de la mémoire persistante."""
        if self.memory is None:
            return {"enabled": False, "available": False}
        return {
            "enabled": True,
            "available": self.memory.is_available,
        }

    def list_memories(self, owner_user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Lister les souvenirs persistants.

        Args:
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur (et les souvenirs partages) sont listes :
                c'est l'isolation entre utilisateurs.
        """
        if self.memory is None or not self.memory.is_available:
            return []
        return self.memory.list_memories(owner_user_id=owner_user_id)

    def add_memory(
        self, content: str, owner_user_id: str = ""
    ) -> dict[str, Any]:
        """Enregistrer un souvenir explicite.

        Args:
            content: texte du souvenir.
            owner_user_id: propriétaire du souvenir (utilisateur
                authentifie) ; la chaine vide designe un souvenir partage.
        """
        if self.memory is None or not self.memory.is_available:
            return {"error": "Mémoire persistante indisponible ou désactivée."}
        try:
            mem_id = self.memory.add_memory(content, owner_user_id=owner_user_id)
            return {"id": mem_id, "content": content}
        except PersistentMemoryError as exc:
            # Message produit par MILES lui-même (texte fixe) : ne contient
            # aucune valeur sensible, il peut être renvoyé au client.
            logger.error(
                "Refus d'enregistrement d'un souvenir : %s", sanitize_text(exc)
            )
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — ne pas faire tomber le serveur
            logger.error(
                "Erreur interne lors de l'enregistrement d'un souvenir (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {"error": "Erreur interne du service."}

    def delete_memory(
        self, memory_id: int, owner_user_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Supprimer un souvenir ciblé.

        Args:
            memory_id: identifiant du souvenir.
            owner_user_id: si fourni, seuls les souvenirs de cet
                utilisateur (ou partages) peuvent etre supprimes.
        """
        if self.memory is None or not self.memory.is_available:
            return {"error": "Mémoire persistante indisponible ou désactivée."}
        try:
            deleted = self.memory.delete_memory(memory_id, owner_user_id=owner_user_id)
            if deleted:
                return {"id": memory_id, "deleted": True}
            return {"error": f"Aucun souvenir avec l'id {memory_id}."}
        except PersistentMemoryError as exc:
            # Message produit par MILES lui-même (texte fixe) : ne contient
            # aucune valeur sensible, il peut être renvoyé au client.
            logger.error(
                "Refus de suppression d'un souvenir : %s", sanitize_text(exc)
            )
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Erreur interne lors de la suppression d'un souvenir (%s) : %s",
                type(exc).__name__,
                sanitize_text(exc),
            )
            return {"error": "Erreur interne du service."}


class MilesHandler(BaseHTTPRequestHandler):
    """Gestionnaire des requêtes HTTP pour MILES."""

    # Délai maximal d'attente d'une requête. Évite qu'un client qui annonce
    # une taille puis n'envoie rien ne bloque un thread indéfiniment.
    timeout = 30

    # L'application métier est attachée au serveur via server.miles_app.
    app: Optional[WebApp] = None

    #: Vrai lorsque le corps de la requête a déjà été consommé.
    _body_consumed: bool = False

    def log_message(self, format: str, *args: Any) -> None:
        """Désactiver les logs de requête HTTP par défaut pour éviter
        l'exposition accidentelle de données sensibles dans les logs."""
        return  # noqa: D401

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict[str, Any]:
        """Lire et valider le corps de la requête.

        Le corps ne doit jamais dépasser MAX_BODY_BYTES octets. La taille
        annoncée est contrôlée AVANT toute lecture : un corps trop
        volumineux n'est donc ni lu ni alloué.

        Raises:
            RequestBodyError: en-tête Content-Length absent, négatif, non
                numérique, corps trop volumineux (413) ou incomplet.
        """
        self._body_consumed = False
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            length = 0
        else:
            try:
                length = int(raw_length)
            except (TypeError, ValueError):
                raise RequestBodyError(
                    400, "Requête mal formée : en-tête Content-Length invalide."
                ) from None
            if length < 0:
                raise RequestBodyError(
                    400, "Requête mal formée : en-tête Content-Length invalide."
                )
            if length > MAX_BODY_BYTES:
                # Refus immédiat : les données annoncées ne sont pas lues.
                # Le corps n'est jamais consommé au-delà de la limite, même
                # en partie : c'est ce qui garantit qu'un client ne peut pas
                # forcer une allocation mémoire côté serveur.
                # Conséquence assumée : le client peut voir sa connexion
                # réinitialisée au lieu de lire la réponse 413, s'il
                # écrivait encore son corps au moment du refus.
                raise RequestBodyError(
                    413,
                    "Requête trop volumineuse : le corps dépasse la limite autorisée.",
                )

        raw = b""
        if length > 0:
            try:
                raw = self.rfile.read(length)
            except (TimeoutError, OSError):
                raise RequestBodyError(
                    400, "Requête mal formée : corps de requête incomplet."
                ) from None
            if len(raw) < length:
                raise RequestBodyError(
                    400, "Requête mal formée : corps de requête incomplet."
                )

        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict):
            raise RequestBodyError(
                400, "Requête mal formée : corps JSON invalide."
            )
        # Le corps a été intégralement consommé : un refus ultérieur ne
        # doit pas tenter de le relire (ce qui bloquerait la connexion).
        self._body_consumed = True
        return data

    def _html_escape(self, text: str) -> str:
        return html.escape(text or "", quote=True)

    # --- Routes ---

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/":
            # Page publique : elle ne contient aucune donnée, seulement la
            # coque de l'interface et le formulaire de connexion.
            self._serve_index()
            return

        session = self._require_session()
        if session is None:
            return

        if path == "/status":
            self._handle_status()
        elif path == "/memory":
            self._handle_list_memories(session)
        elif path == "/tools":
            self._handle_list_tools()
        elif path == "/missions":
            self._handle_list_missions(session)
        elif path.startswith("/mission/"):
            self._handle_mission_detail(path, session)
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        # 1. Origine de la requête (contrôle CSRF de premier niveau).
        #    Ce contrôle est effectué AVANT toute lecture de corps et
        #    AVANT toute action : une requête refusée n'a aucun effet de
        #    bord.
        allowed, reason = self._check_origin()
        if not allowed:
            self._reject(403, reason)
            return

        # 2. Type de contenu : seules les requêtes JSON sont admises.
        if not self._check_content_type():
            self._reject(
                415,
                "Type de contenu non supporté : application/json est requis.",
            )
            return

        # 3. Lecture du corps (après les contrôles précédents).
        try:
            data = self._read_body()
        except RequestBodyError as exc:
            # Le corps n'a pas été lu : la connexion ne peut plus être
            # réutilisée pour une requête suivante.
            self.close_connection = True
            self._send_json(exc.status, {"error": exc.message})
            return

        # 4. Authentification. La connexion (POST /session) est le seul
        #    point d'entrée public : c'est elle qui échange un jeton
        #    d'accès contre une session.
        if path == "/session":
            self._handle_login(data)
            return

        session = self._require_session()
        if session is None:
            return

        # 5. Jeton CSRF : obligatoire sur toute requête modifiante.
        if not self._check_csrf(session):
            self._reject(403, "Jeton CSRF absent ou invalide.")
            return

        if path == "/message":
            self._handle_message(data)
        elif path == "/remember":
            self._handle_remember(data, session)
        elif path == "/forget":
            self._handle_forget(data, session)
        elif path == "/tool":
            self._handle_run_tool(data, session)
        elif path == "/mission":
            self._handle_create_mission(data, session)
        elif re.match(r"^/mission/[^/]+/authorize$", path):
            self._handle_mission_authorize(path, data, session)
        elif re.match(r"^/mission/[^/]+/answer$", path):
            self._handle_mission_answer(path, data, session)
        elif re.match(r"^/mission/[^/]+/cancel$", path):
            self._handle_mission_cancel(path, session)
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    # --- Handlers ---

    def _serve_index(self) -> None:
        html_content = self._build_index_html()
        body = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _build_index_html(self) -> str:
        provider_state = self.app.provider_state() if self.app else {}
        memory_state = self.app.memory_state() if self.app else {}

        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>MILES — Assistant personnel</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; }}
#chat {{ border: 1px solid #ccc; border-radius: 8px; padding: 1rem; height: 40vh; overflow-y: auto; background: #fafafa; margin-bottom: 1rem; }}
.msg {{ margin: 0.5rem 0; padding: 0.5rem; border-radius: 6px; }}
.user {{ background: #e3f2fd; }}
.assistant {{ background: #e8f5e9; }}
.error {{ background: #ffebee; color: #b71c1c; }}
.system {{ background: #eeeeee; color: #666; font-size: 0.9rem; }}
input[type="text"] {{ width: 70%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }}
button {{ padding: 0.5rem 1rem; border: none; background: #1976d2; color: white; border-radius: 4px; cursor: pointer; }}
button:hover {{ background: #1565c0; }}
button.secondary {{ background: #757575; }}
button.secondary:hover {{ background: #616161; }}
.status {{ margin: 1rem 0; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; font-size: 0.9rem; }}
.memories {{ margin: 1rem 0; }}
.memories ul {{ list-style: none; padding: 0; }}
.memories li {{ margin: 0.25rem 0; padding: 0.25rem; background: #f5f5f5; border-radius: 4px; }}
.tools {{ margin: 1rem 0; }}
.tools ul {{ list-style: none; padding: 0; }}
.tools li {{ margin: 0.35rem 0; padding: 0.35rem; background: #f5f5f5; border-radius: 4px; font-size: 0.9rem; }}
.tools code {{ background: #e0e0e0; padding: 0 0.25rem; border-radius: 3px; }}
.tools input[type="text"] {{ width: auto; padding: 0.25rem; border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; }}
.login {{ margin: 1rem 0; padding: 1rem; background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px; }}
.login input[type="password"] {{ width: 60%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }}
</style>
</head>
<body>
<h1>MILES — Assistant personnel</h1>

<div id="login" class="login">
<strong>Connexion requise</strong>
<p>L'interface web exige un jeton d'accès. Saisissez le jeton affiché au démarrage du serveur MILES.</p>
<form id="loginForm" onsubmit="return login(event)">
<input type="password" id="token" placeholder="Jeton d'accès" autocomplete="off">
<button type="submit">Se connecter</button>
</form>
<div id="loginError" class="msg error" style="display:none"></div>
</div>

<div id="app" style="display:none">
<div class="status">
<strong>Fournisseur :</strong> {self._html_escape(str(provider_state.get('name', '—')))}<br>
<strong>Disponible :</strong> {'oui' if provider_state.get('available') else 'non'}<br>
<strong>Mémoire :</strong> {'activée' if memory_state.get('available') else 'désactivée/indisponible'}
</div>

<div id="chat">
<div class="msg system">Bienvenue dans MILES. Tapez votre message ci-dessous.</div>
</div>

<form id="form" onsubmit="return sendMessage(event)">
<input type="text" id="input" placeholder="Votre message..." autocomplete="off">
<button type="submit">Envoyer</button>
<button type="button" class="secondary" onclick="loadStatus()">Rafraîchir le statut</button>
</form>

<div class="memories" id="memories"></div>

<div class="tools" id="tools">
<strong>Outils :</strong>
<div id="toolsList"><p>Chargement…</p></div>
</div>
</div>

<script>
// Session authentifiée : le jeton de session et le jeton CSRF ne sont
// conservés qu'en mémoire (jamais dans un cookie ni dans le stockage local).
let sessionId = null;
let csrfToken = null;

function authHeaders() {{
  const headers = {{ 'Content-Type': 'application/json' }};
  if (sessionId) headers['X-MILES-Session'] = sessionId;
  if (csrfToken) headers['X-MILES-CSRF'] = csrfToken;
  return headers;
}}

function showLogin() {{
  document.getElementById('login').style.display = 'block';
  document.getElementById('app').style.display = 'none';
}}

function showApp() {{
  document.getElementById('login').style.display = 'none';
  document.getElementById('app').style.display = 'block';
}}

async function login(e) {{
  e.preventDefault();
  const token = document.getElementById('token').value.trim();
  const errorBox = document.getElementById('loginError');
  errorBox.style.display = 'none';
  try {{
    const res = await fetch('/session', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ token: token }})
    }});
    const data = await res.json();
    if (!res.ok) {{
      errorBox.textContent = data.error || 'Connexion refusee.';
      errorBox.style.display = 'block';
      return false;
    }}
    sessionId = data.session_id;
    csrfToken = data.csrf_token;
    document.getElementById('token').value = '';
    showApp();
    loadStatus();
  }} catch (err) {{
    errorBox.textContent = 'Erreur reseau : ' + err;
    errorBox.style.display = 'block';
  }}
  return false;
}}

async function sendMessage(e) {{
  e.preventDefault();
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return false;
  appendMessage('user', text);
  input.value = '';
  try {{
    const res = await fetch('/message', {{
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({{ message: text }})
    }});
    if (res.status === 401) {{ showLogin(); return false; }}
    const data = await res.json();
    if (data.response) appendMessage('assistant', data.response);
    if (data.error) appendMessage('error', 'Erreur : ' + data.error);
  }} catch (err) {{
    appendMessage('error', 'Erreur réseau : ' + err);
  }}
  return false;
}}

async function loadStatus() {{
  try {{
    const res = await fetch('/status', {{ headers: authHeaders() }});
    if (res.status === 401) {{ showLogin(); return; }}
    const data = await res.json();
    document.querySelector('.status').innerHTML =
      '<strong>Fournisseur :</strong> ' + escapeHtml(data.name) + '<br>' +
      '<strong>Disponible :</strong> ' + (data.available ? 'oui' : 'non') + '<br>' +
      '<strong>Mémoire :</strong> ' + (data.memory_available ? 'activée' : 'désactivée/indisponible');
    loadMemories();
  }} catch (err) {{ console.error(err); }}
}}

async function loadMemories() {{
  try {{
    const res = await fetch('/memory', {{ headers: authHeaders() }});
    const data = await res.json();
    const container = document.getElementById('memories');
    if (!Array.isArray(data) || data.length === 0) {{
      container.innerHTML = '<p>Aucun souvenir enregistré.</p>';
      return;
    }}
    container.innerHTML = '<strong>Souvenirs :</strong><ul>' +
      data.map(m => '<li>[{0}] {1} (catégorie: {{m.category}}, importance: {{m.importance}})</li>'.replace('{{0}}', m.id).replace('{{1}}', escapeHtml(m.content))).join('') +
      '</ul>';
  }} catch (err) {{ console.error(err); }}
}}

async function loadTools() {{
  const container = document.getElementById('toolsList');
  try {{
    const res = await fetch('/tools', {{ headers: authHeaders() }});
    if (res.status === 401) {{ showLogin(); return; }}
    const data = await res.json();
    if (!Array.isArray(data.tools) || data.tools.length === 0) {{
      container.innerHTML = '<p>Aucun outil disponible.</p>';
      return;
    }}
    container.innerHTML = '<ul>' + data.tools.map(t => {{
      const champs = (t.parameters || []).map(p =>
        '<input type="text" data-tool="' + escapeHtml(t.id) + '" data-param="' + escapeHtml(p.name) +
        '" data-type="' + escapeHtml(p.type) + '" placeholder="' + escapeHtml(p.name) + '" size="12">'
      ).join(' ');
      return '<li><code>' + escapeHtml(t.id) + '</code> [' + escapeHtml(t.risk_level) + '] ' +
        escapeHtml(t.description) +
        (t.requires_confirmation ? ' <em>(confirmation requise)</em>' : '') +
        ' ' + champs +
        ' <button type="button" class="secondary" onclick="runTool(\\'' + escapeHtml(t.id) + '\\')">Exécuter</button></li>';
    }}).join('') + '</ul>';
  }} catch (err) {{
    container.innerHTML = '<p>Erreur de chargement des outils.</p>';
    console.error(err);
  }}
}}

function collectToolParams(toolId) {{
  const params = {{}};
  document.querySelectorAll('input[data-tool="' + toolId + '"]').forEach(input => {{
    const valeur = input.value.trim();
    if (!valeur) return;
    const type = input.getAttribute('data-type');
    if (type === 'int') {{
      params[input.getAttribute('data-param')] = parseInt(valeur, 10);
    }} else if (type === 'float') {{
      params[input.getAttribute('data-param')] = parseFloat(valeur);
    }} else if (type === 'bool') {{
      params[input.getAttribute('data-param')] = (valeur === 'true' || valeur === '1');
    }} else {{
      params[input.getAttribute('data-param')] = valeur;
    }}
  }});
  return params;
}}

async function postTool(toolId, params, userConfirmed, token) {{
  const body = {{ tool: toolId, parameters: params }};
  if (userConfirmed) {{
    body.user_confirmed = true;
    body.confirmation_token = token;
  }}
  const res = await fetch('/tool', {{
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body)
  }});
  return await res.json();
}}

async function runTool(toolId) {{
  const params = collectToolParams(toolId);
  let data = await postTool(toolId, params, false, null);
  if (data.confirmation_required) {{
    // Confirmation humaine explicite : l'utilisateur tranche dans le
    // navigateur avant que le jeton ne soit renvoyé.
    const ok = window.confirm("L'outil '" + toolId + "' requiert une confirmation humaine.\\nExécuter ?");
    if (!ok) {{
      appendMessage('system', 'Action annulée.');
      return;
    }}
    data = await postTool(toolId, params, true, data.confirmation_token);
  }}
  if (data.success) {{
    appendMessage('assistant', 'Résultat de ' + toolId + ' :\\n' + formatToolResult(data.result));
  }} else {{
    appendMessage('error', 'Outil ' + toolId + ' : ' + (data.error || 'échec'));
  }}
}}

function formatToolResult(result) {{
  if (result === null || result === undefined) return '(aucun résultat)';
  if (typeof result === 'object') return JSON.stringify(result, null, 2);
  return String(result);
}}

function appendMessage(role, text) {{
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}}

function escapeHtml(text) {{
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}}

// L'interface démarre en mode connecté : les requêtes sont refusées
// (401) tant qu'aucune session n'a été ouverte.
showLogin();
</script>
</body>
</html>"""

    def _handle_status(self) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        state = self.app.provider_state()
        state["memory_available"] = self.app.memory.is_available if self.app.memory else False
        self._send_json(200, state)

    def _handle_list_tools(self) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.list_tools()
        status = 200 if "error" not in payload else 503
        self._send_json(status, payload)

    def _handle_run_tool(self, data: dict[str, Any], session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.run_tool(data, session)
        # Une demande de confirmation est une réponse normale du protocole
        # (200 + jeton), pas une erreur : le client doit pouvoir confirmer.
        if payload.get("confirmation_required"):
            self._send_json(200, payload)
            return
        if not payload.get("success"):
            # Refus ou échec de l'outil : erreur côté appelant, pas serveur.
            self._send_json(400, payload)
            return
        self._send_json(200, payload)

    def _reject(self, status: int, message: str) -> None:
        """Refuser une requête sans effet de bord.

        Le corps de la requête est d'abord **consommé et jeté** (dans la
        limite de taille autorisée) : sans cela, le client qui écrit encore
        son corps voit sa connexion réinitialisée et ne peut pas lire la
        réponse de refus. La requête reste sans effet de bord : le corps
        n'est jamais interprété.

        La connexion est ensuite fermée pour éviter qu'une requête suivante
        ne soit interprétée à partir d'octets non consommés.
        """
        self._drain_body()
        self.close_connection = True
        self._send_json(status, {"error": message})

    def _drain_body(self) -> None:
        """Lire et jeter le corps annoncé, dans la limite de taille autorisée.

        Appelé uniquement lorsqu'un refus intervient **avant** la lecture du
        corps (contrôle d'origine, type de contenu) : le client peut ainsi
        lire la réponse de refus au lieu de voir sa connexion réinitialisée.

        Un corps plus volumineux que la limite n'est **pas** lu : le
        serveur refuse alors avant toute lecture (invariant S-004).
        """
        if getattr(self, "_body_consumed", False):
            # Le corps a déjà été lu : il ne reste rien à consommer.
            return
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            return
        remaining = length
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (TimeoutError, OSError):
            return
        self._body_consumed = True

    def _check_origin(self) -> tuple[bool, str]:
        """Vérifier l'origine de la requête (protection CSRF de niveau 1).

        - un ``Origin`` présent doit figurer dans la liste des origines
          autorisées ;
        - à défaut, un ``Referer`` présent doit l'être aussi ;
        - en l'absence des deux, la requête est admise **à ce stade** : elle
          doit alors satisfaire les contrôles de session authentifiée et de
          jeton CSRF, qu'un site tiers ne peut pas obtenir.
        """
        if self.app is None:
            return False, "Application non initialisée."
        origin = self.headers.get("Origin")
        referer = self.headers.get("Referer")
        host = self.headers.get("Host")
        return self.app.origin_policy.check(origin, referer, host)

    def _check_content_type(self) -> bool:
        """Vérifier que le corps de la requête est du JSON.

        Un contenu de type ``text/plain`` (ou absent) permet à un navigateur
        d'émettre une requête « simple » sans préflight CORS : c'est
        précisément le vecteur utilisé par l'attaque P1-6-03.
        """
        raw = self.headers.get("Content-Type") or ""
        media_type = raw.split(";", 1)[0].strip().lower()
        return media_type == "application/json"

    def _require_session(self) -> Optional[WebSession]:
        """Exiger une session web authentifiée.

        Retourne la session, ou None après avoir envoyé un refus.
        """
        if self.app is None:
            self._reject(500, "Application non initialisée.")
            return None
        if not self.app.authenticator.is_configured:
            # Fermé par défaut : sans identifiant configuré, aucune route
            # sensible n'est accessible.
            self._reject(
                403,
                "Authentification non configuree : l'interface web est fermee.",
            )
            return None
        session_id = self.headers.get(SESSION_HEADER) or ""
        session = self.app.authenticator.authenticate(
            session_id, user_agent=self.headers.get("User-Agent") or ""
        )
        if session is None:
            self._reject(401, "Session absente ou expiree : connectez-vous.")
            return None
        return session

    def _check_csrf(self, session: WebSession) -> bool:
        """Vérifier le jeton CSRF présenté par le client."""
        if self.app is None:
            return False
        token = self.headers.get(CSRF_HEADER) or ""
        return self.app.authenticator.verify_csrf(session, token)

    def _handle_login(self, data: dict[str, Any]) -> None:
        """Échanger un jeton d'accès contre une session web authentifiée."""
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        token = data.get("token", "")
        if not isinstance(token, str) or not token.strip():
            self._send_json(400, {"error": "Jeton d'accès manquant."})
            return
        try:
            session = self.app.authenticator.login(
                token.strip(),
                client_address=self.client_address[0],
                user_agent=self.headers.get("User-Agent") or "",
            )
        except WebAuthError as exc:
            self._send_json(401, {"error": str(exc)})
            return
        self._send_json(
            200,
            {
                "session_id": session.session_id,
                "csrf_token": session.csrf_token,
                "user_id": session.user_id,
                "expires_at": session.expires_at,
            },
        )

    def _handle_list_missions(self, session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.list_missions(session)
        status = 200 if "error" not in payload else 503
        self._send_json(status, payload)

    def _handle_mission_detail(self, path: str, session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        mission_id = path[len("/mission/") :].strip("/")
        if not mission_id:
            self._send_json(404, {"error": "Mission inconnue"})
            return
        payload = self.app.mission_detail(mission_id, session)
        status = 200 if "error" not in payload else 404
        self._send_json(status, payload)

    def _handle_create_mission(
        self, data: dict[str, Any], session: WebSession
    ) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        payload = self.app.create_mission(data.get("objective", ""), session)
        status = 200 if "error" not in payload else 400
        self._send_json(status, payload)

    def _handle_mission_authorize(
        self, path: str, data: dict[str, Any], session: WebSession
    ) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        mission_id = path.split("/")[2]
        payload = self.app.authorize_mission(mission_id, data, session)
        if "error" not in payload:
            status = 200
        elif payload.get("reason") == REASON_MISSION_BUSY:
            # La mission est en cours de traitement : l'action n'a pas été
            # appliquée, le client peut réessayer (409 Conflict).
            status = 409
        else:
            status = 403
        self._send_json(status, payload)

    def _handle_mission_answer(
        self, path: str, data: dict[str, Any], session: WebSession
    ) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        mission_id = path.split("/")[2]
        payload = self.app.answer_mission(mission_id, data, session)
        if "error" not in payload:
            status = 200
        elif payload.get("reason") == REASON_MISSION_BUSY:
            status = 409
        else:
            status = 403
        self._send_json(status, payload)

    def _handle_mission_cancel(self, path: str, session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        mission_id = path.split("/")[2]
        payload = self.app.cancel_mission(mission_id, session)
        status = 200 if "error" not in payload else 404
        self._send_json(status, payload)

    def _handle_list_memories(self, session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        memories = self.app.list_memories(owner_user_id=session.user_id)
        self._send_json(200, memories)

    def _handle_message(self, data: dict[str, Any]) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        text = data.get("message", "")
        if not isinstance(text, str) or not text.strip():
            self._send_json(400, {"error": "Message vide ou invalide."})
            return
        result = self.app.send_message(text.strip())
        status = 200 if "response" in result else 400
        self._send_json(status, result)

    def _handle_remember(self, data: dict[str, Any], session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        content = data.get("content", "")
        if not isinstance(content, str) or not content.strip():
            self._send_json(400, {"error": "Contenu vide ou invalide."})
            return
        result = self.app.add_memory(content.strip(), owner_user_id=session.user_id)
        status = 200 if "id" in result else 400
        self._send_json(status, result)

    def _handle_forget(self, data: dict[str, Any], session: WebSession) -> None:
        if self.app is None:
            self._send_json(500, {"error": "Application non initialisée"})
            return
        memory_id = data.get("id")
        try:
            memory_id = int(memory_id)
        except (TypeError, ValueError):
            self._send_json(400, {"error": "Identifiant invalide."})
            return
        result = self.app.delete_memory(memory_id, owner_user_id=session.user_id)
        status = 200 if result.get("deleted") else 400
        self._send_json(status, result)


class MilesWebServer:
    """Serveur web MILES, strictement local (127.0.0.1 uniquement).

    L'adresse d'écoute est imposée par le code et n'est pas configurable.
    Toute tentative de démarrage sur une adresse non locale est refusée
    explicitement, que ce soit via le constructeur ou via une affectation
    directe de l'attribut `host`.
    """

    #: Adresse d'écoute autorisée.
    ALLOWED_HOST = LOCAL_ONLY_HOST

    def __init__(
        self,
        app: WebApp,
        host: str = LOCAL_ONLY_HOST,
        port: int = 8080,
    ) -> None:
        self.app = app
        # Passe par la propriété de validation : toute adresse non locale
        # est refusée dès la construction.
        self.host = host
        self.port = port
        self._server: Optional[ThreadingHTTPServer] = None

    @property
    def host(self) -> str:
        """Adresse d'écoute du serveur (toujours locale)."""
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        self._host = assert_local_host(value)

    def start(self) -> None:
        # Revalidation avant toute liaison : `host` est un attribut public,
        # il pourrait avoir été modifié par affectation directe.
        host = assert_local_host(self.host)
        MilesHandler.app = self.app
        self._server = ThreadingHTTPServer((host, self.port), MilesHandler)
        print(f"Interface web MILES sur http://{host}:{self.port}")
        self._server.serve_forever()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
