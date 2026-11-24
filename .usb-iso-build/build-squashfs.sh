#!/usr/bin/env bash
set -eu
ROOTFS="/root/live-rootfs"
SQDIR="/root/live-build/live"
OUT="$SQDIR/filesystem.squashfs.new"

echo "=== umount ==="
for m in dev/pts dev sys proc; do
  umount "$ROOTFS/$m" 2>/dev/null && echo "umount $m OK" || echo "$m deja libre"
done
echo "=== restant ==="
grep "$ROOTFS" /proc/mounts || echo "aucun mount dans le rootfs"

echo "=== mksquashfs (xz, sans /boot) ==="
rm -f "$OUT"
mksquashfs "$ROOTFS" "$OUT" -comp xz -noappend -no-progress -e boot 2>&1 | tail -6
ls -la "$OUT"

echo "=== remplacement ==="
if [ -s "$OUT" ]; then
  mv "$OUT" "$SQDIR/filesystem.squashfs"
  echo "squashfs OK"
else
  echo "ECHEC: squashfs vide"
  exit 1
fi
ls -la "$SQDIR"
