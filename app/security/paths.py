"""Confinement des chemins de fichiers aux racines autorisées.

Les chemins sont résolus de façon **canonique** (`os.path.realpath`), ce qui
résout les liens symboliques : un lien symbolique pointant hors des racines
autorisées est donc refusé, là où une simple normalisation lexicale
(`os.path.abspath`) laisserait passer.

Racines autorisées par défaut :
- le répertoire du projet (celui qui contient le package ``app/``) ;
- le dossier de données ``data/`` du projet.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


class PathSecurityError(Exception):
    """Chemin résolu hors des racines autorisées."""


def project_root() -> Path:
    """Retourner le répertoire racine du projet.

    Déduit de l'emplacement de ce module : ``app/security/paths.py`` ->
    ``app/security`` -> ``app`` -> racine du projet.
    """
    return Path(__file__).resolve().parent.parent.parent


def default_allowed_roots() -> list[Path]:
    """Retourner les racines autorisées par défaut.

    Le répertoire du projet et son dossier de données ``data/``.
    """
    root = project_root()
    return [root, root / "data"]


def canonical_path(
    path: str | os.PathLike[str],
    base: Optional[Path] = None,
) -> Path:
    """Résoudre un chemin de façon canonique.

    Un chemin relatif est résolu par rapport à ``base`` (par défaut la racine
    du projet). La résolution canonique résout les liens symboliques et les
    jonctions, et normalise les segments ``..``.
    """
    raw = os.fspath(path)
    # Sur une plateforme non-Windows, un chemin de type "C:/..." est un
    # chemin Windows absolu : il ne doit JAMAIS etre resolu comme un chemin
    # relatif sous la racine du projet (contournement de confinement --
    # diagnostic Agent B 2026-10-25). On le refuse explicitement.
    # La recherche utilise une regex pour couvrir les contournements par
    # espacement (espace/tab avant le chemin, espace avant le slash ou
    # les deux-points) identifies par l'audit B.
    if os.name != "nt":
        import re as _re
        # Couvrir aussi les contournements par espacement identifies par
        # l'audit B : " C:/...", "\tC:/...", "C: /...", "C :/...".
        if _re.search(r"[A-Za-z]\s*:\s*[\\/]", raw.strip()):
            raise PathSecurityError(
                "Chemin Windows absolu refuse sur cette plateforme : " + repr(raw)
            )
    if not os.path.isabs(raw):
        raw = os.path.join(os.fspath(base if base is not None else project_root()), raw)
    return Path(os.path.realpath(os.path.abspath(raw)))


def is_within(path: Path, root: Path) -> bool:
    """Vérifier qu'un chemin canonique se trouve dans une racine canonique.

    Utilise `relative_to` et non une comparaison de préfixe : `/data-secret`
    ne doit pas être considéré comme contenu dans `/data`.
    """
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_authorized_path(
    path: str | os.PathLike[str],
    roots: Optional[Iterable[str | os.PathLike[str]]] = None,
    base: Optional[Path] = None,
) -> Path:
    """Résoudre un chemin canonique et vérifier qu'il est autorisé.

    Args:
        path: chemin à résoudre.
        roots: racines autorisées (défaut : `default_allowed_roots()`).
        base: base de résolution des chemins relatifs (défaut : racine du projet).

    Returns:
        Le chemin canonique, s'il se trouve dans une racine autorisée.

    Raises:
        PathSecurityError: si le chemin résolu sort des racines autorisées.
    """
    allowed = [
        canonical_path(root)
        for root in (roots if roots is not None else default_allowed_roots())
    ]
    resolved = canonical_path(path, base=base)
    for root in allowed:
        if is_within(resolved, root):
            return resolved
    raise PathSecurityError(
        f"Chemin hors des racines autorisées : {os.fspath(path)!r}"
    )
