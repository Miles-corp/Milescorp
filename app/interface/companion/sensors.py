"""Mesures réelles du poste qui héberge le site Companion.

Aucune valeur n'est inventée (DEC-014). Chaque mesure indisponible est
renvoyée avec une **raison** explicite, jamais avec un chiffre plausible :

- Linux : `/proc` et `/sys` en lecture seule, sans dépendance ;
- Windows (poste de développement) : seuls l'hôte, le disque et le processus
  sont mesurables ; le reste est déclaré indisponible ;
- boîtier : `GET /box/telemetry` sur le backend local (port 8095), avec l'âge
  de la mesure. Backend muet = « indisponible », pas une valeur.

Le module ne lance aucun processus et ne fait aucun appel réseau sortant :
seul le backend boîtier local est interrogé, et uniquement sur une adresse de
bouclage.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
PROC = Path("/proc")
SYS = Path("/sys")
DISK_TARGET = ROOT.parents[2]
CPU_SAMPLE_S = 0.12
CPU_CACHE_S = 2.0
BOX_TIMEOUT_S = 2.0

_LOCK = threading.RLock()
_CPU_CACHE: dict[str, Any] = {"at": 0.0, "value": None}
_CPU_LAST: Optional[tuple[int, int, float]] = None
_NET_LAST: Optional[tuple[float, dict[str, tuple[int, int]]]] = None
_PROCESS_START = time.monotonic()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _metric(
    metric_id: str,
    label: str,
    *,
    value: Any = None,
    unit: str = "",
    available: bool = False,
    reason: Optional[str] = None,
    source: str = "",
    measured_at: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "id": metric_id,
        "label": label,
        "value": value,
        "unit": unit,
        "available": bool(available),
        "reason": None if available else (reason or "non mesuré"),
        "source": source,
        "measured_at": measured_at or _now_iso(),
    }


def _cpu_times() -> Optional[tuple[int, int]]:
    text = _read(PROC / "stat")
    if not text:
        return None
    first = text.splitlines()[0].split()
    if not first or first[0] != "cpu":
        return None
    try:
        values = [int(x) for x in first[1:]]
    except ValueError:
        return None
    if len(values) < 5:
        return None
    idle = values[3] + values[4]
    total = sum(values[:8])
    return idle, total


def cpu_percent() -> Optional[float]:
    """Pourcentage CPU depuis deux relevés de `/proc/stat` (cache 2 s)."""
    global _CPU_LAST
    with _LOCK:
        now = time.monotonic()
        cached = _CPU_CACHE.get("value")
        if cached is not None and now - float(_CPU_CACHE.get("at") or 0) < CPU_CACHE_S:
            return float(cached)

        first = _cpu_times()
        if first is None:
            return None
        if _CPU_LAST is None:
            time.sleep(CPU_SAMPLE_S)
            second = _cpu_times()
            if second is None:
                return None
            _CPU_LAST = (second[0], second[1], time.monotonic())
            return None
        prev_idle, prev_total, prev_at = _CPU_LAST
        idle, total = first
        delta_total = total - prev_total
        delta_idle = idle - prev_idle
        _CPU_LAST = (idle, total, now)
        if delta_total <= 0:
            return float(cached) if cached is not None else None
        percent = max(0.0, min(100.0, 100.0 * (delta_total - delta_idle) / delta_total))
        value = round(percent, 1)
        _CPU_CACHE.update({"at": now, "value": value})
        return value


def load_average() -> Optional[list[float]]:
    text = _read(PROC / "loadavg")
    if not text:
        return None
    try:
        return [float(x) for x in text.split()[:3]]
    except ValueError:
        return None


def memory() -> Optional[dict[str, Any]]:
    text = _read(PROC / "meminfo")
    if not text:
        return None
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        try:
            values[key] = int(parts[0]) * 1024
        except ValueError:
            continue
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if not total or available is None:
        return None
    used = max(0, total - available)
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "used_percent": round(100.0 * used / total, 1) if total else 0.0,
    }


def disk_usage(path: Path = DISK_TARGET) -> Optional[dict[str, Any]]:
    try:
        usage = shutil.disk_usage(str(path))
    except OSError:
        return None
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0,
    }


def uptime_seconds() -> Optional[float]:
    text = _read(PROC / "uptime")
    if not text:
        return None
    try:
        return round(float(text.split()[0]), 1)
    except (ValueError, IndexError):
        return None


def process_uptime_seconds() -> int:
    return max(0, int(time.monotonic() - _PROCESS_START))


def cpu_model() -> Optional[str]:
    text = _read(PROC / "cpuinfo")
    if not text:
        return None
    for line in text.splitlines():
        if line.lower().startswith("model name"):
            _, _, value = line.partition(":")
            value = value.strip()
            return value or None
    return None


def _netdev() -> Optional[dict[str, tuple[int, int]]]:
    text = _read(PROC / "net" / "dev")
    if not text:
        return None
    counters: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, raw = line.split(":", 1)
        fields = raw.split()
        if len(fields) < 9:
            continue
        try:
            counters[name.strip()] = (int(fields[0]), int(fields[8]))
        except ValueError:
            continue
    return counters


def _interfaces() -> dict[str, str]:
    root = SYS / "class" / "net"
    result: dict[str, str] = {}
    try:
        names = sorted(p.name for p in root.iterdir() if p.is_dir())
    except OSError:
        return result
    for name in names:
        state = _read(root / name / "operstate")
        if state:
            result[name] = state.strip()
    return result


def _timedelta_rates(counters: dict[str, tuple[int, int]]) -> Optional[dict[str, dict[str, float]]]:
    """Débits par interface depuis deux relevés ; None au premier passage."""
    global _NET_LAST
    with _LOCK:
        now = time.monotonic()
        previous = _NET_LAST
        _NET_LAST = (now, counters)
        if previous is None:
            return None
        elapsed = now - previous[0]
        if elapsed <= 0:
            return None
        rates: dict[str, dict[str, float]] = {}
        for name, (rx, tx) in counters.items():
            if name not in previous[1]:
                continue
            old_rx, old_tx = previous[1][name]
            rates[name] = {
                "rx_bps": round(max(0, rx - old_rx) / elapsed, 1),
                "tx_bps": round(max(0, tx - old_tx) / elapsed, 1),
            }
        return rates


def _hwmon() -> dict[str, Any]:
    """Températures et ventilateurs exposés par `/sys/class/hwmon`."""
    root = SYS / "class" / "hwmon"
    temperatures: list[dict[str, Any]] = []
    fans: list[dict[str, Any]] = []
    try:
        entries = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return {"temperatures": temperatures, "fans": fans}
    for entry in entries:
        for path in sorted(entry.glob("temp*_input")):
            raw = _read(path)
            if raw is None:
                continue
            try:
                celsius = round(int(raw.strip()) / 1000.0, 1)
            except ValueError:
                continue
            if celsius <= -50 or celsius >= 200:
                continue  # valeur aberrante : pas une mesure exploitable
            label_path = path.with_name(path.name.replace("_input", "_label"))
            label = (_read(label_path) or "").strip()
            temperatures.append(
                {
                    "capteur": entry.name,
                    "libelle": label or entry.name,
                    "celsius": celsius,
                }
            )
        for path in sorted(entry.glob("fan*_input")):
            raw = _read(path)
            if raw is None:
                continue
            try:
                rpm = int(raw.strip())
            except ValueError:
                continue
            if rpm <= 0 or rpm > 60000:
                continue
            fans.append({"capteur": entry.name, "tr_min": rpm})
    return {"temperatures": temperatures, "fans": fans}


def _battery() -> Optional[dict[str, Any]]:
    root = SYS / "class" / "power_supply"
    try:
        entries = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError:
        return None
    for entry in entries:
        kind = (_read(entry / "type") or "").strip().lower()
        if kind != "battery":
            continue
        capacity = _read(entry / "capacity")
        status = (_read(entry / "status") or "").strip()
        if capacity is None:
            continue
        try:
            percent = int(capacity.strip())
        except ValueError:
            continue
        return {
            "percent": percent,
            "status": status or "inconnu",
            "name": entry.name,
        }
    return None


def host_info() -> dict[str, Any]:
    return {
        "name": platform.node() or "poste local",
        "system": platform.system() or "inconnu",
        "release": platform.release() or "inconnu",
        "machine": platform.machine() or "inconnu",
        "cpu_count": os.cpu_count() or 0,
        "python": platform.python_version(),
        "pid": os.getpid(),
    }


def fetch_box(url: str, timeout: float = BOX_TIMEOUT_S) -> dict[str, Any]:
    """Interroger le backend boîtier local, uniquement sur une boucle locale."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "127.0.0.1",
        "localhost",
        "::1",
    ):
        return {
            "available": False,
            "reason": "cible du backend boîtier non locale (refusée)",
        }
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/box/telemetry", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - l'absence est le résultat attendu
        return {"available": False, "reason": "backend muet (%s)" % type(exc).__name__}
    if not isinstance(payload, dict):
        return {"available": False, "reason": "réponse du backend illisible"}
    payload["available"] = True
    payload["received_at"] = _now_iso()
    return payload


def build_snapshot(
    *,
    dev_mode: bool = False,
    box_url: Optional[str] = None,
) -> dict[str, Any]:
    """Photographie complète : mesures réelles + indisponibilités motivées."""
    now = _now_iso()
    linux = PROC.is_dir()
    values: list[dict[str, Any]] = []

    load = load_average()
    cpu = cpu_percent()
    if cpu is not None:
        values.append(_metric("cpu", "Processeur", value=cpu, unit="%", available=True, source="proc/stat"))
    elif load is not None:
        values.append(
            _metric(
                "cpu",
                "Charge (1 min)",
                value=round(load[0], 2),
                unit="",
                available=True,
                source="proc/loadavg",
            )
        )
    else:
        values.append(
            _metric(
                "cpu",
                "Processeur",
                reason="lecture /proc indisponible sur cette plateforme" if not linux else "mesure CPU en cours",
                source="proc/stat",
            )
        )

    mem = memory()
    if mem:
        values.append(
            _metric(
                "ram",
                "Mémoire utilisée",
                value=mem["used_percent"],
                unit="%",
                available=True,
                source="proc/meminfo",
            )
        )
        values.append(
            _metric(
                "ram_free",
                "Mémoire disponible",
                value=round(mem["available_bytes"] / 1073741824, 1),
                unit="Gio",
                available=True,
                source="proc/meminfo",
            )
        )
    else:
        values.append(
            _metric(
                "ram",
                "Mémoire utilisée",
                reason="lecture /proc/meminfo indisponible",
                source="proc/meminfo",
            )
        )

    disk = disk_usage()
    if disk:
        values.append(
            _metric(
                "disk",
                "Disque utilisé",
                value=disk["used_percent"],
                unit="%",
                available=True,
                source="disque",
            )
        )
        values.append(
            _metric(
                "disk_free",
                "Espace libre",
                value=round(disk["free_bytes"] / 1073741824, 1),
                unit="Gio",
                available=True,
                source="disque",
            )
        )
    else:
        values.append(_metric("disk", "Disque", reason="volume illisible", source="disque"))

    up = uptime_seconds()
    if up is not None:
        values.append(
            _metric("uptime", "Uptime système", value=round(up / 3600, 1), unit="h", available=True, source="proc/uptime")
        )
    else:
        values.append(_metric("uptime", "Uptime système", reason="lecture /proc/uptime indisponible", source="proc/uptime"))

    net = _netdev()
    rates = _timedelta_rates(net) if net else None
    if net:
        total_rx = sum(v[0] for k, v in net.items() if k != "lo")
        total_tx = sum(v[1] for k, v in net.items() if k != "lo")
        values.append(
            _metric(
                "network",
                "Réseau (cumul)",
                value=round((total_rx + total_tx) / 1048576, 1),
                unit="Mio",
                available=True,
                source="proc/net/dev",
            )
        )
        if rates:
            rx = sum(v["rx_bps"] for k, v in rates.items() if k != "lo")
            tx = sum(v["tx_bps"] for k, v in rates.items() if k != "lo")
            values.append(
                _metric(
                    "network_rate",
                    "Débit réseau",
                    value="%s ↓ / %s ↑" % (_fmt_bytes(rx), _fmt_bytes(tx)),
                    unit="/s",
                    available=True,
                    source="proc/net/dev",
                )
            )
        else:
            values.append(
                _metric(
                    "network_rate",
                    "Débit réseau",
                    reason="mesure en cours (deuxième relevé nécessaire)",
                    source="proc/net/dev",
                )
            )
    else:
        values.append(_metric("network", "Réseau", reason="lecture /proc/net/dev indisponible", source="proc/net/dev"))

    hw = _hwmon()
    temps = hw["temperatures"]
    if temps:
        hottest = max(temps, key=lambda item: item["celsius"])
        values.append(
            _metric(
                "temperature",
                "Température",
                value=hottest["celsius"],
                unit="°C",
                available=True,
                source="sys/class/hwmon",
            )
        )
    else:
        values.append(
            _metric(
                "temperature",
                "Température",
                reason="aucun capteur thermique exposé par le matériel",
                source="sys/class/hwmon",
            )
        )

    fans = hw["fans"]
    if fans:
        values.append(
            _metric(
                "fan",
                "Ventilateur",
                value=fans[0]["tr_min"],
                unit="tr/min",
                available=True,
                source="sys/class/hwmon",
            )
        )
    else:
        values.append(
            _metric(
                "fan",
                "Ventilateur",
                reason="aucun capteur de ventilation exposé",
                source="sys/class/hwmon",
            )
        )

    battery = _battery()
    if battery:
        values.append(
            _metric(
                "battery",
                "Batterie",
                value=battery["percent"],
                unit="%",
                available=True,
                source="sys/class/power_supply",
            )
        )
    else:
        values.append(
            _metric(
                "battery",
                "Batterie",
                reason="aucune batterie suivie (alimentation secteur)",
                source="sys/class/power_supply",
            )
        )

    model = cpu_model()
    values.append(
        _metric(
            "processor",
            "Modèle du processeur",
            value=model or host_info()["machine"],
            unit="",
            available=bool(model or host_info()["machine"]),
            reason="modèle non exposé",
            source="proc/cpuinfo",
        )
    )

    snapshot: dict[str, Any] = {
        "measured_at": now,
        "mode": "developpeur" if dev_mode else "normal",
        "host": host_info(),
        "process_uptime_s": process_uptime_seconds(),
        "values": values,
        "storage": disk,
        "box": fetch_box(box_url) if box_url else {"available": False, "reason": "backend boîtier non configuré"},
    }
    if dev_mode:
        snapshot["dev"] = {
            "load": load,
            "memory_bytes": mem,
            "interfaces": _interfaces(),
            "network_counters": net,
            "network_rates": rates,
            "temperatures": temps,
            "fans": fans,
            "battery": battery,
            "proc_root": str(PROC),
            "sys_root": str(SYS),
        }
    return snapshot


def _fmt_bytes(value: float) -> str:
    if value >= 1048576:
        return "%.1f Mio" % (value / 1048576)
    if value >= 1024:
        return "%.1f Kio" % (value / 1024)
    return "%d o" % int(value)
