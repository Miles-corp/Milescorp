#!/usr/bin/env bash
set -e
REL="/mnt/c/Users/StanC/Desktop/Milescorp/releases"
SRC="/root/live-build/miles-debian13-live.iso"
NEW="$REL/miles-debian13-live-20261124.iso"

mkdir -p "$REL"
echo "=== copie vers releases/ ==="
cp -f "$SRC" "$NEW"
ls -la "$REL"

echo
echo "=== empreintes SHA-256 ==="
cd "$REL"
sha256sum "miles-debian13-live-20261124.iso" > SHA256-ISO-SUMS
# conserve aussi l'empreinte du squashfs pour diagnostic
if [ -f /root/live-build/miles.squashfs ]; then
  sha256sum /root/live-build/miles.squashfs >> SHA256-ISO-SUMS
fi
cat SHA256-ISO-SUMS

echo
echo "=== ancienne image (obsolete) ==="
if [ -f "$REL/miles-debian13-live.iso" ]; then
  rm -f "$REL/miles-debian13-live.iso"
  echo "supprime: releases/miles-debian13-live.iso"
fi
ls -la "$REL"
