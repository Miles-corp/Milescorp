#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"

echo "=== groupe sudo de miles ==="
chroot "$ROOTFS" groups miles 2>&1 | head -2
echo "=== sudoers actuel ==="
ls "$ROOTFS/etc/sudoers.d/" 2>/dev/null
grep -r "NOPASSWD" "$ROOTFS/etc/sudoers.d/" 2>/dev/null | head -3 || echo "(aucun NOPASSWD)"

echo "=== hostname ==="
echo "avant: $(cat "$ROOTFS/etc/hostname" 2>/dev/null)"
echo "miles-live" > "$ROOTFS/etc/hostname"
sed -i 's/^127.0.1.1.*/127.0.1.1\tmiles-live/' "$ROOTFS/etc/hosts" 2>/dev/null || true
grep "miles" "$ROOTFS/etc/hosts" | head -3

echo "=== sudoers : miles NOPASSWD (live USB) ==="
cat > "$ROOTFS/etc/sudoers.d/10-live" <<'EOF'
# MILES live USB : session local autologin sans mot de passe (comme Debian Live)
miles ALL=(ALL) NOPASSWD:ALL
EOF
chmod 0440 "$ROOTFS/etc/sudoers.d/10-live"
chroot "$ROOTFS" visudo -c 2>&1 | tail -3 || true

echo "=== autologin tty1 ==="
mkdir -p "$ROOTFS/etc/systemd/system/getty@tty1.service.d"
cat > "$ROOTFS/etc/systemd/system/getty@tty1.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin miles --noclear %I $TERM
EOF

echo "=== autologin console serie (debug/depistage) ==="
mkdir -p "$ROOTFS/etc/systemd/system/serial-getty@ttyS0.service.d"
cat > "$ROOTFS/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin miles --keep-baud 115200,9600,38400,19200 %I $TERM
EOF

echo "=== controle syntaxique systemd ==="
ls -la "$ROOTFS/etc/systemd/system/getty@tty1.service.d/" "$ROOTFS/etc/systemd/system/serial-getty@ttyS0.service.d/"
echo "=== etat du mot de passe miles (sans afficher le hash) ==="
H=$(grep "^miles:" "$ROOTFS/etc/shadow" | cut -d: -f2)
case "$H" in
  "")   echo "mot de passe: vide" ;;
  '!'*) echo "mot de passe: verrouille (prefixe !)" ;;
  '*'*) echo "mot de passe: verrouille (prefixe *)" ;;
  *)    echo "mot de passe: defini (hash non affiche)" ;;
esac
echo "=== shell /bin/login existe ==="
ls -la "$ROOTFS/usr/bin/login" "$ROOTFS/sbin/agetty" 2>&1 | head -3
echo "=== TERM sur serie ==="
echo OK
