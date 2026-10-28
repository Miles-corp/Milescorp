#!/usr/bin/env bash
# Préflight matériel du mini-PC — lecture seule, aucun réseau, aucune écriture.
set -euo pipefail
echo "=== Préflight matériel (lecture seule) ==="
echo "OS        : $(uname -srm)"
echo "Python    : $(python3 --version 2>&1)"
echo "Hostname  : $(hostname 2>/dev/null || echo inconnu)"
if [ -r /proc/meminfo ]; then
    grep -E 'MemTotal|MemAvailable' /proc/meminfo | sed 's/^/  /'
fi
if command -v df >/dev/null 2>&1; then
    echo "Disque    : $(df -h / | tail -1 | awk '{print $4} libres sur '$2)"
fi
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null | sed 's/^/GPU       : /'
else
    echo "GPU       : non détecté (nvidia-smi absent)"
fi
if [ -r /sys/class/hwmon ]; then
    for d in /sys/class/hwmon/hwmon*; do
        [ -r "$d/temp1_input" ] && echo "Température : $(( $(cat "$d/temp1_input") / 1000 )) °C"
        [ -r "$d/fan1_input" ] && echo "Ventilateur : $(cat "$d/fan1_input") tr/min"
    done
fi
echo "=== Terminé — aucun fichier modifié ==="
