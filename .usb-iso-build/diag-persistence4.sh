#!/usr/bin/env bash
D=/root/initrd-inspect/usr/lib/live/boot
F="$D/9990-misc-helpers.sh"

echo "=== storage_devices ==="
awk '/^storage_devices/,/^}/' "$F"
echo
echo "=== probe_for_fs_label ==="
awk '/^probe_for_fs_label/,/^}/' "$F"
echo
echo "=== custom_overlay_label / valeurs par defaut ==="
grep -rn "custom_overlay_label" "$D" | head -10
echo
echo "=== 0001-init-vars.sh (defauts) ==="
cat "$D/0001-init-vars.sh"
echo
echo "=== defauts PERSISTENCE_* (9990-cmdline-old) ==="
grep -n "PERSISTENCE_STORAGE=\|PERSISTENCE_ENCRYPTION=\|PERSISTENCE_METHOD=\|PERSISTENCE_MEDIA=\|custom_overlay_label=" "$D/9990-cmdline-old" | head -20
