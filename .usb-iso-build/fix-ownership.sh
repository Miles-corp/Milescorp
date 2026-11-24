#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"

echo "=== uid/gid de miles dans le rootfs ==="
grep "^miles:" "$ROOTFS/etc/passwd" "$ROOTFS/etc/group"

echo "=== uid numerique du proprietaire WSL courant ==="
id -u; id -g

echo "=== appartenances /opt/Milescorp (numeriques) ==="
ls -ln "$ROOTFS/opt/Milescorp/.env" "$ROOTFS/opt/Milescorp/data" 2>&1 | head -6
ls -ln "$ROOTFS/opt/Milescorp" | head -12

echo "=== correction ownership -> miles (1000:1000) ==="
chown -R 1000:1000 "$ROOTFS/opt/Milescorp"
ls -ln "$ROOTFS/opt/Milescorp/.env"
ls -ldn "$ROOTFS/opt/Milescorp/data"
chmod 0600 "$ROOTFS/opt/Milescorp/.env"

echo "=== ownership global anormal (uid != 0 et != 1000) ==="
find "$ROOTFS" -xdev \( -not -uid 0 \) -not -uid 1000 2>/dev/null | head -15
echo "(fin de la liste)"

echo "=== .env : providers ==="
grep "^MILES_PROVIDER" "$ROOTFS/opt/Milescorp/.env"
