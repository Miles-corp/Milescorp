#!/usr/bin/env bash
STAGE="/root/live-build-iso/iso"
echo "=== arbre EFI ==="
find "$STAGE/EFI" -type f 2>/dev/null | head -20
echo
echo "=== shim / signature ? ==="
ls -la "$STAGE/EFI/boot/" 2>/dev/null
find "$STAGE" -iname "*shim*" -o -iname "*.efi*" 2>/dev/null | head -20
echo
echo "=== efi.img (contenu) ==="
ls -la "$STAGE/boot/grub/efi.img" 2>/dev/null
echo
echo "=== paquets shim installe dans le rootfs ? ==="
chroot /root/live-rootfs dpkg -l 'shim*' 'grub-efi*' 2>/dev/null | grep "^ii" || echo "(aucun)"
