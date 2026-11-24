#!/usr/bin/env bash
set -eu
D="/mnt/c/Users/StanC/Desktop/Milescorp/.usb-iso-build"
bash "$D/build-squashfs.sh"
bash "$D/build-live-iso4.sh"
echo "=== RECAP ==="
ls -la /root/live-build/live/
sha256sum /root/live-build/miles-debian13-live.iso
