#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"

echo "=== montage des pseudo-systèmes ==="
mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
mount --bind /sys "$ROOTFS/sys" 2>/dev/null || true
mount --bind /dev "$ROOTFS/dev" 2>/dev/null || true
mount --bind /dev/pts "$ROOTFS/dev/pts" 2>/dev/null || true
cp -f /etc/resolv.conf "$ROOTFS/etc/resolv.conf" 2>/dev/null || true

echo "=== miroirs apt du rootfs ==="
grep -v "^#" "$ROOTFS/etc/apt/sources.list" 2>/dev/null | grep -v "^$" | head -5
ls "$ROOTFS/etc/apt/sources.list.d/" 2>/dev/null

echo "=== installation systemd-sysv + dependances ==="
chroot "$ROOTFS" bash -c '
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C
apt-get update -qq 2>&1 | tail -3
apt-get install -y --no-install-recommends systemd-sysv udev dbus kmod 2>&1 | tail -8
echo "EXIT=$?"
'

echo "=== verification /sbin/init ==="
ls -la "$ROOTFS/sbin/init" "$ROOTFS/usr/sbin/init" 2>&1 | head -5

echo "=== paquets systemd installe ==="
chroot "$ROOTFS" dpkg-query -W -f='${Package} ${Version}\n' systemd systemd-sysv udev dbus 2>&1 | head -10
