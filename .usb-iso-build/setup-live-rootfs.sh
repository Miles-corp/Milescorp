#!/usr/bin/env bash
set -euo pipefail
ROOTFS="/root/live-rootfs"

# Mount proc/sys/dev for chroot
mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
mount --bind /sys "$ROOTFS/sys" 2>/dev/null || true
mount --bind /dev "$ROOTFS/dev" 2>/dev/null || true
mount --bind /dev/pts "$ROOTFS/dev/pts" 2>/dev/null || true

echo "=== installing packages in chroot ==="
chroot "$ROOTFS" bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    linux-image-amd64 live-boot live-boot-initramfs-tools live-config live-config-systemd \
    python3 python3-venv git curl ca-certificates sudo systemd \
    openssh-server keyboard-configuration console-setup locales 2>&1 | tail -5
echo "=== packages installed ==="
' 
echo "EXIT=$?"

# Configure locale (French)
chroot "$ROOTFS" bash -c '
set -e
sed -i "s/^# *fr_FR.UTF-8/fr_FR.UTF-8/" /etc/locale.gen
locale-gen
echo "LANG=fr_FR.UTF-8" > /etc/locale.conf
' 2>&1 | tail -3

# Configure keyboard (AZERTY)
chroot "$ROOTFS" bash -c '
set -e
cat > /etc/default/keyboard <<KBD
XKBMODEL="pc105"
XKBLAYOUT="fr"
XKBVARIANT=""
XKBOPTIONS=""
KBD
dpkg-reconfigure -f noninteractive keyboard-configuration 2>&1 | tail -2 || true
' 2>&1 | tail -3

echo "=== rootfs size after packages ==="
du -sh "$ROOTFS" 2>/dev/null
