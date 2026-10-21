"""Registre et validation des actions locales autorisées.

Seules les actions explicitement enregistrées peuvent être exécutées.
Le modèle propose une action structurée ; le programme vérifie l'autorisation
avant toute exécution. Aucun accès shell arbitraire n'est possible.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.security.paths import (
    PathSecurityError,
    default_allowed_roots,
    resolve_authorized_path,
)


@dataclass
class ActionResult:
    allowed: bool
    reason: str = ""
    output: str | None = None
    error: str | None = None


class ActionValidator:
    """Valide et exécute les actions locales autorisées.

    Les opérations sur le système de fichiers sont confinées aux racines
    autorisées (par défaut : le répertoire du projet et son dossier de
    données ``data/``). Les chemins sont résolus de façon canonique, ce qui
    prend en compte les liens symboliques.
    """

    def __init__(
        self,
        allowed_actions: list[str] | None = None,
        allowed_roots: Optional[Iterable[str]] = None,
    ) -> None:
        self._allowed = set(allowed_actions or ["datetime", "workdir", "list_files"])
        self._allowed_roots: list[str] = list(
            allowed_roots if allowed_roots is not None
            else [str(root) for root in default_allowed_roots()]
        )
        self._registry: dict[str, Any] = {
            "datetime": self._action_datetime,
            "workdir": self._action_workdir,
            "list_files": self._action_list_files,
        }

    def is_allowed(self, action_name: str) -> bool:
        return action_name in self._allowed and action_name in self._registry

    def execute(self, action_name: str, arguments: dict[str, Any] | None = None) -> ActionResult:
        """Valider et exécuter une action si elle est autorisée."""
        args = arguments or {}

        if not action_name or not isinstance(action_name, str):
            return ActionResult(
                allowed=False,
                reason="Nom d'action invalide.",
            )

        if action_name not in self._allowed:
            return ActionResult(
                allowed=False,
                reason=f"Action '{action_name}' non autorisée.",
            )

        if action_name not in self._registry:
            return ActionResult(
                allowed=False,
                reason=f"Action '{action_name}' non implémentée.",
            )

        try:
            handler = self._registry[action_name]
            output = handler(**args)
            return ActionResult(allowed=True, output=str(output))
        except TypeError as exc:
            return ActionResult(
                allowed=True,
                error=f"Arguments invalides pour '{action_name}': {exc}",
            )
        except Exception as exc:  # noqa: BLE001 — ne pas exposer d'erreur système
            return ActionResult(
                allowed=True,
                error=f"Erreur lors de l'exécution de '{action_name}'.",
            )

    # --- Implémentations des actions autorisées ---

    def _action_datetime(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _action_workdir(self) -> str:
        return os.getcwd()

    def _action_list_files(self, path: str = ".") -> str:
        """Lister les fichiers d'un répertoire autorisé.

        Le chemin est résolu canoniquement (liens symboliques et `..`
        inclus) puis vérifié : tout répertoire hors des racines autorisées
        est refusé.
        """
        try:
            target = resolve_authorized_path(path, roots=self._allowed_roots)
        except PathSecurityError:
            return (
                "Accès refusé : le répertoire demandé est hors des racines "
                "autorisées."
            )
        if not os.path.isdir(target):
            return f"Le répertoire '{path}' n'existe pas ou n'est pas un répertoire."
        entries = sorted(os.listdir(target))
        return "\n".join(entries) if entries else "(répertoire vide)"
