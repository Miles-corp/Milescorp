"""Actions locales autorisées pour l'ordinateur.

Ces actions sont exposées via ActionValidator et peuvent être proposées par
le modèle IA, puis validées avant exécution.
"""

from __future__ import annotations

import datetime
import os
from typing import Any


class ComputerActions:
    """Ensemble d'actions locales sûres."""

    def get_datetime(self, **kwargs: Any) -> str:
        del kwargs  # non utilisé
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_workdir(self, **kwargs: Any) -> str:
        del kwargs
        return os.getcwd()

    def list_files(self, path: str = ".", **kwargs: Any) -> str:
        del kwargs
        target = os.path.abspath(path)
        cwd = os.path.abspath(os.getcwd())
        if not target.startswith(cwd + os.sep) and target != cwd:
            return "Accès refusé : répertoire en dehors du répertoire de travail."
        if not os.path.isdir(target):
            return f"Le répertoire '{path}' n'existe pas."
        entries = sorted(os.listdir(target))
        return "\n".join(entries) if entries else "(répertoire vide)"
