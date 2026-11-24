#!/usr/bin/env python3
"""Test complet de l'ISO live MILES.

Boot UEFI ou BIOS, attend l'autoconnexion, verifie les services, les ports,
l'auto-demarrage de MILES sur tty1 (marqueur + process + capture d'ecran).

Usage : python3 test-live3.py [uefi|bios]
"""
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib

MODE = sys.argv[1] if len(sys.argv) > 1 else "uefi"
ISO = "/root/live-build/miles-debian13-live.iso"
T = "/root/qtest-live"
SER = "/tmp/miles-test.ser"
PPM = os.path.join(T, "tty1.ppm")
PNG = os.path.join(T, "tty1.png")

shutil.rmtree(T, ignore_errors=True)
os.makedirs(T)
LOG = os.path.join(T, "serial.log")

subprocess.run("pkill -f miles-test.ser", shell=True)
try:
    os.unlink(SER)
except FileNotFoundError:
    pass

cmd = [
    "qemu-system-x86_64", "-machine", "q35", "-m", "2048", "-smp", "2",
    "-display", "none",
    "-serial", f"unix:{SER},server=on,wait=off",
    "-monitor", f"unix:{T}/mon.sock,server=on,wait=off",
    "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0",
    "-cdrom", ISO,
]
if MODE == "uefi":
    varsf = os.path.join(T, "OVMF_VARS.fd")
    shutil.copy("/usr/share/OVMF/OVMF_VARS_4M.fd", varsf)
    cmd += [
        "-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,unit=1,file={varsf}",
    ]

print("mode:", MODE)
p = subprocess.Popen(cmd, stdout=open(os.path.join(T, "qemu.out"), "w"),
                     stderr=subprocess.STDOUT)
print("pid:", p.pid)

s = socket.socket(socket.AF_UNIX)
for _ in range(40):
    try:
        s.connect(SER)
        break
    except OSError:
        time.sleep(1)
s.settimeout(4)
buf = b""


def pump(sec):
    global buf
    end = time.time() + sec
    while time.time() < end:
        try:
            d = s.recv(65536)
            if d:
                buf += d
                open(LOG, "wb").write(buf)
        except socket.timeout:
            pass


def text():
    t = buf.decode("utf8", "replace")
    t = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", t)
    t = re.sub(r"\x1b[()][AB0]", "", t)
    return t.replace("\r", "")


def sh(c, wait=12):
    mark = f"__E{int(time.time() * 1000) % 100000}__"
    s.sendall((c + f"; echo {mark}\n").encode())
    pump(wait)
    t = text()
    parts = t.split(mark)
    return parts[-2][-4000:] if len(parts) > 1 else ""


# --- attente de la session (autoconnexion) ---
t0 = time.time()
reached = False
while time.time() - t0 < 300:
    pump(5)
    if "miles@" in text():
        reached = True
        break
print(f"[{int(time.time() - t0)}s] session atteinte: {reached}")
if not reached:
    print("---- fin du log ----")
    print(text()[-3000:])
    p.kill()
    sys.exit(1)

CHECKS = [
    'echo "user=$(whoami) host=$(hostname) tty=$(tty)"',
    'echo "-- services --"; sudo systemctl is-active miles miles-companion ssh',
    'echo "-- echec global --"; systemctl --failed --no-pager --no-legend | head -5; echo "(fin)"',
    'echo "-- ecoutes --"; sudo ss -ltnp 2>/dev/null | head -10',
    'echo "-- http companion --"; curl -s -o /dev/null -w "%{http_code}\\n" --max-time 5 http://127.0.0.1:8787/',
    'echo "-- http miles --"; curl -s -o /dev/null -w "%{http_code}\\n" --max-time 5 http://127.0.0.1:8080/',
    'echo "-- auto-demarrage tty1 --"; ls -la /home/miles/.miles-autostart 2>&1 | tail -1; '
    'ps -eo pid,tty,args | grep -E "[m]iles.py" | head -3',
    'echo "-- getty fusionne tty1 --"; systemctl cat getty@tty1.service 2>/dev/null | grep -E "^# /|autologin|ExecStart" | head -10',
    'echo "-- erreurs console --"; tail -5 /home/miles/.miles-console.err 2>/dev/null || echo "(aucune)"',
    'echo "-- journal miles --"; sudo journalctl -u miles -u miles-companion -n 6 --no-pager | tail -8',
    'echo "-- clavier/locale --"; localectl status | tr -s " "; grep XKBLAYOUT /etc/default/keyboard',
    'echo "-- montage --"; mount | grep -E "squash|overlay|persistence" | head -5',
    'echo "-- ssh --"; sudo ss -ltnp 2>/dev/null | grep -c ":22" || echo "0 (ferme)"',
    'echo "-- ecrire --"; touch ~/test-ecriture.txt && echo OK',
]
for c in CHECKS:
    print("\n###", c)
    print(sh(c))

# --- capture d'ecran de tty1 (ou interface graphique) ---
try:
    # Forcer le rafraississement du buffer texte avant capture
    s.sendall(b"sudo chvt 3; sleep 1; sudo chvt 1; echo __REDRAW__\n")
    pump(8)
    mon = socket.socket(socket.AF_UNIX)
    mon.settimeout(5)
    mon.connect(f"{T}/mon.sock")
    mon.sendall(f"screendump {PPM}\n".encode())
    time.sleep(2)
    try:
        mon.recv(65536)
    except socket.timeout:
        pass
    mon.close()
    if os.path.exists(PPM) and os.path.getsize(PPM) > 1000:
        with open(PPM, "rb") as f:
            data = f.read()
        parts, i = [], 0
        while len(parts) < 4:
            while data[i:i + 1].isspace():
                i += 1
            if data[i:i + 1] == b"#":
                while data[i:i + 1] != b"\n":
                    i += 1
                continue
            j = i
            while not data[j:j + 1].isspace():
                j += 1
            parts.append(data[i:j])
            i = j
        i += 1
        w, h = int(parts[1]), int(parts[2])
        raw = data[i:i + w * h * 3]

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        rows = b"".join(b"\x00" + raw[y * w * 3:(y + 1) * w * 3] for y in range(h))
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(rows, 6))
               + chunk(b"IEND", b""))
        open(PNG, "wb").write(png)
        print(f"\ncapture ecran: {PNG} ({w}x{h}, {os.path.getsize(PNG)} o)")
    else:
        print("\ncapture ecran indisponible")
except Exception as exc:  # noqa: BLE001
    print("\ncapture ecran en echec:", exc)

shutil.copy(LOG, os.path.join(T, "serial-final.log"))
p.terminate()
time.sleep(3)
if p.poll() is None:
    p.kill()
print("\nlog:", LOG)
