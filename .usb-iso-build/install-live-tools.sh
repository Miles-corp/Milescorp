#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get install -y debootstrap live-boot live-boot-initramfs-tools live-config live-config-systemd linux-image-amd64 2>&1 | tail -8
echo "EXIT=$?"
command -v debootstrap && debootstrap --version 2>&1 | head -1
command -v mksquashfs && mksquashfs -version 2>&1 | head -1
