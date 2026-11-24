#!/usr/bin/env python3
"""Test de la persistance : 1er boot -> fichier cree -> reboot -> fichier toujours present."""
import os, socket, subprocess, sys, time, shutil, re

ISO = '/root/live-build/miles-debian13-live.iso'
PIMG = '/root/persistence.img'
T = '/root/qtest-persist'
SER = '/tmp/miles-persist.ser'
shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
LOG = os.path.join(T, 'serial.log')

# --- image persistance : toujours reecrite + persistence.conf verifie ---
print("creation de l image persistance...")
subprocess.run(f'rm -f {PIMG}', shell=True)
subprocess.run(f'dd if=/dev/zero of={PIMG} bs=1M count=384 status=none', shell=True, check=True)
subprocess.run(f'mkfs.ext4 -F -L persistence -q {PIMG}', shell=True, check=True)
os.makedirs('/tmp/persist-mnt', exist_ok=True)
subprocess.run('umount /tmp/persist-mnt 2>/dev/null || true', shell=True)
subprocess.run(f'mount -o loop {PIMG} /tmp/persist-mnt', shell=True, check=True)
open('/tmp/persist-mnt/persistence.conf', 'w').write('/ union\n')
subprocess.run('sync; umount /tmp/persist-mnt', shell=True, check=True)
# verification post-ecriture
subprocess.run(f'mount -o loop {PIMG} /tmp/persist-mnt', shell=True, check=True)
conf = open('/tmp/persist-mnt/persistence.conf').read().strip()
subprocess.run('umount /tmp/persist-mnt', shell=True, check=True)
print('persistence.conf =', repr(conf))
assert conf == '/ union', 'persistence.conf absent ou invalide'
print('image OK')

subprocess.run('pkill -f miles-persist.ser', shell=True)
try: os.unlink(SER)
except FileNotFoundError: pass

cmd = ['qemu-system-x86_64', '-machine', 'q35', '-m', '2048', '-smp', '2',
       '-display', 'none',
       '-serial', f'unix:{SER},server=on,wait=off',
       '-netdev', 'user,id=n0', '-device', 'virtio-net-pci,netdev=n0',
       '-drive', f'file={PIMG},format=raw,if=virtio',
       '-cdrom', ISO]
varsf = os.path.join(T, 'OVMF_VARS.fd')
shutil.copy('/usr/share/OVMF/OVMF_VARS_4M.fd', varsf)
cmd += ['-drive', 'if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
        '-drive', f'if=pflash,format=raw,unit=1,file={varsf}']

p = subprocess.Popen(cmd, stdout=open(os.path.join(T, 'qemu.out'), 'w'), stderr=subprocess.STDOUT)
print('pid:', p.pid)

s = socket.socket(socket.AF_UNIX)
for _ in range(40):
    try: s.connect(SER); break
    except OSError: time.sleep(1)
s.settimeout(4)
buf = b''

def pump(sec):
    global buf
    end = time.time() + sec
    while time.time() < end:
        try:
            d = s.recv(65536)
            if d:
                buf += d
                open(LOG, 'wb').write(buf)
        except socket.timeout:
            pass

def text():
    t = buf.decode('utf8', 'replace')
    t = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', t)
    t = re.sub(r'\x1b[()][AB0]', '', t)
    return t.replace('\r', '')

def wait_prompt(timeout=300, from_len=0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        pump(5)
        t = text()[from_len:]
        if 'miles@' in t:
            return True
    return False

def sh(c, wait=12):
    # nouvelle tentative si la sortie n'est pas capturee (getty peut
    # avaler les premieres commandes envoyees trop tot)
    for _ in range(3):
        mark = f'__E{int(time.time()*1000)%100000}__'
        s.sendall((c + f'; echo {mark}\n').encode())
        pump(wait)
        t = text()
        parts = t.split(mark)
        if len(parts) > 1:
            return parts[-2][-3000:]
        time.sleep(2)
    return '<SORTIE NON CAPTUREE>'

print('--- boot 1 ---')
if not wait_prompt():
    print('ECHEC boot 1'); print(text()[-2500:]); p.kill(); sys.exit(1)

print('### montages persistance')
print(sh('cat /proc/cmdline', 8))
print(sh('mount | grep -E "persistence|overlay|squash" | head -6', 10))
print('### lsblk')
print(sh('lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT', 8))
print('### creation du fichier')
print(sh('echo "persistance-ok-$(date +%s)" > ~/persistance-test.txt && cat ~/persistance-test.txt && sync', 8))
print('### reboot')
# longueur du texte NETTOYE (les sequences d'echappement sont retirees :
# decaler sur len(buf) brut tronquerait la fin et ferait rater le prompt)
clean_len = len(text())
s.sendall(b'sync; sudo reboot\n')
time.sleep(5)
pump(30)

# attendre que le SHELL soit reellement pret : on envoie un marqueur
# jusqu'a ce qu'il soit renvoye (un simple 'miles@' peut apparaitre
# trop tot, getty ayant deja avale la commande)
def wait_shell(timeout=300):
    t0 = time.time()
    m = '__RDY__'
    while time.time() - t0 < timeout:
        s.sendall(f'echo {m}\n'.encode())
        pump(4)
        if m in text()[clean_len:]:
            return True
    return False

if not wait_shell():
    print('ECHEC boot 2'); print(text()[-2500:]); p.kill(); sys.exit(1)
print('--- boot 2 ---')
print('### fichier toujours la ? (apres reboot)')
print(sh('cat ~/persistance-test.txt 2>&1 || echo ABSENT', 10))
print('### montages au 2e boot')
print(sh('mount | grep -E "persistence|overlay" | head -6', 10))
print('### services au 2e boot')
print(sh('sudo systemctl is-active miles miles-companion', 10))

shutil.copy(LOG, os.path.join(T, 'serial-final.log'))
p.terminate(); time.sleep(3)
if p.poll() is None: p.kill()
print('log:', LOG)
