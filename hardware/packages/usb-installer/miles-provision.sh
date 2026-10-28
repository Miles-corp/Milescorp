#!/usr/bin/env bash
# MILES — provisionnement au PREMIER BOOT (appelé par miles-provision.service).
#
# Contrat :
# - une seule exécution (marqueur /var/lib/miles-provision.done) ;
# - n'efface rien, ne sort pas du réseau, n'écrit aucun secret ;
# - la clé API MILES n'est PAS fournie ici : elle se saisit ensuite avec
#   `sudo -u miles python3 miles.py --setup` (décision utilisateur) ;
# - journal complet dans /var/log/miles-provision.log + journalctl.

set -uo pipefail

LOG=/var/log/miles-provision.log
SRC=/opt/miles-install/miles-source.tar.gz
DEST=/opt/Milescorp
MARK=/var/lib/miles-provision.done
SERVICE_USER=miles

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== MILES provision — debut ==="

if [ -f "$MARK" ]; then
    log "Deja provisionne (marqueur present) — rien a faire."
    exit 0
fi

if [ ! -f "$SRC" ]; then
    log "ERREUR : payload absente ($SRC). Provisionnement impossible."
    exit 1
fi

# 1. Utilisateur systeme si besoin (l'utilisateur `miles` existe deja en
#    general via le preseed ; on ne le cree que s'il manque).
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    log "Creation de l'utilisateur $SERVICE_USER"
    useradd -m -s /bin/bash "$SERVICE_USER" || log "ATTENTION : useradd a echoue"
fi
usermod -aG sudo "$SERVICE_USER" 2>/dev/null || true

# 2. Depose du code
log "Depose de MILES dans $DEST"
mkdir -p "$DEST"
tar -xzf "$SRC" -C "$DEST" --strip-components=1 2>>"$LOG" \
    || tar -xzf "$SRC" -C "$DEST" 2>>"$LOG" \
    || { log "ERREUR : extraction impossible"; exit 1; }
chown -R "$SERVICE_USER:$SERVICE_USER" "$DEST"

# 3. Environnement virtuel (isolation ; MILES est zero-dependance externe)
log "Creation de l'environnement virtuel"
if [ ! -d "$DEST/.venv" ]; then
    sudo -u "$SERVICE_USER" python3 -m venv "$DEST/.venv" 2>>"$LOG" \
        || log "ATTENTION : venv indisponible (python3-venv ?)"
fi

# 4. Tests de non-regression (sans reseau, sorties simulees)
log "Execution de la suite de tests"
TESTS_STATUS="non execute"
if [ -x "$DEST/.venv/bin/python3" ]; then
    (cd "$DEST" && sudo -u "$SERVICE_USER" "$DEST/.venv/bin/python3" -m unittest discover -s tests -q >>"$LOG" 2>&1)
    TESTS_STATUS=$?
elif command -v python3 >/dev/null 2>&1; then
    (cd "$DEST" && sudo -u "$SERVICE_USER" python3 -m unittest discover -s tests -q >>"$LOG" 2>&1)
    TESTS_STATUS=$?
fi
log "Suite de tests : code retour $TESTS_STATUS (0 = OK)"

# 5. Preflight materiel (lecture seule)
log "Preflight materiel"
(cd "$DEST" && sudo -u "$SERVICE_USER" python3 scripts/box_preflight.py >>"$LOG" 2>&1) \
    || log "ATTENTION : preflight signale des anomalies (non bloquant)"

# 6. Service systemd — ecoute STRICTEMENT 127.0.0.1 (regle permanente)
log "Installation du service miles"
cat > /etc/systemd/system/miles.service <<'EOF'
[Unit]
Description=MILES - assistant personnel (interface locale)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=miles
WorkingDirectory=/opt/Milescorp
ExecStart=/opt/Milescorp/.venv/bin/python3 miles.py --web --web-port 8080
Restart=on-failure
RestartSec=5
# Durcissement : ecriture limitee a data/ ; .env ecrit uniquement par --setup
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/Milescorp/data /opt/Milescorp/.env
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

if /opt/Milescorp/.venv/bin/python3 -V >/dev/null 2>&1; then
    EXEC=/opt/Milescorp/.venv/bin/python3
else
    EXEC=/usr/bin/python3
    sed -i "s|/opt/Milescorp/.venv/bin/python3|$EXEC|" /etc/systemd/system/miles.service
fi

systemctl daemon-reload
systemctl enable miles.service >>"$LOG" 2>&1 || log "ATTENTION : enable a echoue"
systemctl restart miles.service >>"$LOG" 2>&1 || log "ATTENTION : premier demarrage en echec (normal si .env absent)"

# 7. Marqueur de fin (une seule execution)
date '+%Y-%m-%d %H:%M:%S' > "$MARK"
log "=== MILES provision — fin (tests=$TESTS_STATUS) ==="
log "Prochaine etape (sur la machine) : sudo -u miles python3 miles.py --setup"
exit 0
