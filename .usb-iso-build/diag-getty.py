#!/usr/bin/env python3
"""Diagnostic getty/tty1 : combien d'instances, quel ExecStart, quelles sessions."""
import os, re, shutil, socket, struct, subprocess, sys, time, zlib

ISO = "/root/live-build/miles-debian13-live.iso"
T = "/root/qtest-d1"
SER = "/tmp/miles-d1.ser"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
LOG = os.path.join(T, "serial.log")

subprocess.run("pkill -f miles-d1.ser", shell=True)
try: os.unlink(SER)
except FileNotFoundError: pass

cmd = ["qemu-system-x86_64", "-machine", "q35", "-m", "2048", "-smp", "2",
       "-display", "none",
       "-serial", f"unix:{SER},server=on,wait=off",
       "-monitor", f"unix:{T}/mon.sock,server=on,wait=off",
       "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0",
       "-cdrom", ISO]
varsf = os.path.join(T, "OVMF_VARS.fd")
shutil.copy("/usr/share/OVMF/OVMF_VARS_4M.fd", varsf)
cmd += ["-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,unit=1,file={varsf}"]

p = subprocess.Popen(cmd, stdout=open(os.path.join(T, "qemu.out"), "w"), stderr=subprocess.STDOUT)
print("pid:", p.pid)

s = socket.socket(socket.AF_UNIX)
for _ in range(40):
    try: s.connect(SER); break
    except OSError: time.sleep(1)
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
        except socket.timeout: pass

def text():
    t = buf.decode("utf8", "replace")
    t = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", t)
    t = re.sub(r"\x1b[()][AB0]", "", t)
    return t.replace("\r", "")

def sh(c, wait=15):
    mark = f"__D{int(time.time()*1000)%100000}__"
    s.sendall((c + f"; echo {mark}\n").encode())
    pump(wait)
    t = text()
    parts = t.split(mark)
    return parts[-2][-6000:] if len(parts) > 1 else ""

t0 = time.time()
while time.time() - t0 < 300:
    pump(5)
    if "miles@" in text(): break
print(f"[{int(time.time()-t0)}s] session")
time.sleep(10)  # laisser le temps a un eventuel 2e getty de s'executer

CHECKS = [
    'echo "=== getty/agetty en cours ==="; ps -eo pid,lstart,tty,args | grep -E "[a]getty|[g]etty@"',
    'echo "=== sessions ==="; loginctl list-sessions --no-legend; loginctl show-session $(loginctl list-sessions --no-legend | head -1 | cut -d" " -f1) -p Type -p TTY -p Active -p Remote 2>/dev/null',
    'echo "=== VT active ==="; cat /sys/class/tty/tty0/active; ls /sys/class/tty/tty*/active 2>/dev/null | head -3',
    'echo "=== generateur en execution ==="; cat /run/systemd/generator/getty@tty1.service.d/live-config_autologin.conf 2>&1',
    'echo "=== drop-ins etc ==="; ls -la /etc/systemd/system/getty@tty1.service.d/; cat /etc/systemd/system/getty@tty1.service.d/*.conf',
    'echo "=== journal getty@tty1 ==="; sudo journalctl -u getty@tty1 --no-pager -n 40 | tail -45',
    'echo "=== journal login (tty1) ==="; sudo journalctl -t login --no-pager -n 20 | tail -22',
    'echo "=== cmdline ==="; cat /proc/cmdline',
    'echo "=== /etc/live/config.conf ==="; cat /etc/live/config.conf 2>&1',
    'echo "=== env du process tty1 ==="; tr "\\0" " " < /proc/1118/environ 2>/dev/null | head -c 300; echo; ps -eo pid,tty,args | grep "[m]iles.py"',
]
for c in CHECKS:
    print("\n###", c)
    print(sh(c))

# capture ecran
def dump(name):
    mon = socket.socket(socket.AF_UNIX); mon.settimeout(5)
    mon.connect(f"{T}/mon.sock")
    ppm = os.path.join(T, name + ".ppm")
    mon.sendall(f"screendump {ppm}\n".encode())
    time.sleep(2)
    try: mon.recv(65536)
    except socket.timeout: pass
    mon.close()
    if os.path.exists(ppm) and os.path.getsize(ppm) > 1000:
        data = open(ppm, "rb").read()
        parts, i = [], 0
        while len(parts) < 4:
            while data[i:i+1].isspace(): i += 1
            if data[i:i+1] == b"#":
                while data[i:i+1] != b"\n": i += 1
                continue
            j = i
            while not data[j:j+1].isspace(): j += 1
            parts.append(data[i:j]); i = j
        i += 1
        w, h = int(parts[1]), int(parts[2])
        raw = data[i:i+w*h*3]
        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        rows = b"".join(b"\x00" + raw[y*w*3:(y+1)*w*3] for y in range(h))
        png = (b"\x89PNG\r\n\x1a\n"
               + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
        open(os.path.join(T, name + ".png"), "wb").write(png)
        print(f"capture {name}: {w}x{h} -> {name}.png")

dump("tty1")
p.terminate(); time.sleep(3)
if p.poll() is None: p.kill()
print("dossier:", T)
