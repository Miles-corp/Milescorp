#!/usr/bin/env bash
# MILES — script late_command (1er passage de l'installateur Debian).
#
# Contrat : s'exécute dans l'environnement de l'installateur, /target monté.
# - copie la payload + le script de provision + l'unité systemd ;
# - active miles-provision.service au 1er boot (symlink manuel, pas de
#   systemctl dans le chroot) ;
# - restreint SSH à 127.0.0.1 (sécurité : pas d'écoute 0.0.0.0) ;
# - journalise tout dans /target/var/log/miles-late.log ;
# - crée le marqueur /target/var/lib/miles-late-ran (preuve d'exécution).
#
# Ce script est embarqué dans l'ISO à /files/miles-late.sh et appelé par
# preseed/late_command. Il ne dépend d'aucune variable d'environnement.

set -u

LOG=/target/var/log/miles-late.log
MARK=/target/var/lib/miles-late-ran
mkdir -p /target/var/log /target/var/lib /target/opt/miles-install /target/usr/local/sbin
: > "$LOG"
exec 3>"$LOG"

echo "=== miles-late.sh debut $(date '+%Y-%m-%d %H:%M:%S') ===" >&3

# 1. Trouver la clé d'installation (montée sur l'un de ces chemins)
FOUND=""
for CDPATH in /cdrom /target/media/cdrom0 /media/cdrom0 /media/cdrom /cdrom; do
    if [ -f "$CDPATH/files/miles-provision.sh" ]; then
        FOUND="$CDPATH"
        break
    fi
done
echo "CD=$FOUND" >&3

if [ -z "$FOUND" ]; then
    echo "ERREUR : payload introuvable sur la cle d'installation" >&3
    date '+%Y-%m-%d %H:%M:%S' > "$MARK"
    echo "ERREUR" > "$MARK"
    exit 0
fi

# 2. Copier la payload, le script de provision et l'unité systemd
cp "$FOUND/files/miles-provision.sh" /target/usr/local/sbin/miles-provision 2>&3
cp "$FOUND/files/miles-provision.service" /target/etc/systemd/system/miles-provision.service 2>&3
cp "$FOUND/files/miles-source.tar.gz" /target/opt/miles-install/miles-source.tar.gz 2>&3
chmod 755 /target/usr/local/sbin/miles-provision
echo "payload + script + service copies" >&3

# 3. Activer miles-provision.service au 1er boot (symlink manuel)
mkdir -p /target/etc/systemd/system/multi-user.target.wants
ln -sf /etc/systemd/system/miles-provision.service \
    /target/etc/systemd/system/multi-user.target.wants/miles-provision.service
echo "miles-provision.service active au 1er boot" >&3

# 4. Restreindre SSH à 127.0.0.1 (sécurité : pas d'écoute 0.0.0.0)
if [ -f /target/etc/ssh/sshd_config ]; then
    if grep -q '^ListenAddress' /target/etc/ssh/sshd_config; then
        sed -i 's/^ListenAddress.*/ListenAddress 127.0.0.1/' /target/etc/ssh/sshd_config
    else
        echo "ListenAddress 127.0.0.1" >> /target/etc/ssh/sshd_config
    fi
    echo "SSH restreint a 127.0.0.1" >&3
fi

# 5. Marqueur de fin (preuve d'exécution)
date '+%Y-%m-%d %H:%M:%S' > "$MARK"
echo "OK" >> "$MARK"
echo "=== miles-late.sh fin ===" >&3

exit 0
