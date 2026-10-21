"""Moteur de décision pour l'exécution d'outils MILES.

Valide, autorise et exécute les outils demandés par le modèle, avec des
contrôles de sécurité stricts :

- Vérifie que l'outil existe et est enregistré.
- Valide strictement les paramètres (types, contraintes, absence de
  paramètres supplémentaires non déclarés).
- Applique la politique de sécurité (pas de shell, pas de code généré,
  pas d'accès aux secrets).
- Vérifie les permissions requises.
- Exige une confirmation humaine explicite pour les outils MEDIUM/HIGH,
  avec expiration des jetons.
- Exécute avec un délai maximal (timeout) et arrêt effectif du processus.
- Journalise chaque demande (outil, décision, résultat) sans exposer
  de secrets ni d'exceptions brutes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing
import queue
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from app.tools.audit import AuditLogger
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolRegistry

logger = logging.getLogger("miles.tools")
if not logger.handlers:
    # Handler neutre : l'application reste libre de configurer la
    # journalisation. N'écrit rien sur stderr par défaut.
    logger.addHandler(logging.NullHandler())


@dataclass
class ToolResult:
    """Résultat d'une demande d'outil.

    Attributs :
        tool_id : identifiant de l'outil demandé.
        success : True si l'outil a été exécuté avec succès.
        data : données retournées par l'outil (si succès).
        error_message : message d'erreur (si échec ou refus).
        confirmation_required : True si une confirmation humaine est requise.
        confirmation_token : jeton de confirmation à représenter pour
            confirmer la demande.
        execution_time_ms : durée d'exécution en millisecondes.
    """

    tool_id: str
    success: bool
    data: Any = None
    error_message: str = ""
    confirmation_required: bool = False
    confirmation_token: str = ""
    execution_time_ms: float = 0.0


@dataclass
class _PendingConfirmation:
    """Demande de confirmation en attente pour un outil risqué.

    Attributs :
        tool_id : identifiant de l'outil.
        parameters_hash : empreinte des paramètres exacts.
        token : jeton de confirmation.
        expires_at : instant d'expiration (secondes depuis l'époque).
        context_id : contexte de mission du jeton (vide si non applicable).
        actor_id : identité de session ayant demandé la confirmation.
    """

    tool_id: str
    parameters_hash: str
    token: str
    expires_at: float
    context_id: str = ""
    actor_id: str = ""


def _select_start_context() -> Any:
    """Choisir explicitement le contexte de démarrage des sous-processus.

    Le contexte par défaut de ``multiprocessing`` est ``fork`` sous Linux :
    dans un processus multi-thread (le serveur web est un
    ``ThreadingHTTPServer``), ``fork`` provoke un ``DeprecationWarning`` et
    peut provoquer des interblocages dans l'enfant. Python 3.14 changera de
    toute façon ce défaut.

    On impose donc :
    - ``forkserver`` quand il est disponible (Linux, macOS) ;
    - ``spawn`` sinon (Windows).

    Les handlers doivent rester picklables : c'est déjà une contrainte du
    moteur (voir :func:`_run_handler_in_process`).
    """
    try:
        methods = multiprocessing.get_all_start_methods()
    except Exception:  # noqa: BLE001 — repli sur le contexte par défaut
        return multiprocessing
    for method in ("forkserver", "spawn"):
        if method in methods:
            return multiprocessing.get_context(method)
    return multiprocessing


#: Contexte multiprocessing utilisé par le moteur (explicite et stable).
_MP_CONTEXT = _select_start_context()


def _make_queue() -> "multiprocessing.Queue[Any]":
    """Créer une file de résultat dans le contexte multiprocessing du moteur.

    Point d'entrée unique (et point de substitution pour les tests de
    non-régression sur la fermeture des files) : la file et le processus
    enfant doivent impérativement appartenir au même contexte.
    """
    return _MP_CONTEXT.Queue()


def _run_handler_in_process(
    handler: Callable[..., Any],
    parameters: Dict[str, Any],
    result_queue: "multiprocessing.Queue[Any]",
    error_queue: "multiprocessing.Queue[str]",
) -> None:
    """Exécuter un handler dans un processus séparé.

    Cette fonction est définie au niveau du module pour pouvoir être
    sérialisée par multiprocessing sur Windows (spawn).
    """
    try:
        result = handler(**parameters)
        result_queue.put(("ok", result))
    except Exception as exc:  # noqa: BLE001
        error_queue.put(("error", str(exc)))


class ToolEngine:
    """Moteur de décision et d'exécution des outils.

    Attributs :
        registry : registre des outils autorisés.
        policy : politique de sécurité.
        audit : journal d'audit.
        _clock : fonction retournant le temps actuel (secondes depuis
            l'époque). Utilisée pour les tests d'expiration.
        _confirmation_ttl_seconds : durée de validité d'un jeton de
            confirmation (défaut : 300 secondes = 5 minutes).
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        audit: AuditLogger,
        *,
        clock: Callable[[], float] = time.time,
        confirmation_ttl_seconds: float = 300.0,
        grant_checker: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit = audit
        self._clock = clock
        self._confirmation_ttl_seconds = confirmation_ttl_seconds
        self._pending_confirmations: Dict[str, _PendingConfirmation] = {}
        # Vérificateur d'autorisations (grants) liés à une session et à une
        # mission. Le moteur ne connaît que le contrat minimal : il ne
        # dépend d'aucun module d'orchestration.
        self._grant_checker = grant_checker

    def set_grant_checker(self, grant_checker: Optional[Any]) -> None:
        """Brancher (ou retirer) le vérificateur d'autorisations."""
        self._grant_checker = grant_checker

    # --- Interface publique ---

    def request_tool(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        user_confirmed: bool = False,
        confirmation_token: Optional[str] = None,
        context_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> ToolResult:
        """Demander l'exécution d'un outil avec validation complète.

        Args :
            tool_id : identifiant de l'outil demandé.
            parameters : paramètres fournis par le modèle.
            user_confirmed : indication que l'utilisateur a confirmé
                (seulement valide avec confirmation_token).
            confirmation_token : jeton généré précédemment par ce moteur.
            context_id : contexte de la demande (mission). Le jeton de
                confirmation n'est valable que dans ce contexte.
            actor_id : identité de session de l'acteur. Le jeton de
                confirmation n'est valable que pour cette session.

        Retourne :
            ToolResult contenant le résultat ou la demande de confirmation.
        """
        start_time = time.time()

        # 1. Vérifier que l'outil existe
        tool = self._registry.get_tool(tool_id)
        if tool is None:
            self._record(
                tool_id,
                user_confirmed,
                False,
                "refused",
                f"Outil inconnu : {tool_id}",
                parameters,
            )
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error_message=f"Outil inconnu : {tool_id}",
            )

        # 2. Appliquer la politique de sécurité sur les paramètres
        #
        # Les paramètres déclarés comme CHEMINS par le schéma de l'outil
        # sont validés structurellement par la politique (caractères de
        # contrôle et métacaractères) au lieu du contrôle par sous-chaîne
        # réservé aux valeurs libres : un répertoire légitime dont le nom
        # contient « source » ou « code » n'est ainsi pas refusé à tort.
        # Le type est déclaré par l'application, jamais par le modèle ; le
        # confinement des chemins (`app.security.paths`) reste l'unique
        # autorité sur les fichiers réellement accessibles.
        path_parameters = {
            param.name for param in tool.parameters if param.is_path
        }
        try:
            self._policy.validate_no_shell_access(
                parameters, path_parameters=path_parameters
            )
            self._policy.validate_no_code_execution(
                parameters, path_parameters=path_parameters
            )
            self._policy.validate_no_secret_access(
                parameters, path_parameters=path_parameters
            )
        except PermissionError as exc:
            params_hash = self._hash_parameters(parameters)
            self._record(
                tool_id,
                user_confirmed,
                False,
                "refused",
                "Refus de sécurité : action non autorisée.",
                parameters,
                params_hash,
            )
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error_message="Action refusée par la politique de sécurité.",
            )

        # 3. Rejeter tout paramètre supplémentaire non déclaré
        declared_params = {p.name for p in tool.parameters}
        extra_params = set(parameters.keys()) - declared_params
        if extra_params:
            params_hash = self._hash_parameters(parameters)
            self._record(
                tool_id,
                user_confirmed,
                False,
                "refused",
                f"Paramètres supplémentaires non déclarés : {sorted(extra_params)}",
                parameters,
                params_hash,
            )
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error_message=(
                    f"Paramètres supplémentaires non autorisés : "
                    f"{sorted(extra_params)}"
                ),
            )

        # 4. Valider les paramètres déclarés
        param_errors = self._validate_parameters(tool, parameters)
        if param_errors:
            params_hash = self._hash_parameters(parameters)
            self._record(
                tool_id,
                user_confirmed,
                False,
                "refused",
                "; ".join(param_errors),
                parameters,
                params_hash,
            )
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error_message="; ".join(param_errors),
            )

        # 5. Vérifier les permissions requises
        if not self._policy.has_all_permissions(tool.required_permissions):
            missing = [
                p for p in tool.required_permissions
                if not self._policy.has_permission(p)
            ]
            params_hash = self._hash_parameters(parameters)
            self._record(
                tool_id,
                user_confirmed,
                False,
                "refused",
                f"Permissions manquantes : {missing}",
                parameters,
                params_hash,
            )
            return ToolResult(
                tool_id=tool_id,
                success=False,
                error_message=f"Permissions manquantes : {missing}",
            )

        # 6. Gérer la confirmation pour outils risqués
        params_hash = self._hash_parameters(parameters)

        if self._policy.requires_human_confirmation(tool.risk_level):
            pending = self._find_pending_confirmation(
                tool_id, params_hash, confirmation_token, context_id, actor_id
            )
            if pending is None or not user_confirmed:
                # Voie 1 : une autorisation liée à la session et à la mission
                # a déjà été accordée par l'utilisateur. Elle remplace la
                # confirmation interactive, sans jamais contourner la
                # politique de sécurité ni les permissions.
                grant_id = self._authorized_grant_id(
                    tool_id, parameters, context_id, actor_id
                )
                if grant_id is not None:
                    self._grant_checker.consume(grant_id)
                    self._audit.record(
                        tool_id=tool_id,
                        user_confirmed=True,
                        permission_granted=True,
                        result="authorized",
                        error_message="Autorisation liée à la session et à la mission",
                        parameters_hash=params_hash,
                    )
                    if pending is not None:
                        self._pending_confirmations.pop(pending.token, None)
                else:
                    # Voie 2 : demande de confirmation interactive.
                    token = self._create_pending_confirmation(
                        tool_id, params_hash, context_id, actor_id
                    )
                    self._audit.record(
                        tool_id=tool_id,
                        user_confirmed=user_confirmed,
                        permission_granted=True,
                        result="confirmation_required",
                        error_message="Confirmation humaine requise",
                        parameters_hash=params_hash,
                    )
                    return ToolResult(
                        tool_id=tool_id,
                        success=False,
                        confirmation_required=True,
                        confirmation_token=token,
                        error_message=(
                            "Confirmation humaine requise pour cet outil. "
                            "Utilisez le jeton de confirmation retourné."
                        ),
                    )
            else:
                # Confirmation valide : consommer le token
                self._pending_confirmations.pop(pending.token, None)

        # 7. Exécuter l'outil avec timeout et arrêt effectif
        result = self._execute_tool(tool, parameters)

        # 8. Consigner le résultat (sans exposer de secrets)
        self._record(
            tool_id,
            user_confirmed,
            True,
            "success" if result.success else "error",
            result.error_message,
            parameters,
            params_hash,
        )

        execution_time_ms = (time.time() - start_time) * 1000.0
        result.execution_time_ms = execution_time_ms
        return result

    # --- Méthodes internes ---

    def _validate_parameters(
        self, tool: ToolDefinition, parameters: Dict[str, Any]
    ) -> list[str]:
        """Valider les paramètres contre la définition de l'outil.

        Retourne une liste de messages d'erreur (vide si valide).
        """
        errors: list[str] = []
        declared = {p.name: p for p in tool.parameters}

        # Vérifier les paramètres requis manquants
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                errors.append(f"Paramètre requis manquant : {param.name}")
                continue

        # Valider les paramètres fournis
        for name, value in parameters.items():
            if name not in declared:
                continue  # déjà rejeté plus haut
            param = declared[name]

            # Vérification de type
            if not isinstance(value, param.type):
                errors.append(
                    f"Paramètre '{param.name}' doit être de type "
                    f"{param.type.__name__}, reçu {type(value).__name__}"
                )
                continue

            # Vérification des contraintes numériques
            if isinstance(value, (int, float)):
                if (
                    param.min_value is not None
                    and value < param.min_value
                ):
                    errors.append(
                        f"Paramètre '{param.name}' doit être >= {param.min_value}"
                    )
                if (
                    param.max_value is not None
                    and value > param.max_value
                ):
                    errors.append(
                        f"Paramètre '{param.name}' doit être <= {param.max_value}"
                    )

            # Vérification des valeurs autorisées
            if (
                param.allowed_values is not None
                and value not in param.allowed_values
            ):
                errors.append(
                    f"Paramètre '{param.name}' doit être dans {param.allowed_values}"
                )

        return errors

    def _execute_tool(
        self,
        tool: ToolDefinition,
        parameters: Dict[str, Any],
    ) -> ToolResult:
        """Exécuter l'outil avec un délai maximal et arrêt effectif.

        L'exécution se fait dans un processus séparé (multiprocessing)
        pour permettre un arrêt effectif en cas de dépassement de délai.
        Aucun shell arbitraire n'est utilisé.

        Les files de résultat et d'erreur sont systématiquement fermées,
        y compris sur les chemins d'erreur et de dépassement de délai, afin
        de ne pas laisser de descripteurs de fichiers ni de threads
        derrière soi.
        """
        result_queue: "multiprocessing.Queue[Any]" = _make_queue()
        error_queue: "multiprocessing.Queue[str]" = _make_queue()

        try:
            process = _MP_CONTEXT.Process(
                target=_run_handler_in_process,
                args=(tool.handler, parameters, result_queue, error_queue),
                daemon=True,
            )
            process.start()

            # Le résultat est récupéré PENDANT l'exécution du processus
            # enfant, et non après : le tampon d'un tube fait 8 Kio sous
            # Windows. Un résultat plus volumineux que ce tampon bloquerait
            # l'enfant (qui attend l'écriture dans le tube) pendant que le
            # parent attend la fin du processus : le délai d'attente
            # expirerait à tort. Le parent doit donc consommer la file en
            # continu.
            deadline = time.monotonic() + tool.timeout_seconds
            outcome: Optional[tuple] = None
            timed_out = False

            while True:
                try:
                    outcome = result_queue.get(timeout=0.05)
                    break
                except queue.Empty:
                    pass
                try:
                    outcome = error_queue.get(timeout=0.01)
                    break
                except queue.Empty:
                    pass
                if not process.is_alive():
                    # Le processus est terminé : dernière lecture possible
                    # (les données peuvent être encore en transit).
                    try:
                        outcome = result_queue.get(timeout=0.2)
                    except queue.Empty:
                        try:
                            outcome = error_queue.get(timeout=0.1)
                        except queue.Empty:
                            outcome = None
                    break
                if time.monotonic() >= deadline:
                    timed_out = True
                    break

            if timed_out:
                # Arrêt effectif du processus enfant (invariant S-006).
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    # Récolter le processus tué : pas de processus zombie.
                    process.join(timeout=5)
                return ToolResult(
                    tool_id=tool.tool_id,
                    success=False,
                    error_message=(
                        f"Délai d'attente dépassé ({tool.timeout_seconds}s). "
                        "Exécution arrêtée."
                    ),
                )

            # Le processus a produit son résultat : on le recueille.
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)

            if outcome is not None:
                kind, value = outcome
                if kind == "ok":
                    return ToolResult(
                        tool_id=tool.tool_id,
                        success=True,
                        data=value,
                    )
                # Erreur levée par le handler : message générique, jamais
                # l'exception brute.
                return ToolResult(
                    tool_id=tool.tool_id,
                    success=False,
                    error_message="Erreur d'exécution.",
                )

            return ToolResult(
                tool_id=tool.tool_id,
                success=False,
                error_message="Erreur interne lors de l'exécution.",
            )
        finally:
            # Les files sont fermées dans tous les cas (succès, erreur,
            # dépassement de délai).
            self._close_queues(result_queue, error_queue)

    @staticmethod
    def _close_queues(*queues: "multiprocessing.Queue[Any]") -> None:
        """Fermer les files de résultat et d'erreur.

        `cancel_join_thread()` est appelé avant `close()` : si le processus
        enfant a été tué en cours d'écriture, la fermeture ne doit pas
        bloquer sur le thread d'alimentation de la file.
        """
        for queue in queues:
            try:
                queue.cancel_join_thread()
            except Exception as exc:  # noqa: BLE001 — fermeture best-effort
                logger.warning("Annulation de jointure de file impossible : %s", exc)
            try:
                queue.close()
            except Exception as exc:  # noqa: BLE001 — fermeture best-effort
                logger.warning("Fermeture de file impossible : %s", exc)

    def _hash_parameters(self, parameters: Dict[str, Any]) -> str:
        """Calculer une empreinte déterministe des paramètres."""
        serializable = json.dumps(
            parameters, sort_keys=True, default=str
        )
        return hashlib.sha256(serializable.encode("utf-8")).hexdigest()

    def _create_pending_confirmation(
        self,
        tool_id: str,
        parameters_hash: str,
        context_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> str:
        """Créer une demande de confirmation en attente.

        Le jeton est lié au contexte (mission) et à l'identité de session :
        il ne peut pas être rejoué dans un autre contexte.
        """
        token = uuid.uuid4().hex
        expires_at = self._clock() + self._confirmation_ttl_seconds
        self._pending_confirmations[token] = _PendingConfirmation(
            tool_id=tool_id,
            parameters_hash=parameters_hash,
            token=token,
            expires_at=expires_at,
            context_id=str(context_id or ""),
            actor_id=str(actor_id or ""),
        )
        return token

    def _find_pending_confirmation(
        self,
        tool_id: str,
        parameters_hash: str,
        confirmation_token: Optional[str],
        context_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> Optional[_PendingConfirmation]:
        """Vérifier si un token de confirmation correspond à la demande.

        Le jeton doit correspondre à l'outil, aux paramètres exacts, au
        contexte de mission **et** à l'identité de session. Un jeton émis
        dans un autre contexte n'est jamais accepté (échec fermé).
        """
        if confirmation_token is None:
            return None
        pending = self._pending_confirmations.get(confirmation_token)
        if pending is None:
            return None
        if pending.tool_id != tool_id:
            return None
        if pending.parameters_hash != parameters_hash:
            return None
        if pending.context_id != str(context_id or ""):
            return None
        if pending.actor_id != str(actor_id or ""):
            return None
        if self._clock() > pending.expires_at:
            # Jeton expiré : le supprimer et refuser
            del self._pending_confirmations[pending.token]
            return None
        return pending

    def _authorized_grant_id(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        context_id: Optional[str],
        actor_id: Optional[str],
    ) -> Optional[str]:
        """Retourner l'identifiant d'un grant couvrant la demande, ou None."""
        if self._grant_checker is None:
            return None
        try:
            grant_id = self._grant_checker.authorize(
                tool_id, parameters, context_id, actor_id
            )
        except Exception:  # noqa: BLE001 — un grant invalide ne vaut pas autorisation
            logger.warning(
                "Verificateur d'autorisations indisponible : requete refusee."
            )
            return None
        if not grant_id:
            return None
        return str(grant_id)

    def _record(
        self,
        tool_id: str,
        user_confirmed: bool,
        permission_granted: bool,
        result: str,
        error_message: str,
        parameters: Optional[Dict[str, Any]] = None,
        parameters_hash: Optional[str] = None,
    ) -> None:
        """Enregistrer une entrée d'audit sans exposer de secrets.

        Les exceptions brutes ne sont jamais journalisées : seul un message
        générique est enregistré.
        """
        if parameters_hash is None:
            parameters_hash = self._hash_parameters(parameters or {})
        self._audit.record(
            tool_id=tool_id,
            user_confirmed=user_confirmed,
            permission_granted=permission_granted,
            result=result,
            error_message=error_message,
            parameters_hash=parameters_hash,
        )
