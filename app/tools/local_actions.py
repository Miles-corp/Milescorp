"""Outil MILES : actions locales en lecture seule.

Ce module expose des **fonctions de niveau module** : le moteur d'outils
exécute les handlers dans un sous-processus (arrêt effectif garanti en cas
de dépassement de délai), ce qui impose que le handler soit picklable.
Une closure ou une méthode liée ne conviendrait pas.

Les chemins sont confinés aux racines autorisées (répertoire du projet et
dossier ``data/``) via :mod:`app.security.paths`.
"""

from __future__ import annotations

import datetime
import os

from app.security.paths import PathSecurityError, resolve_authorized_path


def datetime_handler() -> str:
    """Retourner la date et l'heure locales (aucun effet de bord)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def workdir_handler() -> str:
    """Retourner le répertoire de travail courant (aucun effet de bord)."""
    return os.getcwd()


def list_files_handler(path: str = ".") -> str:
    """Lister les fichiers d'un répertoire autorisé.

    Le chemin est résolu canoniquement et confiné aux racines autorisées :
    un lien symbolique pointant hors racines est refusé.

    Args:
        path: répertoire à lister, relatif à la racine du projet.

    Raises:
        PathSecurityError: si le chemin sort des racines autorisées.
    """
    try:
        target = resolve_authorized_path(path)
    except PathSecurityError as exc:
        raise PermissionError(str(exc)) from exc

    if not os.path.isdir(target):
        return f"Répertoire introuvable ou non lisible : {path}"

    entries = sorted(os.listdir(target))
    return "\n".join(entries) if entries else "(répertoire vide)"
