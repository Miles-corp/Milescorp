#!/usr/bin/env bash
set -e
ISO="/root/live-build-iso/iso"
ROOTFS="/root/live-rootfs"

echo "=== 1. ligne de commande proposee par les menus ==="
echo "--- grub.cfg ---"
grep -n -E "linux|append|persistence" "$ISO/boot/grub/grub.cfg" | head -20
echo "--- isolinux (txt.cfg / isolinux.cfg) ---"
grep -rn -E "append|persistence" "$ISO/isolinux/" 2>/dev/null | head -20

echo
echo "=== 2. live-boot dans le rootfs ==="
dpkg -l live-boot live-config 2>/dev/null | tail -5 || true
ls -la "$ROOTFS/lib/live/boot/" 2>/dev/null | head -20

echo
echo "=== 3. l'initrd contient-il les scripts live/persistence ? ==="
INITRD=$(ls "$ROOTFS"/boot/initrd.img-* 2>/dev/null | head -1)
echo "initrd: $INITRD"
ls -la "$INITRD"
mkdir -p /root/initrd-inspect
cd /root/initrd-inspect
rm -rf ./* 2>/dev/null || true
lsinitramfs "$INITRD" 2>/dev/null | grep -E "live|persist" | head -30 || {
  # fallback : extraction manuelle
  echo "(lsinitramfs indisponible, extraction gzip+cpio)"
  (zcat "$INITRD" | cpio -t 2>/dev/null | grep -E "live|persist" | head -30) || true
}

echo
echo "=== 4. script live dans l'initrd : gestion persistence ? ==="
if command -v unmkinitramfs >/dev/null 2>&1; then
  unmkinitramfs "$INITRD" /root/initrd-inspect 2>/dev/null || true
  find /root/initrd-inspect -name "*misc-helpers*" -o -name "9990*" | head
fi
