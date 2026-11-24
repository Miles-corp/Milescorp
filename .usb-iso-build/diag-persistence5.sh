#!/usr/bin/env bash
D=/root/initrd-inspect
echo "=== outils presents dans l initrd ==="
for t in blkid e2fsck fsck.ext4 tune2fs mount losetup udevadm; do
  found=$(find "$D" -name "$t" -type f 2>/dev/null | head -3)
  if [ -n "$found" ]; then echo "  $t : OUI -> $found"; else echo "  $t : NON"; fi
done

echo
echo "=== overlay.sh 275-420 (utilisation de overlay_devices) ==="
sed -n '275,420p' "$D/usr/lib/live/boot/9990-overlay.sh"
