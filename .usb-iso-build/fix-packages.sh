#!/usr/bin/env bash
set -u
ROOTFS="/root/live-rootfs"
mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
mount --bind /sys "$ROOTFS/sys" 2>/dev/null || true
mount --bind /dev "$ROOTFS/dev" 2>/dev/null || true
mount --bind /dev/pts "$ROOTFS/dev/pts" 2>/dev/null || true

echo "=== paquets actuellement installes (releves) ==="
chroot "$ROOTFS" dpkg-query -W -f='${Package}\n' 2>/dev/null > /tmp/pk-now.txt
for p in sudo curl ca-certificates iproute2 openssh-server openssh-client live-config live-boot locales console-setup keyboard-configuration dbus udev systemd systemd-sysv policykit-1; do
  if grep -qx "$p" /tmp/pk-now.txt; then echo "  $p : OUI"; else echo "  $p : non"; fi
done

echo "=== installation des paquets essentiels ==="
chroot "$ROOTFS" bash -c '
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C
apt-get install -y --no-install-recommends \
  sudo curl ca-certificates iproute2 net-tools procps \
  console-setup keyboard-configuration locales 2>&1 | tail -5
echo "EXIT=$?"
'

echo "=== desactivation de ssh (fail-closed) ==="
chroot "$ROOTFS" bash -c 'systemctl disable ssh ssh.service sshd 2>&1 | tail -3; systemctl is-enabled ssh 2>&1 | tail -1' || true
rm -f "$ROOTFS/etc/systemd/system/multi-user.target.wants/sshd.service"
ls -la "$ROOTFS/etc/systemd/system/multi-user.target.wants/" | head -10

echo "=== live-config et services MILES ==="
chroot "$ROOTFS" dpkg-query -W -f='${Package} ${Status}\n' live-config live-config-systemd 2>&1
ls -la "$ROOTFS/etc/systemd/system/multi-user.target.wants/" 2>/dev/null
echo "--- miles.service ---"
cat "$ROOTFS/etc/systemd/system/miles.service" 2>/dev/null | head -30
