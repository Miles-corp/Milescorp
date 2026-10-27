"""Cockpit projet MILES : lecture des documents de coordination.

Ce module est volontairement **pur** (bibliothèque standard uniquement) et
séparé de l'interface web :

- il lit `TASKS.md`, `STATUS.md`, `DECISIONS.md` et `MESSAGES.md` ;
- il expose une photographie structurée du pilotage du projet ;
- il permet une **écriture strictement bornée** : le statut d'une tâche de
  `TASKS.md`, et rien d'autre.

Règles de sécurité appliquées :

1. Le répertoire des documents est fixé à la construction (ou par
   ``MILES_COORDINATION_DIR``). **Aucun chemin ne provient d'une requête.**
2. Un identifiant de tâche est validé par expression régulière avant toute
   recherche dans le fichier.
3. Une ligne de tableau ambiguë (nombre de colonnes incorrect, identifiant
   présent deux fois) est **refusée**, jamais devinée.
4. L'écriture est **atomique** (fichier temporaire + ``os.replace``).
5. Chaque changement est journalisé dans un fichier d'audit JSONL hors Git,
   écrit **avant** la modification du document.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

__all__ = [
    "ALLOWED_STATUSES",
    "AGENTS",
    "TRANSITIONS",
    "TaskWriteError",
    "default_coordination_dir",
    "build_board",
    "parse_tasks",
    "set_task_status",
]

#: Statuts autorisés par `AGENTS.md`.
ALLOWED_STATUSES: tuple[str, ...] = (
    "TODO",
    "IN_PROGRESS",
    "BLOCKED",
    "DONE",
    "CANCELLED",
)

#: Agents autorisés (identifiants de `AGENTS.md`).
AGENTS: tuple[str, ...] = ("Agent A", "Agent B")

#: Transitions autorisées. Une tâche terminée ou annulée n'est plus modifiable
#: depuis le cockpit : la réouverture exige une décision explicite commitée
#: dans `TASKS.md`, pas un clic.
TRANSITIONS: dict[str, frozenset[str]] = {
    "TODO": frozenset({"IN_PROGRESS", "BLOCKED", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"DONE", "BLOCKED", "CANCELLED"}),
    "BLOCKED": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "DONE": frozenset(),
    "CANCELLED": frozenset(),
}

_TASK_ID_RE = re.compile(r"^TASK(?:-DEV)?-\d{3}$")
_STATUS_RE = re.compile(r"^(TODO|IN_PROGRESS|BLOCKED|DONE|CANCELLED)\b")
_AGENT_RE = re.compile(r"^(Agent [AB])\b")
_DECISION_RE = re.compile(r"^##\s+((?:DEC|D)-\d{3})\s*[—-]\s*(.+)$")

#: Colonnes du tableau des tâches (`TASKS.md`).
_TASK_COLUMNS = (
    "id",
    "title",
    "description",
    "status",
    "owner",
    "files",
    "expected",
    "blocked_by",
    "created",
    "updated",
)


class TaskWriteError(Exception):
    """Refus explicite d'une écriture dans `TASKS.md`.

    Le code est stable et destiné à l'interface (``invalid_status``,
    ``forbidden_owner``…), le message est lisible par un humain. Le statut
    HTTP à renvoyer est porté par l'exception.
    """

    def __init__(self, code: str, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def default_coordination_dir() -> Path:
    """Répertoire des documents de coordination.

    Priorité à ``MILES_COORDINATION_DIR`` (utile aux tests et aux
    installations déplacées), sinon ``docs/coordination`` à la racine du
    dépôt. Le chemin est résolu une fois, jamais depuis une requête.
    """
    override = os.environ.get("MILES_COORDINATION_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    # app/interface/project_board.py -> app/interface -> app -> racine
    return (Path(__file__).resolve().parents[2] / "docs" / "coordination").resolve()


# --------------------------------------------------------------------------
# Lecture des documents
# --------------------------------------------------------------------------


def _read_text(path: Path) -> Optional[str]:
    """Lire un document en UTF-8, ou renvoyer ``None`` s'il est absent."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _split_row(line: str) -> list[str]:
    """Découper une ligne de tableau Markdown en cellules nettoyées."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _document_meta(path: Path, text: Optional[str]) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "name": path.name,
        "exists": text is not None,
        "lines": len(text.splitlines()) if text else 0,
        "modified": None,
    }
    try:
        meta["modified"] = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).astimezone().isoformat(timespec="seconds")
    except OSError:
        pass
    return meta


def parse_tasks(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Analyser le tableau des tâches de `TASKS.md`.

    Returns:
        (tâches, anomalies). Une ligne de tableau qui ne comporte pas
        exactement dix colonnes est signalée comme anomalie : le cockpit
        l'affiche au lieu de la masquer, et l'écriture la refusera.
    """
    tasks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| TASK"):
            continue
        cells = _split_row(line)
        task_id = cells[0] if cells else ""
        if len(cells) != len(_TASK_COLUMNS):
            issues.append(
                {
                    "line": lineno,
                    "id": task_id,
                    "problem": (
                        f"{len(cells)} colonnes au lieu de "
                        f"{len(_TASK_COLUMNS)} : ligne illisible par le cockpit"
                    ),
                }
            )
            tasks.append(
                {
                    "id": task_id,
                    "title": cells[1] if len(cells) > 1 else "",
                    "description": "",
                    "status": "",
                    "status_base": None,
                    "owner": cells[2] if len(cells) > 2 else "",
                    "files": "",
                    "expected": "",
                    "blocked_by": "",
                    "created": "",
                    "updated": "",
                    "line": lineno,
                    "malformed": True,
                }
            )
            continue

        record = dict(zip(_TASK_COLUMNS, cells))
        record["status_base"] = _normalize_status(record["status"])
        record["line"] = lineno
        record["malformed"] = record["status_base"] is None
        if record["malformed"]:
            issues.append(
                {
                    "line": lineno,
                    "id": task_id,
                    "problem": f"statut non reconnu : {record['status']!r}",
                }
            )
        tasks.append(record)

    seen: dict[str, int] = {}
    for task in tasks:
        seen[task["id"]] = seen.get(task["id"], 0) + 1
    for task_id, count in seen.items():
        if count > 1:
            issues.append(
                {
                    "id": task_id,
                    "line": None,
                    "problem": f"identifiant présent {count} fois : écriture refusée",
                }
            )
    return tasks, issues


def _normalize_status(cell: str) -> Optional[str]:
    """Extraire le statut de base d'une cellule (`DONE (analyse…)` → `DONE`)."""
    match = _STATUS_RE.match((cell or "").strip())
    return match.group(1) if match else None


def _summarize(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {status: 0 for status in ALLOWED_STATUSES}
    for task in tasks:
        base = task.get("status_base")
        if base in counts:
            counts[base] += 1
    blocked = [
        {"id": t["id"], "title": t["title"], "blocked_by": t.get("blocked_by", "")}
        for t in tasks
        if t.get("status_base") == "BLOCKED"
    ]
    return {
        "total": len(tasks),
        "by_status": counts,
        "blocked": blocked,
        "malformed": sum(1 for t in tasks if t.get("malformed")),
        "owners": {
            agent: sum(1 for t in tasks if str(t.get("owner", "")).startswith(agent))
            for agent in AGENTS
        },
    }


def parse_decisions(text: str, limit: int = 8) -> list[dict[str, str]]:
    """Extraire les dernières décisions de `DECISIONS.md`."""
    decisions: list[dict[str, str]] = []
    current: Optional[dict[str, str]] = None
    for line in text.splitlines():
        match = _DECISION_RE.match(line.strip())
        if match:
            current = {"id": match.group(1), "title": match.group(2).strip()}
            decisions.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        for key, label in (
            ("date", "- **Date** :"),
            ("author", "- **Auteur** :"),
            ("status", "- **Statut** :"),
        ):
            if stripped.startswith(label):
                current[key] = stripped[len(label):].strip()
    return decisions[-limit:][::-1]


def parse_messages(text: str, limit: int = 30) -> dict[str, Any]:
    """Extraire les messages d'échange et les demandes en attente."""
    messages: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| M-"):
            continue
        cells = _split_row(line)
        if len(cells) < 5:
            continue
        messages.append(
            {
                "id": cells[0],
                "route": cells[1],
                "date": cells[2],
                "status": cells[3],
                "subject": cells[4],
            }
        )
    pending = [m for m in messages if "EN ATTENTE" in m["status"].upper()]
    return {
        "total": len(messages),
        "pending_count": len(pending),
        "pending": pending[:limit],
        "recent": messages[-limit:][::-1],
    }


def _extract_section(text: str, heading: str) -> list[str]:
    """Extraire le corps d'une section de niveau 2, jusqu'à la suivante."""
    lines = text.splitlines()
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.strip().startswith("## "):
            if inside:
                break
            inside = line.strip() == heading
            continue
        if inside:
            collected.append(line)
    return [line for line in collected if line.strip()]


def build_board(docs_dir: Optional[Path] = None, docs_root: Optional[Path] = None) -> dict[str, Any]:
    """Construire la photographie du pilotage à partir des documents.

    Args:
        docs_dir: répertoire des documents de coordination.
        docs_root: racine du dépôt, utilisée pour des chemins relatifs lisibles.
    """
    base = (docs_dir or default_coordination_dir()).resolve()
    root = (docs_root or base.parent.parent).resolve()

    def relative(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.name

    documents: dict[str, Any] = {}
    texts: dict[str, Optional[str]] = {}
    for name in ("TASKS.md", "STATUS.md", "DECISIONS.md", "MESSAGES.md"):
        path = base / name
        texts[name] = _read_text(path)
        documents[name] = _document_meta(path, texts[name])

    tasks_text = texts["TASKS.md"] or ""
    tasks, issues = parse_tasks(tasks_text)

    missing = [name for name, meta in documents.items() if not meta["exists"]]
    for name in missing:
        issues.append(
            {
                "id": None,
                "line": None,
                "problem": f"document absent : {relative(base / name)}",
            }
        )

    status_text = texts["STATUS.md"] or ""
    decisions_text = texts["DECISIONS.md"] or ""
    messages_text = texts["MESSAGES.md"] or ""

    board: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "coordination_dir": relative(base),
        "documents": documents,
        "summary": _summarize(tasks),
        "tasks": tasks,
        "issues": issues,
        "transitions": {key: sorted(value) for key, value in TRANSITIONS.items()},
        "agents": list(AGENTS),
        "decisions": parse_decisions(decisions_text),
        "messages": parse_messages(messages_text),
        "status_excerpt": _extract_section(status_text, "## État instantané (2026-10-27, Agent A)")
        or _extract_section(status_text, "## Blocages"),
        "blockages": _extract_section(status_text, "## Blocages"),
        "status_headings": [
            line.strip()
            for line in status_text.splitlines()
            if line.startswith("## ")
        ][:6],
    }
    return board


# --------------------------------------------------------------------------
# Écriture contrôlée d'un statut
# --------------------------------------------------------------------------


def _audit_path(docs_dir: Path) -> Path:
    return docs_dir.parent.parent / "data" / "project_board_audit.jsonl"


def _append_audit(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def set_task_status(
    *,
    task_id: str,
    new_status: str,
    agent: str,
    docs_dir: Optional[Path] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """Modifier le statut d'une tâche de `TASKS.md`, avec garde-fous.

    Chaque refus lève ``TaskWriteError`` **sans avoir touché au fichier**.

    Raises:
        TaskWriteError: identifiant invalide ou inconnu, statut invalide,
            agent invalide, ligne ambiguë, tâche appartenant à l'autre agent,
            transition non autorisée, écriture impossible.
    """
    task_id = (task_id or "").strip()
    new_status = (new_status or "").strip().upper()
    agent = (agent or "").strip()

    if not _TASK_ID_RE.match(task_id):
        raise TaskWriteError(
            "invalid_task_id",
            "Identifiant de tâche invalide (format attendu : TASK-DEV-000).",
        )
    if new_status not in ALLOWED_STATUSES:
        raise TaskWriteError(
            "invalid_status",
            "Statut inconnu. Valeurs autorisées : " + ", ".join(ALLOWED_STATUSES) + ".",
        )
    if agent not in AGENTS:
        raise TaskWriteError(
            "invalid_agent",
            "Agent inconnu. Indiquez « Agent A » ou « Agent B » (AGENTS.md).",
        )

    base = (docs_dir or default_coordination_dir()).resolve()
    path = base / "TASKS.md"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TaskWriteError(
            "missing_document",
            f"Document de tâches illisible : {path.name}.",
            http_status=500,
        ) from exc

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TaskWriteError(
            "invalid_encoding",
            "Le document de tâches n'est pas en UTF-8 : écriture refusée.",
            http_status=500,
        ) from exc

    newline = "\r\n" if "\r\n" in text else "\n"
    trailing_newline = text.endswith(("\n", "\r"))
    lines = text.splitlines()

    matches = [
        index
        for index, line in enumerate(lines)
        if line.startswith(f"| {task_id} |")
    ]
    if not matches:
        raise TaskWriteError("task_not_found", f"Tâche {task_id} introuvable.")
    if len(matches) > 1:
        raise TaskWriteError(
            "ambiguous_task",
            f"Identifiant {task_id} présent {len(matches)} fois : écriture refusée "
            "(corrigez d'abord la duplication, DEC-013).",
            http_status=409,
        )

    index = matches[0]
    cells = _split_row(lines[index])
    if len(cells) != len(_TASK_COLUMNS):
        raise TaskWriteError(
            "malformed_row",
            f"Ligne {index + 1} illisible ({len(cells)} colonnes au lieu de "
            f"{len(_TASK_COLUMNS)}). Corrigez le tableau à la main, puis réessayez.",
            http_status=409,
        )

    record = dict(zip(_TASK_COLUMNS, cells))
    current_status = _normalize_status(record["status"])
    if current_status is None:
        raise TaskWriteError(
            "malformed_status",
            f"Statut actuel illisible : {record['status']!r}.",
            http_status=409,
        )
    owner_match = _AGENT_RE.match(record["owner"])
    if owner_match is None:
        raise TaskWriteError(
            "malformed_owner",
            f"Agent responsable illisible : {record['owner']!r}.",
            http_status=409,
        )
    owner = owner_match.group(1)

    if current_status == new_status:
        return {
            "task": _task_payload(task_id, record, current_status),
            "changed": False,
            "previous_status": current_status,
            "message": "Aucun changement : la tâche porte déjà ce statut.",
        }

    if owner != agent and current_status in ("IN_PROGRESS", "BLOCKED"):
        raise TaskWriteError(
            "forbidden_owner",
            f"{task_id} est {current_status} et appartient à {owner} : "
            f"{agent} ne peut pas la modifier sans coordination explicite "
            "(règle anti-conflit, AGENTS.md §4).",
            http_status=403,
        )

    if new_status not in TRANSITIONS[current_status]:
        allowed = sorted(TRANSITIONS[current_status]) or ["aucune"]
        raise TaskWriteError(
            "invalid_transition",
            f"Transition {current_status} → {new_status} refusée. "
            f"Depuis {current_status}, transitions autorisées : {', '.join(allowed)}.",
            http_status=409,
        )

    now = today or date.today()
    stamp = now.isoformat()
    cells[3] = new_status
    cells[9] = stamp
    updated_line = "| " + " | ".join(cells) + " |"

    entry = {
        "at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "task_id": task_id,
        "agent": agent,
        "previous_status": current_status,
        "new_status": new_status,
        "document": "docs/coordination/TASKS.md",
        "line": index + 1,
    }
    audit = _audit_path(base)
    try:
        _append_audit(audit, entry)
    except OSError as exc:
        raise TaskWriteError(
            "audit_unavailable",
            "Journal d'audit inaccessible : modification refusée (aucune écriture).",
            http_status=500,
        ) from exc

    lines[index] = updated_line
    payload = newline.join(lines) + (newline if trailing_newline else "")
    try:
        _atomic_write(path, payload.encode("utf-8"))
    except OSError as exc:
        raise TaskWriteError(
            "write_failed",
            "Écriture du document impossible : aucune modification appliquée.",
            http_status=500,
        ) from exc

    new_record = dict(zip(_TASK_COLUMNS, cells))
    result = {
        "task": _task_payload(task_id, new_record, new_status),
        "changed": True,
        "previous_status": current_status,
        "message": f"{task_id} : {current_status} → {new_status} ({agent}).",
        "audit": {"document": "data/project_board_audit.jsonl", "at": entry["at"]},
    }
    return result


def _task_payload(task_id: str, record: dict[str, str], status: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "title": record.get("title", ""),
        "status": status,
        "owner": record.get("owner", ""),
        "updated": record.get("updated", ""),
        "blocked_by": record.get("blocked_by", ""),
    }
