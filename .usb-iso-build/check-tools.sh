#!/usr/bin/env bash
ROOTFS="/root/live-rootfs"
echo "=== outils presents dans l'image live ==="
for t in fdisk sfdisk cfdisk partprobe partx lsblk mkfs.ext4 mke2fs tune2fs mount umount curl wget git vim nano htop; do
  p=$(command -v "$t" 2>/dev/null || true)
  if [ -z "$p" ]; then
    # recherche dans le rootfs
    if [ -x "$ROOTFS/usr/sbin/$t" ]; then p="$ROOTFS/usr/sbin/$t";
    elif [ -x "$ROOTFS/sbin/$t" ]; then p="$ROOTFS/sbin/$t";
    elif [ -x "$ROOTFS/usr/bin/$t" ]; then p="$ROOTFS/usr/bin/$t"; fi
  fi
  if [ -n "$p" ]; then echo "  $t : OUI"; else echo "  $t : NON"; fi
done
echo
echo "=== persistence : live-boot accepte-t-il un fichier ? ==="
B="$ROOTFS/usr/lib/live/boot"
grep -n "PERSISTENCE" "$B/9990-misc-helpers.sh" | head -15
echo "--- find_persistence_media (extrait) ---"
awk '/^find_persistence_media/,/^}/' "$B/9990-misc-helpers.sh" | head -50
