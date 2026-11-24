#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"
HOME_D="$ROOTFS/home/miles"

echo "=== fichiers du home miles ==="
ls -la "$HOME_D" | head -20

echo "=== .profile existant ? ==="
for f in .profile .bash_profile .bashrc .bash_login; do
  if [ -f "$HOME_D/$f" ]; then echo "--- $f ---"; cat "$HOME_D/$f"; fi
done

echo "=== creation du lanceur MILES (auto-demarrage tty1) ==="
cat > "$HOME_D/.bash_profile" <<'EOF'
# MILES live USB — session console (profil de connexion bash)
[ -f /etc/profile ] && . /etc/profile
[ -f "$HOME/.profile" ] && . "$HOME/.profile"

# Auto-demarrage de MILES uniquement sur la console principale (tty1),
# jamais sur la console serie utilisee pour le diagnostic.
if [ -t 0 ] && [ -t 1 ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ] && [ -z "${MILES_NO_AUTOSTART:-}" ]; then
    cd /opt/Milescorp 2>/dev/null || exit 0
    echo "======================================================================"
    echo "  MILES live — assistant personnel (Debian 13, clavier AZERTY)"
    echo "----------------------------------------------------------------------"
    echo "  * MILES demarre automatiquement ci-dessous."
    echo "  * Apres sortie de MILES : 'miles' pour relancer,"
    echo "    'miles --setup' pour renseigner la cle IA (persiste sur la cle)."
    echo "  * Services locaux : http://127.0.0.1:8080 (interface web)"
    echo "                      http://127.0.0.1:8787 (Companion)"
    echo "  * shell : tapez 'exit' puis 'bash' (ou Ctrl+D dans MILES)."
    echo "======================================================================"
    echo
    touch "$HOME/.miles-autostart" 2>/dev/null
    /opt/Milescorp/.venv/bin/python3 miles.py 2>"$HOME/.miles-console.err"
    rc=$?
    echo
    echo "[MILES s'est arrete (code $rc). Entrez 'miles' pour le relancer.]"
    [ -s "$HOME/.miles-console.err" ] && { echo "--- dernieres erreurs ---"; tail -5 "$HOME/.miles-console.err"; }
fi
EOF
chmod 0644 "$HOME_D/.bash_profile"
chown 1000:1000 "$HOME_D/.bash_profile"

echo "=== commande 'miles' ==="
cat > "$ROOTFS/usr/local/bin/miles" <<'EOF'
#!/bin/sh
# Lanceur MILES (live USB / Debian)
cd /opt/Milescorp || exit 1
exec /opt/Milescorp/.venv/bin/python3 miles.py "$@"
EOF
chmod 0755 "$ROOTFS/usr/local/bin/miles"
chown 0:0 "$ROOTFS/usr/local/bin/miles"

echo "=== message d'accueil (MOTD) ==="
cat > "$ROOTFS/etc/motd" <<'EOF'
Bienvenue sur MILES live (Debian 13, AZERTY).
  - La console principale (tty1) demarre MILES automatiquement.
  - 'miles'              : relancer MILES dans le terminal
  - 'miles --setup'      : configurer le fournisseur IA et sa cle
  - 'systemctl status miles miles-companion' : etat des services
  - http://127.0.0.1:8080 (web) et http://127.0.0.1:8787 (Companion)
  - sudo pour les droits administrateur (sans mot de passe sur cette cle).
EOF

echo "=== nettoyage des restes de chroot ==="
rm -rf "$ROOTFS/run/"* "$ROOTFS/tmp/"* "$ROOTFS/var/tmp/"* 2>/dev/null
ls -la "$ROOTFS/run" "$ROOTFS/tmp" | head -10

echo "=== verification syntaxique .bash_profile ==="
bash -n "$HOME_D/.bash_profile" && echo "syntaxe OK"
sh -n "$ROOTFS/usr/local/bin/miles" && echo "lanceur OK"
