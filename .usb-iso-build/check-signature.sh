#!/usr/bin/env bash
STAGE="/root/live-build-iso/iso"
IMG="/root/usb-sim.img"

echo "=== table de partitions de l'image (chemin cle USB) ==="
fdisk -l "$IMG" 2>/dev/null || sfdisk -l "$IMG" 2>/dev/null

echo
echo "=== signature Authenticode des binaires EFI ==="
for f in "$STAGE/EFI/boot/bootx64.efi" "$STAGE/EFI/boot/grubx64.efi"; do
  echo "--- $f ---"
  if command -v sbverify >/dev/null 2>&1; then
    sbverify --list "$f" 2>&1 | head -6
  fi
  strings -n 8 "$f" 2>/dev/null | grep -i -E "microsoft corporation|debian secure boot|CN=.*CA" | head -5
done

echo
echo "=== contenu de la partition EFI (efi.img) ==="
EFIMG="$STAGE/boot/grub/efi.img"
command -v mdir >/dev/null 2>&1 && mdir -i "$EFIMG" ::/ 2>/dev/null | head -15
echo "--- sous répertoires ---"
command -v mdir >/dev/null 2>&1 && mdir -i "$EFIMG" ::/EFI 2>/dev/null | head -10

echo
echo "=== partitions : montage reel vu au boot ==="
echo "sda1 = ISO9660 (systeme live) ; sda2 = FAT 3,6 Mo = image EFI"
