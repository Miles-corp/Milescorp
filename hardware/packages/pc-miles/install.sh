#!/usr/bin/env bash
# Installation de MILES sur le mini-PC (Debian 13) — paquet pc-miles.
# Lecture seule du système : rien n'est supprimé, rien n'est réinitialisé.
set -euo pipefail

echo "=== MILES — installation du paquet PC ==="

# 1. Préflight (lecture seule)
if command -v python3 >/dev/null 2>&1; then
    python3 box_preflight.sh || echo "ATTENTION : préflight a signalé des anomalies."
else
    echo "ERREUR : python3 absent. sudo apt install python3 python3-venv"
    exit 1
fi

# 2. Clone et environnement virtuel
if [ ! -d "Milescorp" ]; then
    git clone https://github.com/Miles-corp/Milescorp.git
fi
cd Milescorp
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt 2>/dev/null || true

# 3. Configuration
if [ ! -f .env ]; then
    cp ../.env.example .env
    chmod 600 .env
    echo "ERREUR : .env créé. Éditez-le (clé API) puis relancez."
    exit 1
fi

# 4. Tests rapides (sans réseau)
python3 -m unittest discover -s tests -q

# 5. Service systemd (si demandé)
if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
    sudo cp ../miles.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now miles
    echo "Service miles démarré."
fi

echo "=== Terminé. Lancer : python3 miles.py --web ==="
