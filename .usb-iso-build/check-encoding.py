#!/usr/bin/env python3
import os
base = '/mnt/c/Users/StanC/Desktop/Milescorp/docs/coordination'
for name in ['TASKS.md', 'STATUS.md', 'HANDOFF.md', 'DECISIONS.md']:
    p = os.path.join(base, name)
    raw = open(p, 'rb').read()
    try:
        raw.decode('utf-8')
        enc = 'UTF-8 valide'
    except UnicodeDecodeError as e:
        enc = f'PAS UTF-8 ({e})'
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n')
    print(f'{name:16} {len(raw):8} octets | {enc} | CRLF={crlf} LF={lf}')
    print(f'   derniere ligne : {raw.rstrip(b"\n").splitlines()[-1][:120]}')
