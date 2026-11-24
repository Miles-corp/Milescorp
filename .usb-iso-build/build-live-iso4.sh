#!/usr/bin/env bash
set -euo pipefail
WORK="/root/live-build-iso"
ISO_OUT="/root/live-build/miles-debian13-live.iso"
SRC_ISO="/mnt/c/Users/StanC/Desktop/Milescorp/releases/miles-debian13-autoinstall-20261111.iso"
TREE="$WORK/iso"

# --- 0. arbre neuf ---
rm -rf "$WORK"
mkdir -p "$TREE/live" "$TREE/isolinux" "$TREE/boot/grub" "$TREE/EFI" "$TREE/.disk"

# --- 1. noyau, initrd (composite cpio+gzip, tel quel) et squashfs ---
# Le noyau et l'initrd sont pris directement dans le rootfs (jamais de copie figée).
cp /root/live-rootfs/boot/vmlinuz-* "$TREE/live/vmlinuz"
INITRD_SRC="$(ls -1 /root/live-rootfs/boot/initrd.img-* | sort -V | tail -1)"
cp "$INITRD_SRC" "$TREE/live/initrd.img"

# Validation obligatoire : l'initrd doit contenir /init + scripts/live dans un segment gzip valide
python3 - "$TREE/live/initrd.img" <<'PY'
import sys, zlib
d = open(sys.argv[1], 'rb').read()
pos, found = 0, False
while True:
    i = d.find(b'\x1f\x8b\x08', pos)
    if i < 0:
        break
    try:
        o = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = o.decompress(d[i:])
    except Exception:
        pos = i + 3
        continue
    if b'scripts/live' in out and b'live-boot' in out:
        found = True
        print(f"initrd: segment gzip a l'offset {i} valide ({len(out)} octets deconpresses)")
        break
    pos = i + 3
if not found:
    print("initrd INVALIDE: aucun segment gzip contenant /init + scripts/live")
    sys.exit(1)
PY

cp /root/live-build/live/filesystem.squashfs "$TREE/live/filesystem.squashfs"
echo "[1] live/: $(ls "$TREE/live" | tr '\n' ' ')"

# --- 2. fichiers de boot depuis l'ISO installateur ---
xorriso -osirrox on -dev "$SRC_ISO" -extract /isolinux "$TREE/isolinux" >/dev/null 2>&1
xorriso -osirrox on -dev "$SRC_ISO" -extract /boot/grub "$TREE/boot/grub" >/dev/null 2>&1
xorriso -osirrox on -dev "$SRC_ISO" -extract /EFI "$TREE/EFI" >/dev/null 2>&1
rm -f "$TREE/isolinux/"*.cfg "$TREE/isolinux/"*.txt
chmod -R u+w "$TREE"
echo "[2] isolinux: $(ls "$TREE/isolinux" | tr '\n' ' ')"

# --- 3. isolinux.cfg (BIOS) ---
cat > "$TREE/isolinux/isolinux.cfg" <<'CFG'
DEFAULT live
PROMPT 0
TIMEOUT 50
ONTIMEOUT live

LABEL live
  MENU LABEL Live MILES (Francais, AZERTY)
  KERNEL /live/vmlinuz
  APPEND boot=live components locales=fr_FR.UTF-8 keyboard-layouts=fr timezone=Europe/Paris persistence console=tty0 console=ttyS0,115200n8 initrd=/live/initrd.img quiet

LABEL live-text
  MENU LABEL Live MILES (mode texte)
  KERNEL /live/vmlinuz
  APPEND boot=live components locales=fr_FR.UTF-8 keyboard-layouts=fr timezone=Europe/Paris persistence console=tty0 console=ttyS0,115200n8 initrd=/live/initrd.img
CFG

# --- 4. grub.cfg (menu UEFI, sur l'ISO) ---
cat > "$TREE/boot/grub/grub.cfg" <<'CFG'
set timeout=5
set timeout_style=menu

menuentry "Live MILES (Francais, AZERTY)" {
    linux /live/vmlinuz boot=live components locales=fr_FR.UTF-8 keyboard-layouts=fr timezone=Europe/Paris persistence console=tty0 console=ttyS0,115200n8 quiet
    initrd /live/initrd.img
}

menuentry "Live MILES (mode texte)" {
    linux /live/vmlinuz boot=live components locales=fr_FR.UTF-8 keyboard-layouts=fr timezone=Europe/Paris persistence console=tty0 console=ttyS0,115200n8
    initrd /live/initrd.img
}
CFG

# --- 5. grub.cfg interne de l'image EFI : suppression du search /.disk/id/<uuid> ---
EFI_IMG="$TREE/boot/grub/efi.img"
cat > /tmp/efi-grub.cfg <<'CFG'
# MILES live - amorcage UEFI
search --file --set=root /live/vmlinuz
if [ -z "$root" ]; then
  search --file --set=root /.disk/info
fi
set prefix=($root)/boot/grub
source ($root)/boot/grub/grub.cfg
CFG
export MTOOLS_SKIP_CHECK=1
mdir -i "$EFI_IMG" ::/efi/debian >/dev/null
mcopy -o -i "$EFI_IMG" /tmp/efi-grub.cfg ::/efi/debian/grub.cfg
echo "[5] grub.cfg EFI remplace :"
mdir -i "$EFI_IMG" ::/efi/debian

# --- 6. .disk + identifiant (compatibilite outils Debian) ---
echo "Debian 13 trixie live - MILES" > "$TREE/.disk/info"
echo "live" > "$TREE/.disk/base_installable"
mkdir -p "$TREE/.disk/id"
touch "$TREE/.disk/id/19d5b690-0f60-4b5d-9755-2b7afd177e7e"
ls -la "$TREE/.disk/id/"

# --- 7. fabrication ISO hybride BIOS + UEFI ---
rm -f "$ISO_OUT"
xorriso -as mkisofs \
    -r -J -joliet-long -l \
    -V "MILES-LIVE" \
    -o "$ISO_OUT" \
    -b isolinux/isolinux.bin \
    -c isolinux/boot.cat \
    -no-emul-boot -boot-load-size 4 -boot-info-table \
    -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
    -eltorito-alt-boot -e boot/grub/efi.img -no-emul-boot \
    -isohybrid-gpt-basdat \
    -iso_mbr_part_type 0x83 \
    "$TREE" 2>&1 | tail -6

echo "[7] resultat"
ls -la "$ISO_OUT"
sha256sum "$ISO_OUT"
