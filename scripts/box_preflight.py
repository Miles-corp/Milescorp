#!/usr/bin/env python3
"""Préflight du boîtier MILES (Q3) — diagnostic STRICTEMENT en lecture seule.

Contrat :
- **Aucun effet de bord** : rien n'est écrit, installé, modifié ou redémarré ;
- **Aucun réseau** : les « ports en écoute » sont lus dans /proc (ou ignorés
  hors Linux) — aucune connexion, aucun bind ;
- **Aucune dépendance** hors bibliothèque standard ;
- les sous-commandes système optionnelles (nvidia-smi, arecord, aplay) sont
  tentées avec un délai court et **ignorées proprement** si absentes.

Usage :  python3 scripts/box_preflight.py
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import Any

#: Délai maximal pour une sous-commande locale (jamais réseau).
_TIMEOUT = 3.0


def _sous_commande(cmd: list[str]) -> str | None:
    """Exécuter une commande LOCALE en lecture seule, ou None si absente/échec."""
    try:
        sortie = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_TIMEOUT, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if sortie.returncode != 0:
        return None
    return sortie.stdout.strip()


def _lecture_fichier(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _meminfo() -> dict[str, str]:
    texte = _lecture_fichier("/proc/meminfo") or ""
    resultat: dict[str, str] = {}
    for ligne in texte.splitlines():
        if ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            resultat[cle.strip()] = valeur.strip()
    return resultat


def _cpu() -> dict[str, Any]:
    modele = ""
    texte = _lecture_fichier("/proc/cpuinfo") or ""
    for ligne in texte.splitlines():
        if ligne.lower().startswith("model name"):
            modele = ligne.split(":", 1)[1].strip()
            break
    return {"cœurs": os.cpu_count(), "modèle": modele}


def _disque(chemin: str = "/") -> dict[str, Any]:
    try:
        u = shutil.disk_usage(chemin)
    except OSError as exc:
        return {"erreur": type(exc).__name__}
    return {
        "total_Go": round(u.total / 1e9, 1),
        "libre_Go": round(u.free / 1e9, 1),
        "utilisé_%": round(100 * (u.total - u.free) / u.total, 1),
    }


def _ports_ecoutes() -> list[str]:
    """Lire /proc/net/tcp{,6} (lecture fichier locale, zéro socket)."""
    ports: set[str] = set()
    for chemin in ("/proc/net/tcp", "/proc/net/tcp6"):
        texte = _lecture_fichier(chemin)
        if not texte:
            continue
        for ligne in texte.splitlines()[1:]:
            champs = ligne.split()
            if len(champs) >= 4 and champs[3] == "0A":  # état LISTEN
                adresse_locale = champs[1]
                if ":" in adresse_locale:
                    _, port_hex = adresse_locale.rsplit(":", 1)
                    try:
                        ports.add(str(int(port_hex, 16)))
                    except ValueError:
                        pass
    return sorted(ports, key=lambda p: int(p))


def _gpu() -> str | None:
    sortie = _sous_commande(["nvidia-smi", "--query-gpu=name,memory.total,temperature.gpu",
                             "--format=csv,noheader"])
    return sortie or None


def _audio() -> dict[str, str | None]:
    return {
        "capture (arecord -l)": _sous_commande(["arecord", "-l"]),
        "lecture (aplay -l)": _sous_commande(["aplay", "-l"]),
    }


def collecter() -> dict[str, Any]:
    """Rassembler TOUS les indicateurs (lecture seule, sans exception)."""
    mem = _meminfo()
    try:
        distribution = platform.freedesktop_os_release().get("PRETTY_NAME")
    except (OSError, AttributeError):
        # Absent sous Windows : on n'exige aucun fichier système externe.
        distribution = platform.platform()
    return {
        "systeme": {
            "OS": f"{platform.system()} {platform.release()}",
            "distribution": distribution,
            "architecture": platform.machine(),
            "python": sys.version.split()[0],
        },
        "cpu": _cpu(),
        "ram": {
            "totale": mem.get("MemTotal", "?"),
            "disponible": mem.get("MemAvailable", "?"),
        },
        "disque": _disque(),
        "gpu": _gpu() or "non détecté (nvidia-smi absent)",
        "audio": _audio(),
        "ports_en_ecoute": _ports_ecoutes() or ["non lisible hors Linux"],
    }


def formater(rapport: dict[str, Any]) -> str:
    """Formater le rapport pour un humain (lisible au terminal)."""
    lignes = ["=" * 56, " PREFLIGHT BOÎTIER MILES (lecture seule)", "=" * 56]
    for section, contenu in rapport.items():
        lignes.append(f"\n[{section}]")
        if isinstance(contenu, dict):
            for cle, valeur in contenu.items():
                lignes.append(f"  {cle} : {valeur}")
        elif isinstance(contenu, list):
            lignes.append(f"  {', '.join(map(str, contenu))}")
        else:
            lignes.append(f"  {contenu}")
    lignes.append("\nAucun fichier modifié, aucune installation, aucun réseau.")
    return "\n".join(lignes)


def main() -> int:
    print(formater(collecter()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
