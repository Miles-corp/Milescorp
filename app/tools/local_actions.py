"""Outils MILES : actions locales en lecture seule.

Ce module expose des **fonctions de niveau module** : le moteur d'outils
exécute les handlers dans un sous-processus (arrêt effectif garanti en cas
de dépassement de délai), ce qui impose que le handler soit picklable.
Une closure ou une méthode liée ne conviendrait pas.

Les chemins sont confinés aux racines autorisées (répertoire du projet et
dossier ``data/``) via :mod:`app.security.paths`.

Aucun de ces outils n'écrit, ne supprime et n'exécute de commande : ce sont
des outils d'observation, utilisables par l'orchestrateur de missions.

Sécurité de la lecture de fichiers :
- le chemin est résolu canoniquement (les liens symboliques sont résolus) ;
- les fichiers potentiellement porteurs de secrets (``.env``, clés privées,
  fichiers d'identifiants) sont **refusés** ;
- la taille lue est bornée ;
- le contenu est expurgé des motifs de secrets avant d'être retourné.
"""

from __future__ import annotations

import datetime
import os
import tempfile
from typing import Any, Dict, List
from app.security.paths import (
    PathSecurityError,
    canonical_path,
    is_within,
    resolve_authorized_path,
)
from app.utilities.redaction import sanitize_text

#: Taille maximale lue par défaut (octets).
DEFAULT_MAX_READ_BYTES = 20000

#: Taille maximale absolue lue (octets), quel que soit le paramètre fourni.
HARD_MAX_READ_BYTES = 65536

#: Nombre maximal d'entrées retournées par un listing.
MAX_LIST_ENTRIES = 500

#: Profondeur maximale de listing.
MAX_LIST_DEPTH = 3

#: Noms de fichiers dont la lecture est refusée (contenu potentiellement secret).
_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        ".git-credentials",
        "credentials",
        "secrets",
    }
)

#: Suffixes de fichiers dont la lecture est refusée.
_SENSITIVE_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    ".crt",
    ".cer",
    ".der",
    ".asc",
    ".gpg",
)

#: Préfixes de noms de fichiers dont la lecture est refusée.
_SENSITIVE_PREFIXES = (
    ".env.",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
)

#: Extensions considérées comme du texte lisible (aperçu pertinent).
TEXT_EXTENSIONS = frozenset(
    {
        ".md", ".markdown", ".rst", ".txt", ".text",
        ".py", ".json", ".toml", ".ini", ".cfg", ".conf",
        ".yaml", ".yml", ".csv", ".tsv",
        ".sh", ".bash", ".zsh", ".ps1", ".bat",
        ".html", ".htm", ".css", ".js", ".ts", ".jsx", ".tsx",
        ".sql", ".xml", ".gitignore", ".dockerignore", ".editorconfig",
        ".example", ".sample", ".template",
    }
)


def is_sensitive_filename(name: str) -> bool:
    """Indiquer si un nom de fichier correspond à un fichier sensible.

    Un fichier sensible n'est jamais lu : ni son contenu, ni un aperçu.
    """
    lowered = name.lower()
    if lowered in _SENSITIVE_NAMES:
        return True
    if any(lowered.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES):
        return True
    if any(lowered.startswith(prefix) for prefix in _SENSITIVE_PREFIXES):
        return True
    return False


def is_text_filename(name: str) -> bool:
    """Indiquer si un fichier est probablement du texte lisible."""
    lowered = name.lower()
    if lowered in ("readme", "license", "makefile", "dockerfile"):
        return True
    for extension in TEXT_EXTENSIONS:
        if lowered.endswith(extension):
            return True
    return False


def datetime_handler() -> str:
    """Retourner la date et l'heure locales (aucun effet de bord)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def workdir_handler() -> str:
    """Retourner le répertoire de travail courant (aucun effet de bord)."""
    return os.getcwd()


def list_files_handler(path: str = ".", depth: int = 1) -> Dict[str, Any]:
    """Lister les fichiers d'un répertoire autorisé.

    Le chemin est résolu canoniquement et confiné aux racines autorisées :
    un lien symbolique pointant hors racines est refusé. La descente dans
    les sous-répertoires applique **la même** contrainte : un sous-dossier
    dont la résolution canonique sort des racines autorisées n'est pas
    parcouru.

    Le résultat est **structuré** afin que l'orchestrateur puisse exploiter
    les entrées sans deviner : nom, chemin, taille, caractère textuel et
    caractère sensible. Aucun contenu de fichier n'est retourné ici.

    Args:
        path: répertoire à lister, relatif à la racine du projet.
        depth: profondeur de parcours (1 = le dossier seul, 2 = un niveau
            de sous-dossiers). La profondeur est bornée.

    Returns:
        Un dictionnaire ``{"path", "depth", "entries", "count",
        "truncated"}``.

    Raises:
        PermissionError: si le chemin sort des racines autorisées.
    """
    try:
        target = resolve_authorized_path(path)
    except PathSecurityError as exc:
        raise PermissionError(str(exc)) from exc

    levels = max(1, min(int(depth), MAX_LIST_DEPTH))

    if not os.path.isdir(target):
        return {
            "path": str(target),
            "depth": levels,
            "entries": [],
            "count": 0,
            "truncated": False,
            "message": f"Répertoire introuvable ou non lisible : {path}",
        }

    entries: List[Dict[str, Any]] = []
    truncated = False

    def _walk(directory: str, current_depth: int) -> None:
        nonlocal truncated
        if truncated:
            return
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return
        for name in names:
            if len(entries) >= MAX_LIST_ENTRIES:
                truncated = True
                return
            full_path = os.path.join(directory, name)
            is_dir = os.path.isdir(full_path)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = -1
            entries.append(
                {
                    "name": name,
                    "path": full_path,
                    "is_dir": is_dir,
                    "size": size,
                    "is_text": is_text_filename(name),
                    "sensitive": is_sensitive_filename(name),
                    "depth": current_depth,
                }
            )
            if is_dir and current_depth < levels:
                # Un sous-dossier n'est parcouru que si sa résolution
                # canonique reste dans les racines autorisées.
                try:
                    resolve_authorized_path(full_path)
                except PathSecurityError:
                    continue
                _walk(full_path, current_depth + 1)

    _walk(str(target), 1)

    return {
        "path": str(target),
        "depth": levels,
        "entries": entries,
        "count": len(entries),
        "truncated": truncated,
    }


def read_file_handler(path: str, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    """Lire (en partie) le contenu d'un fichier autorisé.

    Contrôles appliqués :
    - confinement canonique du chemin (racines autorisées) ;
    - refus des fichiers sensibles (``.env``, clés privées, identifiants) ;
    - lecture bornée par ``max_bytes`` (plafond absolu : 64 Kio) ;
    - expurgation des motifs de secrets du contenu retourné.

    Args:
        path: fichier à lire, relatif à la racine du projet.
        max_bytes: nombre maximal d'octets lus.

    Returns:
        Le contenu lu, ou un message expliquant pourquoi le fichier n'a
        pas été lu.

    Raises:
        PermissionError: si le chemin sort des racines autorisées ou si le
            fichier est sensible.
    """
    try:
        target = resolve_authorized_path(path)
    except PathSecurityError as exc:
        raise PermissionError(str(exc)) from exc

    name = os.path.basename(str(target))
    if is_sensitive_filename(name):
        raise PermissionError(
            f"Fichier sensible : lecture interdite ({name})."
        )

    if not os.path.isfile(target):
        return f"Fichier introuvable ou illisible : {path}"

    try:
        size = os.path.getsize(target)
    except OSError:
        size = -1

    limit = max(1, min(int(max_bytes), HARD_MAX_READ_BYTES))
    if size > limit:
        return (
            f"Fichier non lu : taille de {size} octets supérieure à la "
            f"limite de {limit} octets."
        )

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(limit)
    except OSError:
        return f"Fichier illisible : {path}"

    return sanitize_text(content)


#: Répertoire strictement autorisé pour les notes d'écriture (S3).
NOTES_DIR = "data/notes"

#: Extensions autorisées pour une note.
NOTE_EXTENSIONS = (".md", ".txt")

#: Taille maximale d'une note (caractères).
MAX_NOTE_CHARS = 4000


def write_note_handler(path: str, content: str) -> Dict[str, Any]:
    """Écrire une note dans le répertoire autorisé ``data/notes`` (S3).

    Première action d'écriture de MILES, strictement bornée :

    - confinement canonique : le chemin doit rester **sous** ``data/notes``
      (y compris les liens symboliques, résolus par ``canonical_path``) ;
    - nom de fichier sain : pas de nom sensible (``.env``, clés), extension
      ``.md`` ou ``.txt``, nom simple sans traversée de répertoire ;
    - **refus d'écrasement** : un fichier existant n'est jamais modifié ;
    - écriture atomique (fichier temporaire + ``os.replace``) ;
    - contenu borné (4 000 caractères).

    La confirmation humaine n'est pas gérée ici : c'est le moteur d'outils
    (``ToolPolicy``, risque MEDIUM) qui l'exige avant tout appel.

    Args:
        path: chemin de la note, relatif à la racine du projet et sous
            ``data/notes`` (ex. ``data/notes/journal.md``).
        content: contenu texte de la note.

    Returns:
        Un dictionnaire ``{"written": chemin, "bytes": taille}``, ou
        ``{"error": motif}`` en cas de refus d'écriture.

    Raises:
        PermissionError: chemin hors de ``data/notes`` ou fichier sensible.
        ValueError: contenu ou nom invalide (vide, trop long, extension,
            écrasement demandé).
    """
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Le contenu de la note est vide.")
    if len(content) > MAX_NOTE_CHARS:
        raise ValueError(
            f"Contenu trop long : {len(content)} caractères "
            f"(maximum {MAX_NOTE_CHARS})."
        )

    notes_root = resolve_authorized_path(NOTES_DIR)
    try:
        target = resolve_authorized_path(path)
    except PathSecurityError as exc:
        raise PermissionError(str(exc)) from exc

    try:
        if not is_within(canonical_path(str(target)), canonical_path(str(notes_root))):
            raise PermissionError(
                "Écriture refusée : seul le répertoire data/notes est autorisé."
            )
    except (OSError, ValueError) as exc:
        raise PermissionError("Chemin de note invalide.") from exc

    name = os.path.basename(str(target))
    if is_sensitive_filename(name):
        raise PermissionError(f"Fichier sensible : écriture interdite ({name}).")
    if not name.lower().endswith(NOTE_EXTENSIONS):
        raise ValueError("Extension de note invalide : .md ou .txt attendu.")
    if name != os.path.basename(path.replace("\\", "/").split("/")[-1]):
        raise ValueError("Nom de note invalide.")
    if os.path.exists(str(target)):
        raise ValueError("Une note du même nom existe déjà : écrasement interdit.")

    os.makedirs(str(notes_root), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".miles-note-", suffix=".tmp", dir=str(notes_root)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(tmp_path, str(target))
    except OSError as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return {"error": f"Écriture impossible : {type(exc).__name__}."}
    return {
        "written": os.path.relpath(str(target)),
        "bytes": len(content.encode("utf-8")),
    }
