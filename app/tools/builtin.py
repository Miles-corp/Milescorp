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
``action_read_file``         MEDIUM    Lecture bornée d'un fichier autorisé
===========================  ========  =========================================

``action_list_files`` et ``action_read_file`` sont classés MEDIUM car ils
accèdent au système de fichiers : une confirmation humaine explicite est
donc exigée. La permission requise est ``lecture_systeme`` : aucune
permission nouvelle n'est introduite.
"""

from __future__ import annotations

from app.tools.local_actions import (
    DEFAULT_MAX_READ_BYTES,
    HARD_MAX_READ_BYTES,
    MAX_LIST_DEPTH,
    datetime_handler,
    list_files_handler,
    read_file_handler,
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
                    is_path=True,
                ),
                ToolParameter(
                    name="depth",
                    type=int,
                    required=False,
                    description=(
                        "Profondeur de parcours (1 = le dossier seul, "
                        f"2 = un niveau de sous-dossiers, maximum {MAX_LIST_DEPTH})."
                    ),
                    min_value=1,
                    max_value=MAX_LIST_DEPTH,
                ),
            ),
            risk_level="MEDIUM",
            required_permissions=("lecture_systeme",),
            timeout_seconds=10,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="action_read_file",
            description=(
                "Lire le début d'un fichier texte autorisé. Les fichiers "
                "sensibles (.env, clés privées) sont refusés et la lecture "
                "est bornée."
            ),
            handler=read_file_handler,
            parameters=(
                ToolParameter(
                    name="path",
                    type=str,
                    required=True,
                    description="Fichier à lire, relatif à la racine du projet.",
                    is_path=True,
                ),
                ToolParameter(
                    name="max_bytes",
                    type=int,
                    required=False,
                    description=(
                        "Nombre maximal d'octets lus "
                        f"(entre 1024 et {HARD_MAX_READ_BYTES})."
                    ),
                    min_value=1024,
                    max_value=HARD_MAX_READ_BYTES,
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

#: Outils d'observation (lecture seule) utilisables par une mission.
READ_ONLY_TOOLS = (
    "status_read",
    "action_datetime",
    "action_workdir",
    "action_list_files",
    "action_read_file",
)

#: Taille de lecture par défaut (octets).
DEFAULT_READ_BYTES = DEFAULT_MAX_READ_BYTES
