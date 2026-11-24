#!/usr/bin/env python3
import re
p = '/root/qtest-persist/serial-final.log'
d = open(p, 'rb').read().decode('utf8', 'replace')
d = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', d)
d = re.sub(r'\x1b[()][AB0]', '', d)
d = d.replace('\r', '')
i = d.find('--- boot 2 ---')
print('taille log:', len(d), '| index boot2:', i)
if i < 0:
    # localise le 2e autologin pour afficher tout ce qui suit
    first = d.find('login: miles')
    second = d.find('login: miles', first + 1) if first >= 0 else -1
    i = second if second >= 0 else max(0, len(d) - 8000)
print(d[i:])
