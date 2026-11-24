#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"

echo "=== 1) composants live-config creant un utilisateur ==="
grep -rln "useradd\|usermod\|chpasswd" "$ROOTFS/lib/live/config/" 2>/dev/null | head -10
echo "(fin de liste)"

echo
echo "=== 2) LIVE_USERNAME hors ecrans graphiques ==="
grep -rn "LIVE_USERNAME" "$ROOTFS/lib/live/" "$ROOTFS/usr/share/live-config/" 2>/dev/null \
  | grep -v -E "sddm|gdm|lightdm|lxdm|slim|kdm|xinit|kde|gnome|screensaver" | head -20
echo "(fin de liste)"

echo
echo "=== 3) /etc/live/config.conf ==="
cat > "$ROOTFS/etc/live/config.conf" <<'EOF'
# Configuration live-mode MILES.
# LIVE_USERNAME doit designer le compte reel de l'image : par defaut
# live-config utilise "user" (inexistant ici) et son generateur ecrase
# notre autologin tty1 avec un compte qui n'existe pas.
LIVE_USERNAME="miles"
EOF
chmod 0644 "$ROOTFS/etc/live/config.conf"
cat "$ROOTFS/etc/live/config.conf"

echo
echo "=== 4) test reel du generateur (chroot + faux /proc/cmdline) ==="
echo "boot=live components" > "$ROOTFS/proc/cmdline"
rm -rf "$ROOTFS/tmp/gen-test"
mkdir -p "$ROOTFS/tmp/gen-test"
chroot "$ROOTFS" sh -c '. /usr/lib/live/init-config.sh; echo "LIVE_USERNAME resolu = ${LIVE_USERNAME}"'
chroot "$ROOTFS" sh -c '/usr/lib/systemd/system-generators/live-config-getty-generator /tmp/gen-test; echo "rc=$?"'
echo "--- fichiers generes ---"
find "$ROOTFS/tmp/gen-test" -type f
echo "--- getty@tty1 ---"
cat "$ROOTFS/tmp/gen-test/getty@tty1.service.d/"*.conf 2>/dev/null
echo "--- getty@tty6 ---"
cat "$ROOTFS/tmp/gen-test/getty@tty6.service.d/"*.conf 2>/dev/null
rm -f "$ROOTFS/proc/cmdline"
rm -rf "$ROOTFS/tmp/gen-test"
echo "nettoyage fait (faux cmdline + sortie generateur supprimes)"
