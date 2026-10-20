"""Registre par défaut des outils MILES.

Alimente :class:`~app.tools.registry.ToolRegistry` avec les seuls outils
réellement implémentés. Aucun outil fictif n'est déclaré.

Les outils enregistrés :

===========================  ========  =========================================
Identifiant                  Risque    Rôle
===========================  ========  =========================================
``status_read``              LOW       Référence d'état du moteur d'outils
``action_datetime``          LOW       Date et heure locales
``action_workdir``           LOW       Répertoire de travail courant
``action_list_files``        MEDIUM    Liste d'un répertoire autorisé (disque)
===========================  ========  =========================================

``action_list_files`` est classé MEDIUM car il accède au système de
fichiers : une confirmation humaine explicite est donc exigée.
"""

from __future__ import annotations

from app.tools.local_actions import (
    datetime_handler,
    list_files_handler,
    workdir_handler,
)
from app.tools.registry import ToolDefinition, ToolParameter, ToolRegistry
from app.tools.status_tool import status_tool_handler


def build_default_registry() -> ToolRegistry:
    """Construire le registre des outils disponibles dans MILES."""
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            tool_id="status_read",
            description=(
                "Consulter l'état de référence statique du moteur d'outils. "
                "Ces valeurs sont fixes : elles ne reflètent pas l'état en "
                "direct de l'instance en cours d'exécution."
            ),
            handler=status_tool_handler,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=5,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="action_datetime",
            description="Afficher la date et l'heure locales.",
            handler=datetime_handler,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=5,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="action_workdir",
            description="Afficher le répertoire de travail courant.",
            handler=workdir_handler,
            parameters=(),
            risk_level="LOW",
            required_permissions=(),
            timeout_seconds=5,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="action_list_files",
            description=(
                "Lister les fichiers d'un répertoire autorisé "
                "(racine du projet ou dossier data/)."
            ),
            handler=list_files_handler,
            parameters=(
                ToolParameter(
                    name="path",
                    type=str,
                    required=False,
                    description="Répertoire à lister, relatif à la racine du projet.",
                ),
            ),
            risk_level="MEDIUM",
            required_permissions=("lecture_systeme",),
            timeout_seconds=10,
        )
    )

    return registry


#: Permissions connues du modèle d'outils.
KNOWN_PERMISSIONS = ("lecture_systeme",)
