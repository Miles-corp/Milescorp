#!/usr/bin/env python3
"""Test decisif : le contenu de l'ecran vient-il bien de tty1 ?"""
import os, re, shutil, socket, struct, subprocess, time, zlib

ISO = "/root/live-build/miles-debian13-live.iso"
T = "/root/qtest-d2"
SER = "/tmp/miles-d2.ser"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
LOG = os.path.join(T, "serial.log")
subprocess.run("pkill -f miles-d2.ser", shell=True)
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
                buf += d; open(LOG, "wb").write(buf)
        except socket.timeout: pass

def text():
    t = buf.decode("utf8", "replace")
    t = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", t)
    t = re.sub(r"\x1b[()][AB0]", "", t)
    return t.replace("\r", "")

def sh(c, wait=15):
    mark = f"__S{int(time.time()*1000)%100000}__"
    s.sendall((c + f"; echo {mark}\n").encode())
    pump(wait)
    parts = text().split(mark)
    return parts[-2][-5000:] if len(parts) > 1 else ""

t0 = time.time()
while time.time() - t0 < 300:
    pump(5)
    if "miles@" in text(): break
print(f"[{int(time.time()-t0)}s] session")
time.sleep(5)

print("### processus miles.py")
print(sh("ps -eo pid,tty,args | grep '[m]iles.py'"))
print("### tty reel du process")
print(sh("PID=$(pgrep -f 'python3 miles.py$' | tail -1); echo pid=$PID; awk '{print \"tty_nr=\" $7}' /proc/$PID/stat; ls -l /proc/$PID/fd/0 2>&1"))
print("### getty")
print(sh("ps -ef | grep -E '[a]getty|[l]ogin' | head -10; echo '(fin)'"))
print("### ecriture marqueur sur tty1")
print(sh("sudo sh -c 'printf \"\\nMARQUEUR-TTY1-OK\\n\" > /dev/tty1'; echo rc=$?"))
time.sleep(3)

def dump(name):
    mon = socket.socket(socket.AF_UNIX); mon.settimeout(5)
    mon.connect(f"{T}/mon.sock")
    ppm = os.path.join(T, name + ".ppm")
    mon.sendall(f"screendump {ppm}\n".encode()); time.sleep(2)
    try: mon.recv(65536)
    except socket.timeout: pass
    mon.close()
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
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))
    open(os.path.join(T, name + ".png"), "wb").write(png)
    print(f"capture {name}: {w}x{h}")

dump("apres-marqueur")
print("### redessiner tty1 (chvt 2 puis 1)")
print(sh("sudo chvt 2; sleep 1; sudo chvt 1; echo rc=$?"))
time.sleep(3)
dump("apres-chvt")
p.terminate(); time.sleep(3)
if p.poll() is None: p.kill()
print("dossier:", T)
