#!/usr/bin/env bash
set -euo pipefail
ROOTFS="/root/live-rootfs"
rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"
echo "=== debootstrap trixie (minimal) ==="
debootstrap --arch=amd64 --variant=minbase trixie "$ROOTFS" http://deb.debian.org/debian 2>&1 | tail -5
echo "EXIT=$?"
echo "=== rootfs size ==="
du -sh "$ROOTFS" 2>/dev/null
echo "=== basic check ==="
ls "$ROOTFS/bin" | head -3
cat "$ROOTFS/etc/os-release" 2>/dev/null | head -3
