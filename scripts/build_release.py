#!/usr/bin/env python3
"""Génère les archives de téléchargement des paquets matériels (MILES).

Contrat :
- lecture seule des sources ; écriture UNIQUEMENT dans `releases/` ;
- une archive par paquet : `releases/miles-<paquet>-<date>.tar.gz` ;
- `releases/SHA256SUMS` pour vérifier l'intégrité du téléchargement ;
- aucun secret dans les archives (`.env`, clés et identifiants WiFi
  des `build_flags` ne sont JAMAIS copiés — seuls les `.example` le sont) ;

**Convention obligatoire pour les fichiers de configuration personnels :**
ils doivent porter l'extension `.local` (ex. `platformio.local.ini`), exclue
par construction. Un `*.ini` ordinaire, lui, est archivé : y placer des
identifiants les ferait partir dans le livrable.

Usage : python3 scripts/build_release.py
"""

from __future__ import annotations

import fnmatch
import hashlib
import tarfile
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PAQUETIER = RACINE / "hardware" / "packages"
RELEASES = RACINE / "releases"

#: Segments de chemin jamais archivés : secrets locaux et artefacts de build.
#: Comparaison sur les SEGMENTS, jamais sur le chemin complet : un motif
#: « .pio/ » ne correspondrait ni à une entrée de dossier « .pio » ni à un
#: séparateur Windows « \\ » (défaut corrigé : les archives partaient avec
#: les artefacts de compilation et les caches Python).
SEGMENTS_EXCLUS = frozenset({".env", ".pio", "__pycache__", ".git", ".pytest_cache"})

#: Motifs de NOM jamais archivés. `*.ini.local` porte la convention : les
#: fichiers personnels (SSID, clés) finissent par `.local`, les fichiers
#: livrés (platformio.ini) n'en contiennent aucun.
MOTIFS_EXCLUS = (
    "auth.json",
    "box_state.json",
    "*.pem",
    "*.key",
    "*.ini.local",   # identifiants WiFi/backend : seule la version vierge part
)


def exclure(nom: str) -> bool:
    """Indiquer si un chemin relatif doit rester hors de l'archive.

    Indépendant du séparateur : ``a/.pio/x`` et ``a\\.pio\\x`` sont traités
    de la même façon. ``.env.example`` reste archivé (c'est un modèle, pas un
    secret) ; ``.env`` jamais.
    """
    segments = [s for s in nom.replace("\\", "/").split("/") if s]
    if any(segment in SEGMENTS_EXCLUS for segment in segments):
        return True
    return any(
        fnmatch.fnmatch(segment, motif)
        for segment in segments
        for motif in MOTIFS_EXCLUS
    )


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
