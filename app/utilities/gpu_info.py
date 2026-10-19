"""Utilitaire de diagnostic GPU NVIDIA.

Lit la sortie de `nvidia-smi` pour identifier le GPU, la mémoire vidéo
disponible et le pilote/CUDA. Utilisé uniquement à des fins de diagnostic
et de documentation ; le programme fonctionne sans GPU ni sans nvidia-smi.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class GpuInfo:
    """Informations sur un GPU NVIDIA détecté."""

    name: str
    vram_total_mib: int
    vram_used_mib: int
    driver_version: str
    cuda_version: str | None
    available: bool


def detect_nvidia_gpu() -> GpuInfo | None:
    """Détecter le GPU NVIDIA via `nvidia-smi`.

    Cette fonction est en lecture seule : elle ne modifie aucun matériel
    ni aucun paramètre système. Retourne None si `nvidia-smi` est
    indisponible ou qu'aucun GPU NVIDIA n'est détecté.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if not line:
            return None
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            return None
        name = parts[0]
        vram_total = int(parts[1]) if parts[1].isdigit() else 0
        vram_used = int(parts[2]) if parts[2].isdigit() else 0
        driver = parts[3]
        cuda = _detect_cuda_version()
        return GpuInfo(
            name=name,
            vram_total_mib=vram_total,
            vram_used_mib=vram_used,
            driver_version=driver,
            cuda_version=cuda,
            available=True,
        )
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        OSError,
        ValueError,
        IndexError,
    ):
        return None


def _detect_cuda_version() -> str | None:
    """Détecter la version CUDA via la sortie de `nvidia-smi`."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if "CUDA Version:" in line:
                for part in line.split("|"):
                    if "CUDA Version:" in part:
                        return part.split("CUDA Version:")[1].strip().split()[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
