#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"
K="6.12.117+deb13-amd64"
mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
mount --bind /sys "$ROOTFS/sys" 2>/dev/null || true
mount --bind /dev "$ROOTFS/dev" 2>/dev/null || true
mount --bind /dev/pts "$ROOTFS/dev/pts" 2>/dev/null || true

echo "=== apt clean ==="
chroot "$ROOTFS" bash -c 'export DEBIAN_FRONTEND=noninteractive; apt-get clean; rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb'
echo "OK"
echo "=== update-initramfs ==="
chroot "$ROOTFS" update-initramfs -u -k "$K"
echo "EXIT=$?"
ls -la "$ROOTFS/boot/" | tail -6
