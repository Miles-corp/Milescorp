#!/usr/bin/env bash
STAGE="/root/live-build-iso/iso"
echo "=== isolinux.cfg ==="
cat "$STAGE/isolinux/isolinux.cfg" 2>/dev/null
echo
echo "=== timer.cfg / autre ==="
ls "$STAGE/isolinux/"
echo
echo "=== grub.cfg ==="
cat "$STAGE/boot/grub/grub.cfg" 2>/dev/null | head -40
