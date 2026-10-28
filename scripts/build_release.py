#!/usr/bin/env python3
"""Génère les archives de téléchargement des paquets matériels (MILES).

Contrat :
- lecture seule des sources ; écriture UNIQUEMENT dans `releases/` ;
- une archive par paquet : `releases/miles-<paquet>-<date>.tar.gz` ;
- `releases/SHA256SUMS` pour vérifier l'intégrité du téléchargement ;
- aucun secret dans les archives (`.env`, clés et identifiants WiFi
  des `build_flags` ne sont JAMAIS copiés — seuls les `.example` le sont).

Usage : python3 scripts/build_release.py
"""

from __future__ import annotations

import hashlib
import os
import tarfile
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PAQUETIER = RACINE / "hardware" / "packages"
RELEASES = RACINE / "releases"

#: Fichiers JAMAIS inclus dans les archives (secrets).
EXCLUS = (
    ".env",
    "auth.json",
    "*.pem", "*.key",
    "box_state.json",
    ".pio/", "__pycache__/",
)


def exclure(nom: str) -> bool:
    for motif in EXCLUS:
        if nom.endswith(motif) or ("/" + motif) in "/" + nom:
            return True
    # Identifiants WiFi dans les .ini : on n'archive que la version vierge.
    if nom.endswith(".ini.local"):
        return True
    return False


def construire_archive(nom_paquet: str, dossier: Path) -> Path:
    """Créer `releases/miles-<nom>-<date>.tar.gz` et retourner son chemin."""
    RELEASES.mkdir(exist_ok=True)
    sortie = RELEASES / f"miles-{nom_paquet}-{date.today().isoformat()}.tar.gz"
    with tarfile.open(sortie, "w:gz") as tar:
        for chemin in sorted(dossier.rglob("*")):
            relatif = chemin.relative_to(dossier.parent)
            if exclure(str(relatif)):
                continue
            tar.add(chemin, arcname=str(relatif))
    return sortie


def sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as fh:
        for bloc in iter(lambda: fh.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


def main() -> int:
    paquets = sorted(p for p in PAQUETIER.iterdir() if p.is_dir())
    if not paquets:
        print("Aucun paquet trouvé dans hardware/packages/")
        return 1
    sommes = []
    for dossier in paquets:
        archive = construire_archive(dossier.name, dossier)
        digest = sha256(archive)
        sommes.append(f"{digest}  {archive.name}")
        print(f"{archive.name}  {archive.stat().st_size} octets  sha256={digest[:16]}…")
    RELEASES.mkdir(exist_ok=True)
    with (RELEASES / "SHA256SUMS").open("w", encoding="utf-8") as fh:
        fh.write("\n".join(sommes) + "\n")
    print("SHA256SUMS écrit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
