#!/usr/bin/env bash
F=/root/initrd-inspect/usr/lib/live/boot/9990-misc-helpers.sh
G=/root/initrd-inspect/usr/lib/live/boot/9990-overlay.sh

echo "=== find_persistence_media ==="
awk '/^find_persistence_media\(\)/,/^}/' "$F"
echo
echo "=== get persistence (match label) : extrait autour de PERSISTENCE_LABEL ==="
grep -n "PERSISTENCE_LABEL\|persistence_label\|grep -i persistence" "$F" | head -30
echo
echo "=== 9990-overlay.sh : appel persistence ==="
grep -n -E "persistence|PERSISTENCE|union" "$G" | head -40
echo
echo "=== 9990-main.sh : declencheur ==="
grep -n -E "persistence|PERSISTENCE" /root/initrd-inspect/usr/lib/live/boot/9990-main.sh | head -30
