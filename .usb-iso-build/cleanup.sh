#!/usr/bin/env bash
# Nettoyage des scripts one-off du chantier Live USB.
# On ne supprime QUE ce qui n'est pas dans la liste blanche.
set -u
cd "$(dirname "$0")"

KEEP=$(cat <<'EOF'
README.md
install-live-tools.sh
debootstrap.sh
setup-live-rootfs.sh
setup-live-miles.sh
fix-packages.sh
fix-init.sh
fix-env.sh
fix-ownership.sh
gen-initrd.sh
setup-autologin.sh
setup-autostart.sh
fix-liveconfig-user.sh
build-squashfs.sh
build-live-iso4.sh
full-rebuild.sh
deliver-iso.sh
check-signature.sh
check-secureboot.sh
check-tools.sh
show-menus.sh
test-live3.py
test-usb-boot.py
test-persistence.py
diag-getty.py
diag-tty.py
diag-persistence.sh
diag-persistence2.sh
diag-persistence3.sh
diag-persistence4.sh
diag-persistence5.sh
diag-persist-boot2.py
cleanup.sh
EOF
)

deleted=0
kept=0
for f in *; do
  [ -f "$f" ] || continue
  if printf '%s\n' "$KEEP" | grep -qx "$f"; then
    kept=$((kept+1))
  else
    rm -f "$f"
    deleted=$((deleted+1))
  fi
done
echo "scripts conserves : $kept"
echo "scripts supprimes : $deleted"
echo
ls -la
