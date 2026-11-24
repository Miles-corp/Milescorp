#!/usr/bin/env python3
"""Test du chemin 'cle USB' : l'ISO ecrit sur un disque, monte comme peripherique
de stockage USB (pas en -cdrom). C'est ce que fera le vrai material."""
import os, re, shutil, socket, subprocess, time

ISO = "/root/live-build/miles-debian13-live.iso"
IMG = "/root/usb-sim.img"
T = "/root/qtest-usb"
SER = "/tmp/miles-usb.ser"
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
LOG = os.path.join(T, "serial.log")

# copie ISO -> disque simule
shutil.copyfile(ISO, IMG)
print("disque simule:", os.path.getsize(IMG), "octets")

subprocess.run("pkill -f miles-usb.ser", shell=True)
try: os.unlink(SER)
except FileNotFoundError: pass

cmd = ["qemu-system-x86_64", "-machine", "q35", "-m", "2048", "-smp", "2",
       "-display", "none",
       "-serial", f"unix:{SER},server=on,wait=off",
       "-monitor", f"unix:{T}/mon.sock,server=on,wait=off",
       "-netdev", "user,id=n0", "-device", "virtio-net-pci,netdev=n0",
       "-drive", f"file={IMG},format=raw,if=none,id=usbdisk,cache=none",
       "-device", "qemu-xhci,id=xhci",
       "-device", "usb-storage,drive=usbdisk,bus=xhci.0"]
varsf = os.path.join(T, "OVMF_VARS.fd")
shutil.copy("/usr/share/OVMF/OVMF_VARS_4M.fd", varsf)
cmd += ["-drive", "if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
        "-drive", f"if=pflash,format=raw,unit=1,file={varsf}"]

print(" ".join(cmd))
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

t0 = time.time()
ok = False
while time.time() - t0 < 300:
    pump(5)
    t = text()
    if "miles@" in t:
        ok = True; break
    if "GRUB" in t or "GNU GRUB" in t:
        print(f"[{int(time.time()-t0)}s] menu GRUB atteint")
print(f"[{int(time.time()-t0)}s] session atteinte: {ok}")

# derniere trace utile
tail = text()
print("---- dernieres lignes ----")
print(tail[-2500:])

if ok:
    def sh(c, wait=12):
        mark = f"__U{int(time.time()*1000)%100000}__"
        s.sendall((c + f"; echo {mark}\n").encode())
        pump(wait)
        parts = text().split(mark)
        return parts[-2][-3000:] if len(parts) > 1 else ""
    print("### boot source / montage")
    print(sh("cat /proc/cmdline; mount | grep -E 'squash|overlay|persistence' | head -4"))
    print("### disques")
    print(sh("lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT | head -10"))
    print("### services")
    print(sh("sudo systemctl is-active miles miles-companion"))

p.terminate(); time.sleep(3)
if p.poll() is None: p.kill()
print("log:", LOG)
