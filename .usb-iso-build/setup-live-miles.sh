#!/usr/bin/env bash
set -euo pipefail
ROOTFS="/root/live-rootfs"
REPO="/mnt/c/Users/StanC/Desktop/Milescorp"

# Clean up hardware build artifacts
rm -rf "$REPO/hardware/packages/esp32-s3/.pio" 2>/dev/null || true

# Mount proc/sys/dev for chroot
mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
mount --bind /sys "$ROOTFS/sys" 2>/dev/null || true
mount --bind /dev "$ROOTFS/dev" 2>/dev/null || true
mount --bind /dev/pts "$ROOTFS/dev/pts" 2>/dev/null || true

echo "=== installing MILES into rootfs ==="
mkdir -p "$ROOTFS/opt/Milescorp"
# Copy MILES code (excluding build artifacts, .git, data, logs, etc.)
rsync -a --exclude='.git' --exclude='data' --exclude='logs' --exclude='releases' \
    --exclude='experiments' --exclude='docs/marketing' --exclude='brag-output-*' \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='node_modules' \
    --exclude='.env' --exclude='.env.*' --exclude='*.mp4' --exclude='*.wav' --exclude='*.mkv' \
    --exclude='CLIP' --exclude='dist' --exclude='docs/skills' \
    --exclude='.pio' --exclude='build-output' --exclude='.usb-iso-build' \
    "$REPO/" "$ROOTFS/opt/Milescorp/" 2>&1 | tail -3
echo "MILES code copied"

# Create venv
chroot "$ROOTFS" bash -c '
set -e
cd /opt/Milescorp
python3 -m venv .venv
echo "venv created"
' 2>&1 | tail -3

# Create data directory
mkdir -p "$ROOTFS/opt/Milescorp/data"
chown -R 1000:1000 "$ROOTFS/opt/Milescorp" 2>/dev/null || true

# Copy companion frontend build
mkdir -p "$ROOTFS/opt/Milescorp/app/interface/companion/assets"
cp -r "$REPO/app/interface/companion/assets/"* "$ROOTFS/opt/Milescorp/app/interface/companion/assets/" 2>/dev/null || true
cp "$REPO/app/interface/companion/server.py" "$ROOTFS/opt/Milescorp/app/interface/companion/" 2>/dev/null || true
cp "$REPO/app/interface/companion/miles-bridge.js" "$ROOTFS/opt/Milescorp/app/interface/companion/" 2>/dev/null || true
cp "$REPO/app/interface/companion/index.html" "$ROOTFS/opt/Milescorp/app/interface/companion/" 2>/dev/null || true
# Copy dist build
cp -r "$REPO/app/interface/companion/frontend/dist" "$ROOTFS/opt/Milescorp/app/interface/companion/" 2>/dev/null || true
echo "Companion copied"

# Create MILES systemd service
cat > "$ROOTFS/etc/systemd/system/miles.service" <<'EOF'
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
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/Milescorp/data /opt/Milescorp/.env
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Create companion systemd service
cat > "$ROOTFS/etc/systemd/system/miles-companion.service" <<'EOF'
[Unit]
Description=MILES Companion - site de controle
After=network-online.target miles.service
Wants=network-online.target

[Service]
Type=simple
User=miles
WorkingDirectory=/opt/Milescorp
ExecStart=/opt/Milescorp/.venv/bin/python -m app.interface.companion.server --port 8787
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/Milescorp/data
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Enable services and create user
chroot "$ROOTFS" bash -c '
set -e
systemctl enable miles.service 2>/dev/null || true
systemctl enable miles-companion.service 2>/dev/null || true
id miles >/dev/null 2>&1 || useradd -m -s /bin/bash miles
usermod -aG sudo miles 2>/dev/null || true
' 2>&1 | tail -3

# Create .env template (no secrets)
cat > "$ROOTFS/opt/Milescorp/.env" <<'EOF'
# MILES - configuration live (secrets a saisir via --setup)
MILES_PROVIDER=off
MILES_WEB_AUTH_TOKEN=
EOF
chown 1000:1000 "$ROOTFS/opt/Milescorp/.env" 2>/dev/null || true
chmod 600 "$ROOTFS/opt/Milescorp/.env" 2>/dev/null || true

# Create user miles home
mkdir -p "$ROOTFS/home/miles"
chown 1000:1000 "$ROOTFS/home/miles" 2>/dev/null || true

echo "=== rootfs size after MILES+Companion ==="
du -sh "$ROOTFS" 2>/dev/null
echo "=== check ==="
ls "$ROOTFS/opt/Milescorp/miles.py" 2>/dev/null && echo "miles.py OK" || echo "miles.py MANQUANT"
ls "$ROOTFS/opt/Milescorp/app/interface/companion/server.py" 2>/dev/null && echo "companion server.py OK" || echo "companion MANQUANT"
ls "$ROOTFS/opt/Milescorp/app/interface/companion/dist/index.html" 2>/dev/null && echo "companion dist OK" || echo "companion dist MANQUANT"
ls "$ROOTFS/opt/Milescorp/.venv/bin/python3" 2>/dev/null && echo "venv OK" || echo "venv MANQUANT"
