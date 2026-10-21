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

    Attributs :
        name : nom du paramètre.
        type : type Python attendu.
        required : le paramètre doit-il être fourni ?
        description : description lisible par l'humain.
        min_value, max_value : bornes numériques.
        allowed_values : ensemble des valeurs autorisées.
        is_path : le paramètre porte-t-il un CHEMIN de fichier ? La
            politique de sécurité lui applique alors un contrôle
            **structurel** (caractères de contrôle et métacaractères de
            commande) au lieu du contrôle par sous-chaîne réservé aux
            valeurs libres : un répertoire légitime dont le nom contient
            « source », « code » ou « script » est alors accepté par la
            politique. Cela n'ouvre aucun accès : le confinement des
            chemins (`app.security.paths`) reste la seule autorité sur les
            fichiers réellement accessibles.
    """

    name: str
    type: type
    required: bool = True
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[tuple] = None
    is_path: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    """Définition d'un outil autorisé.

    Attributs :
        tool_id : identifiant de l'outil.
        description : description lisible par l'humain.
        handler : fonction Python qui implémente l'outil.
        parameters : paramètres attendus et leurs contraintes.
        risk_level : "LOW", "MEDIUM" ou "HIGH".
        required_permissions : permissions nécessaires pour exécuter l'outil.
        timeout_seconds : délai maximal d'exécution en secondes.
        read_only : l'outil est-il déclaré **sans effet de bord** ? Un outil
            déclaré sans effet peut être rejoué après une interruption :
            l'absence d'effet précédent est alors démontrée par la
            déclaration elle-même (faire relire un fichier n'écrit rien).
            Un outil qui n'est pas déclaré sans effet n'est **jamais** rejoué
            automatiquement : une étape interrompue est marquée incertaine et
            exige une vérification explicite. La déclaration est posée par
            l'application, jamais par le modèle ; le défaut est « à effet ».
    """

    tool_id: str
    description: str
    handler: Callable[..., Any]
    parameters: tuple[ToolParameter, ...] = ()
    risk_level: str = "LOW"
    required_permissions: tuple[str, ...] = ()
    timeout_seconds: int = 30
    read_only: bool = False

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
