"""Registre et validation des actions locales autorisées.

Seules les actions explicitement enregistrées peuvent être exécutées.
Le modèle propose une action structurée ; le programme vérifie l'autorisation
avant toute exécution. Aucun accès shell arbitraire n'est possible.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    allowed: bool
    reason: str = ""
    output: str | None = None
    error: str | None = None


class ActionValidator:
    """Valide et exécute les actions locales autorisées."""

    def __init__(self, allowed_actions: list[str] | None = None) -> None:
        self._allowed = set(allowed_actions or ["datetime", "workdir", "list_files"])
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
        """Lister les fichiers d'un répertoire autorisé (sous-répertoires du CWD uniquement)."""
        # Empêcher les traversées de répertoires
        target = os.path.abspath(path)
        cwd = os.path.abspath(os.getcwd())
        if not target.startswith(cwd + os.sep) and target != cwd:
            return "Accès refusé : le répertoire demandé est en dehors du répertoire de travail."
        if not os.path.isdir(target):
            return f"Le répertoire '{path}' n'existe pas ou n'est pas un répertoire."
        entries = sorted(os.listdir(target))
        return "\n".join(entries) if entries else "(répertoire vide)"
