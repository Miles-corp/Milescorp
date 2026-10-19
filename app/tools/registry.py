"""Registre central des outils autorisés de MILES.

Définit et stocke les outils que le modèle peut demander.
Chaque outil déclare son interface, son niveau de risque, ses permissions
requises et son délai maximal. Aucun outil n'est exécutable s'il n'est pas
enregistré ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ToolParameter:
    """Déclaration d'un paramètre d'outil.

    Sert à valider les arguments fournis par le modèle avant exécution.
    """

    name: str
    type: type
    required: bool = True
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[tuple] = None


@dataclass(frozen=True)
class ToolDefinition:
    """Définition d'un outil autorisé.

    Attributs :
        tool_id : identifiant unique de l'outil.
        description : description lisible pour l'humain.
        handler : fonction Python qui implémente l'outil.
        parameters : paramètres attendus et leurs contraintes.
        risk_level : "LOW", "MEDIUM" ou "HIGH".
        required_permissions : permissions nécessaires pour exécuter l'outil.
        timeout_seconds : délai maximal d'exécution en secondes.
    """

    tool_id: str
    description: str
    handler: Callable[..., Any]
    parameters: tuple[ToolParameter, ...] = ()
    risk_level: str = "LOW"
    required_permissions: tuple[str, ...] = ()
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.risk_level not in ("LOW", "MEDIUM", "HIGH"):
            raise ValueError(f"Niveau de risque invalide : {self.risk_level!r}")


class ToolRegistry:
    """Registre central des outils autorisés.

    Seuls les outils enregistrés ici peuvent être demandés par le modèle.
    L'enregistrement est effectué par l'application, jamais par le modèle.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Enregistrer un outil dans le registre."""
        self._tools[tool.tool_id] = tool

    def get_tool(self, tool_id: str) -> Optional[ToolDefinition]:
        """Retourner la définition d'un outil, ou None s'il n'existe pas."""
        return self._tools.get(tool_id)

    def list_tools(self) -> list[str]:
        """Retourner la liste triée des identifiants d'outils enregistrés."""
        return sorted(self._tools.keys())

    def is_registered(self, tool_id: str) -> bool:
        """Vérifier qu'un outil est enregistré."""
        return tool_id in self._tools

    def unregister(self, tool_id: str) -> bool:
        """Retirer un outil du registre. Retourner True si retiré."""
        if tool_id in self._tools:
            del self._tools[tool_id]
            return True
        return False
