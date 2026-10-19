"""Moteur de décision pour l'exécution d'outils MILES.

Valide, autorise et exécute les outils demandés par le modèle, avec des
contrôles de sécurité stricts :

- Vérifie que l'outil existe et est enregistré.
- Valide strictement les paramètres (types, contraintes, absence de
  paramètres supplémentaires non déclarés).
- Vérifie les permissions requises.
- Exige une confirmation humaine explicite pour les outils MEDIUM/HIGH.
- Exécute avec un délai maximal (timeout).
- Journalise chaque demande (outil, décision, résultat).
- Aucun shell arbitraire, aucun eval()/exec() de code généré.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from app.tools.audit import AuditLogger
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolRegistry


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
    """Demande de confirmation en attente pour un outil risqué."""

    tool_id: str
    parameters_hash: str
    token: str


class ToolEngine:
    """Moteur de décision et d'exécution des outils.

    Attributs :
        registry : registre des outils autorisés.
        policy : politique de sécurité.
        audit : journal d'audit.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        audit: AuditLogger,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._audit = audit
        self._pending_confirmations: Dict[str, _PendingConfirmation] = {}

    # --- Interface publique ---

    def request_tool(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        user_confirmed: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> ToolResult:
        """Demander l'exécution d'un outil avec validation complète.

        Args :
            tool_id : identifiant de l'outil demandé.
            parameters : paramètres fournis par le modèle.
            user_confirmed : indication que l'utilisateur a confirmé
                (seulement valide avec confirmation_token).
            confirmation_token : jeton généré précédemment par ce moteur.

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

        # 2. Rejeter tout paramètre supplémentaire non déclaré
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

        # 3. Valider les paramètres déclarés
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

        # 4. Vérifier les permissions requises
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

        # 5. Gérer la confirmation pour outils risqués
        params_hash = self._hash_parameters(parameters)

        if self._policy.requires_human_confirmation(tool.risk_level):
            # Vérifier si une confirmation valide existe déjà pour ce tool
            # et ces paramètres exacts.
            pending = self._find_pending_confirmation(
                tool_id, params_hash, confirmation_token
            )
            if pending is None or not user_confirmed:
                # Générer un nouveau token de confirmation
                token = self._create_pending_confirmation(tool_id, params_hash)
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
            # Confirmation valide : consommer le token
            self._pending_confirmations.pop(pending.token, None)

        # 6. Exécuter l'outil avec timeout
        result = self._execute_tool(tool, parameters)

        # 7. Consigner le résultat
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
        """Exécuter l'outil avec un délai maximal.

        L'exécution se fait dans un thread séparé pour permettre l'interruption
        en cas de dépassement de délai. Aucun shell arbitraire n'est utilisé.
        """
        result_container: Dict[str, Any] = {}
        error_container: Dict[str, Optional[Exception]] = {}

        def _target() -> None:
            try:
                result_container["value"] = tool.handler(**parameters)
            except Exception as exc:  # noqa: BLE001
                error_container["error"] = exc

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=tool.timeout_seconds)

        if thread.is_alive():
            # Le thread est toujours en cours : dépassement de délai
            return ToolResult(
                tool_id=tool.tool_id,
                success=False,
                error_message=(
                    f"Délai d'attente dépassé ({tool.timeout_seconds}s)"
                ),
            )

        if "error" in error_container:
            exc = error_container["error"]
            return ToolResult(
                tool_id=tool.tool_id,
                success=False,
                error_message=f"Erreur d'exécution : {exc}",
            )

        return ToolResult(
            tool_id=tool.tool_id,
            success=True,
            data=result_container.get("value"),
        )

    def _hash_parameters(self, parameters: Dict[str, Any]) -> str:
        """Calculer une empreinte déterministe des paramètres."""
        serializable = json.dumps(
            parameters, sort_keys=True, default=str
        )
        return hashlib.sha256(serializable.encode("utf-8")).hexdigest()

    def _create_pending_confirmation(
        self, tool_id: str, parameters_hash: str
    ) -> str:
        """Créer une demande de confirmation en attente."""
        token = uuid.uuid4().hex
        self._pending_confirmations[token] = _PendingConfirmation(
            tool_id=tool_id,
            parameters_hash=parameters_hash,
            token=token,
        )
        return token

    def _find_pending_confirmation(
        self,
        tool_id: str,
        parameters_hash: str,
        confirmation_token: Optional[str],
    ) -> Optional[_PendingConfirmation]:
        """Vérifier si un token de confirmation correspond à la demande."""
        if confirmation_token is None:
            return None
        pending = self._pending_confirmations.get(confirmation_token)
        if pending is None:
            return None
        if pending.tool_id != tool_id:
            return None
        if pending.parameters_hash != parameters_hash:
            return None
        return pending

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
        """Enregistrer une entrée d'audit."""
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
