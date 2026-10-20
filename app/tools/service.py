"""Service d'outils MILES : point d'entrée unique pour le CLI et l'interface web.

Ce module évite toute duplication de logique métier entre les deux
interfaces : le CLI et le web appellent **toujours** :class:`ToolService`,
qui délègue au moteur :class:`~app.tools.engine.ToolEngine`.

Aucune politique de sécurité n'est définie ici : les permissions accordées
sont fournies par l'application, jamais par le modèle.
"""

from __future__ import annotations

from typing import Any, Optional

from app.tools.audit import AuditLogger
from app.tools.builtin import build_default_registry
from app.tools.engine import ToolEngine, ToolResult
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolRegistry


class ToolService:
    """Facade commune du moteur d'outils.

    Attributs :
        registry : registre des outils autorisés.
        policy : politique de sécurité (permissions accordées par l'application).
        engine : moteur de décision et d'exécution.
        audit : journal d'audit.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        granted_permissions: Optional[set[str]] = None,
        confirmation_ttl_seconds: float = 300.0,
        grant_checker: Optional[Any] = None,
    ) -> None:
        self.registry = registry if registry is not None else build_default_registry()
        self.policy = ToolPolicy(
            granted_permissions if granted_permissions is not None else {"lecture_systeme"}
        )
        self.audit = AuditLogger()
        self.engine = ToolEngine(
            registry=self.registry,
            policy=self.policy,
            audit=self.audit,
            confirmation_ttl_seconds=confirmation_ttl_seconds,
            grant_checker=grant_checker,
        )

    # --- Découverte ---

    def list_tools(self) -> list[dict[str, Any]]:
        """Retourner le catalogue des outils enregistrés.

        Chaque entrée décrit l'outil sans exposer de donnée sensible :
        identifiant, description, niveau de risque, permissions requises et
        paramètres acceptés.
        """
        catalogue: list[dict[str, Any]] = []
        for tool_id in self.registry.list_tools():
            tool = self.registry.get_tool(tool_id)
            if tool is None:
                continue
            catalogue.append(
                {
                    "id": tool.tool_id,
                    "description": tool.description,
                    "risk_level": tool.risk_level,
                    "required_permissions": list(tool.required_permissions),
                    "requires_confirmation": tool.risk_level in ("MEDIUM", "HIGH"),
                    "parameters": [
                        {
                            "name": param.name,
                            "type": param.type.__name__,
                            "required": param.required,
                            "description": param.description,
                        }
                        for param in tool.parameters
                    ],
                }
            )
        return catalogue

    def has_tool(self, tool_id: str) -> bool:
        """Indiquer si un outil est enregistré."""
        return self.registry.is_registered(tool_id)

    # --- Invocation ---

    def request_tool(
        self,
        tool_id: str,
        parameters: Optional[dict[str, Any]] = None,
        user_confirmed: bool = False,
        confirmation_token: Optional[str] = None,
        context_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> ToolResult:
        """Demander l'exécution d'un outil.

        Toute la validation (existence, permissions, paramètres, politique,
        confirmation, délai) est réalisée par le moteur. Cette méthode est
        le seul point d'entrée : le CLI et l'interface web l'utilisent sans
        dupliquer la logique métier.

        Args:
            tool_id : outil demandé.
            parameters : paramètres de l'appel.
            user_confirmed : confirmation interactive déjà obtenue.
            confirmation_token : jeton de confirmation correspondant.
            context_id : contexte de la demande (mission) : le jeton de
                confirmation n'est valable que dans ce contexte.
            actor_id : identité de session : le jeton de confirmation n'est
                valable que pour cette session.
        """
        return self.engine.request_tool(
            tool_id=tool_id,
            parameters=parameters or {},
            user_confirmed=user_confirmed,
            confirmation_token=confirmation_token,
            context_id=context_id,
            actor_id=actor_id,
        )

    def describe_result(self, result: ToolResult) -> dict[str, Any]:
        """Convertir un résultat en charge utile JSON pour les interfaces.

        Ne contient aucun secret : le message d'erreur du moteur est déjà
        générique et expurgé.
        """
        payload: dict[str, Any] = {
            "tool_id": result.tool_id,
            "success": result.success,
        }
        if result.success:
            payload["result"] = result.data
        if result.error_message:
            payload["error"] = result.error_message
        if result.confirmation_required:
            payload["confirmation_required"] = True
            payload["confirmation_token"] = result.confirmation_token
        if result.execution_time_ms:
            payload["execution_time_ms"] = round(result.execution_time_ms, 2)
        return payload
