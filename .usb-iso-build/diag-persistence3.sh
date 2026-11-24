#!/usr/bin/env bash
D=/root/initrd-inspect/usr/lib/live/boot
echo "=== definition de find_persistence_media ==="
grep -rn "find_persistence_media" "$D" | head
echo
echo "=== overlay.sh 195-275 ==="
sed -n '195,275p' "$D/9990-overlay.sh"
echo
echo "=== corps de find_persistence_media (si definie ailleurs) ==="
for f in "$D"/*; do
  if grep -q "^find_persistence_media" "$f" 2>/dev/null; then
    echo "--- $f ---"
    awk '/^find_persistence_media/,/^}/' "$f"
  fi
done
