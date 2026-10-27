"""Télémétrie réelle du poste qui héberge MILES.

Aucune valeur n'est inventée : chaque champ est soit mesuré sur la machine,
soit déclaré indisponible avec sa raison. C'est la règle inverse de
l'interface de démonstration, qui affichait des températures, une batterie et
un signal fabriqués par ``Math.random``.

Les capteurs matériels de la Miles Box (température, batterie, ventilateurs,
signal radio) ne sont pas exposés par MILES : ils sont donc renvoyés
``available: false`` avec une raison explicite, jamais une valeur plausible.

Module volontairement sans dépendance : uniquement la bibliothèque standard.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

__all__ = ["build_telemetry", "uptime_seconds", "SENSOR_IDS"]

#: Capteurs de la Miles Box qui ne sont pas exposés par MILES aujourd'hui.
#: Ils restent déclarés pour que l'interface montre un manque assumé au lieu
#: d'un chiffre décoratif.
SENSOR_IDS: tuple[tuple[str, str, str], ...] = (
    ("temperature", "Température", "aucun capteur thermique déclaré dans MILES"),
    ("battery", "Batterie", "alimentation secteur : aucune batterie suivie"),
    ("fan", "Ventilateurs", "vitesse non exposée par le matériel"),
    ("signal", "Signal radio", "liaison locale filaire : pas de métrique radio"),
)

_PROCESS_START = time.monotonic()


def uptime_seconds() -> int:
    """Durée de vie du processus qui sert cette requête, en secondes."""
    return max(0, int(time.monotonic() - _PROCESS_START))


def _repo_root() -> Path:
    """Racine du dépôt, déduite de l'emplacement de ce module."""
    return Path(__file__).resolve().parents[1]


def _disk(path: Path) -> dict[str, Any]:
    """Occupation du volume qui contient ``path``."""
    try:
        usage = shutil.disk_usage(str(path))
    except OSError as exc:  # volume inaccessible : on le dit, sans inventer
        return {"available": False, "reason": type(exc).__name__}
    used_percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
    return {
        "available": True,
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": used_percent,
    }


def build_telemetry(
    *,
    provider: Optional[dict[str, Any]] = None,
    memory_available: Optional[bool] = None,
    root: Optional[Path] = None,
) -> dict[str, Any]:
    """Construire la télémétrie réelle du poste.

    Args:
        provider: état du fournisseur (``provider_state``), jamais des secrets.
        memory_available: disponibilité de la mémoire locale.
        root: racine dont on mesure le disque (dépôt par défaut).

    Returns:
        Un dictionnaire sérialisable. Chaque section indique ``available``.
    """
    base = (root or _repo_root()).resolve()
    state = provider or {}
    sensors = [
        {
            "id": sensor_id,
            "label": label,
            "available": False,
            "value": None,
            "reason": reason,
        }
        for sensor_id, label, reason in SENSOR_IDS
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": {
            "available": True,
            "name": platform.node() or "poste local",
            "system": platform.system() or "inconnu",
            "release": platform.release() or "inconnu",
            "machine": platform.machine() or "inconnu",
            "cpu_count": os.cpu_count() or 0,
            "python": platform.python_version(),
        },
        "process": {
            "available": True,
            "pid": os.getpid(),
            "uptime_seconds": uptime_seconds(),
        },
        "disk": {"path": str(base), **_disk(base)},
        "provider": {
            "available": bool(state.get("name")),
            "name": state.get("name") or "non configuré",
            "mode": state.get("mode") or "inconnu",
            "model": state.get("model") or "inconnu",
            "availability": state.get("availability") or "non testée",
        },
        "memory": {
            "available": bool(memory_available),
            "label": "mémoire locale SQLite" if memory_available else "indisponible",
        },
        "sensors": sensors,
        "unavailable": [sensor["id"] for sensor in sensors],
    }
