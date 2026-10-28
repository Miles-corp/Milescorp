#!/usr/bin/env bash
# Installation de MILES sur le mini-PC (Debian 13) — paquet pc-miles.
#
# Principes :
# - lecture seule tant que rien n'est confirmé : aucun fichier supprimé,
#   aucune configuration réinitialisée ;
# - chaque étape est idempotente : relancer le script ne casse rien ;
# - aucun secret n'est écrit ici : le `.env` est copié depuis l'exemple puis
#   édité à la main (permissions 600).
#
# Variables d'environnement reconnues :
#   MILES_DIR      répertoire d'installation du dépôt (défaut : ./Milescorp)
#   MILES_REPO_URL dépôt à cloner
#   MILES_USER     utilisateur du service (défaut : miles)
#   INSTALL_SERVICE=1 pour installer et démarrer l'unité systemd
set -euo pipefail

PAQUET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CIBLE="${MILES_DIR:-$PWD/Milescorp}"
DEPOT="${MILES_REPO_URL:-https://github.com/Miles-corp/Milescorp.git}"
UTILISATEUR="${MILES_USER:-miles}"

echo "=== MILES — installation du paquet PC ==="
echo "Paquet : $PAQUET_DIR"
echo "Cible  : $CIBLE"

# 1. Prérequis
for outil in python3 git; do
    if ! command -v "$outil" >/dev/null 2>&1; then
        echo "ERREUR : $outil absent. sudo apt install -y python3 python3-venv git" >&2
        exit 1
    fi
done

# 2. Préflight matériel — lecture seule, aucun réseau.
#    C'est un script bash : il s'exécute avec bash, jamais via python3.
echo
echo "--- Préflight matériel (lecture seule) ---"
if ! bash "$PAQUET_DIR/box_preflight.sh"; then
    echo "ATTENTION : le préflight a signalé des anomalies (installation poursuivie)." >&2
fi

# 3. Récupération du code
echo
echo "--- Dépôt ---"
if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
    if ! id -u "$UTILISATEUR" >/dev/null 2>&1; then
        sudo useradd --system --create-home --shell /usr/sbin/nologin "$UTILISATEUR"
        echo "Utilisateur système '$UTILISATEUR' créé."
    fi
    sudo mkdir -p "$(dirname "$CIBLE")"
    if [ ! -d "$CIBLE/.git" ]; then
        sudo -u "$UTILISATEUR" git clone "$DEPOT" "$CIBLE"
    else
        echo "Dépôt déjà présent : $CIBLE (aucune mise à jour automatique)."
    fi
    sudo -u "$UTILISATEUR" python3 -m venv "$CIBLE/.venv"
    sudo -u "$UTILISATEUR" mkdir -p "$CIBLE/data"
else
    if [ ! -d "$CIBLE/.git" ]; then
        git clone "$DEPOT" "$CIBLE"
    else
        echo "Dépôt déjà présent : $CIBLE (aucune mise à jour automatique)."
    fi
    python3 -m venv "$CIBLE/.venv"
    mkdir -p "$CIBLE/data"
fi

# 4. Configuration : copiée depuis l'exemple DU PAQUET, jamais inventée.
echo
echo "--- Configuration ---"
if [ ! -f "$CIBLE/.env" ]; then
    if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
        sudo install -m 600 -o "$UTILISATEUR" -g "$UTILISATEUR" \
            "$PAQUET_DIR/.env.example" "$CIBLE/.env"
    else
        install -m 600 "$PAQUET_DIR/.env.example" "$CIBLE/.env"
    fi
    cat >&2 <<'MESSAGE'
ERREUR (attendue au premier lancement) : .env vient d'être créé, permissions 600.

Renseignez au minimum :
  - MILES_PROVIDER (remote ou local) et la clé API correspondante
    (MILES_REMOTE_API_KEY ou MILES_LOCAL_API_KEY) ;
  - MILES_WEB_AUTH_TOKEN, le jeton d'accès de l'interface web.

Puis relancez ce script. Aucune valeur par défaut n'est inventée ici.
MESSAGE
    exit 1
fi

# 5. Contrôles automatiques (aucun réseau requis)
echo
echo "--- Tests du dépôt ---"
(
    cd "$CIBLE"
    # shellcheck disable=SC1091
    . .venv/bin/activate
    python3 -m unittest discover -s tests -q
)

# 6. Service systemd, uniquement sur demande explicite
echo
if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
    echo "--- Service systemd ---"
    # L'unité livrée cite /opt/Milescorp : on l'adapte au répertoire réel.
    sed "s#/opt/Milescorp#$CIBLE#g" "$PAQUET_DIR/miles.service" \
        | sudo install -m 644 /dev/stdin /etc/systemd/system/miles.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now miles
    echo "Service 'miles' activé (écoute locale sur 127.0.0.1:8080)."
    echo "Journaux : journalctl -u miles -f"
else
    echo "Service non installé (relancer avec INSTALL_SERVICE=1 pour l'installer)."
fi

echo
echo "=== Terminé ==="
echo "Interface web : cd $CIBLE && . .venv/bin/activate && python3 miles.py --web"
echo "Cockpit local : bash $PAQUET_DIR/cockpit-launcher.sh"
