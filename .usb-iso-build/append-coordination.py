#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append des entrees Agent A dans les documents de coordination.
Les fichiers existants sont UTF-8 + CRLF : on append en bytes, sans re-encodage."""
import os

BASE = '/mnt/c/Users/StanC/Desktop/Milescorp/docs/coordination'

TASKS = """
| TASK-DEV-071 | Image Live USB Debian 13 (clé 64 Go, persistance, MILES auto) | Fabriquer une image **live** sans installation : rootfs Debian 13 + MILES + Companion, squashfs, ISO hybride BIOS/UEFI, autologin `miles`, MILES auto-démarré sur tty1, persistance, défauts fail-closed ; tester UEFI, BIOS, le chemin clé USB et la persistance sur deux démarrages ; livrer l'ISO et le guide utilisateur | DONE | Agent A | `.usb-iso-build/**` (chaîne de build et tests), `docs/installation/LIVE_USB.md`, `releases/miles-debian13-live-20261124.iso`, `docs/coordination/*` | ISO 299 892 736 o, SHA256 `e7b5ac8e85311d7886f0084a7704bec44402be2f8cd4d9fbccbc0cbed5201fc1` ; tests QEMU 10.2/OVMF : UEFI (session ~63 s), BIOS (~45 s), clé USB (`qemu-xhci` + `usb-storage`), persistance 2 démarrages (fichier conservé, `upperdir` sur la clé), services `active` + HTTP 200/200, SSH fermé, FR/AZERTY, MILES sur tty1 ; guide `LIVE_USB.md` ; 87 scripts one-off purgés (33 conservés + README de chaîne) | — | 2026-11-24 | 2026-11-24 |
"""

DECISIONS = """
## DEC-035 — Image Live USB : construction manuelle, persistance par partition, console comme interface principale

- **Date** : 2026-11-24
- **Décidé par** : Agent A
- **Contexte** : livrer une clé USB 64 Go exécutant MILES sans installation disque, en français/AZERTY, avec persistance et démarrage automatique de l'assistant.
- **Décisions** :
  1. **Image live construite à la main** (`debootstrap` → `mksquashfs` → `xorriso`) : `live-build` n'est pas en place sur le poste et la chaîne doit rester lisible et rejouable (`.usb-iso-build/README.md`).
  2. **Persistance = seconde partition étiquetée `persistence`** contenant `persistence.conf` (`/ union`). Sans ce fichier, `live-boot` referme la partition après montage : les deux sont donc exigés par le guide.
  3. **Interface principale = console MILES auto-démarrée sur tty1** : l'image ne contient ni serveur graphique ni navigateur (choix « le plus fiable, le moins lent »). `miles.service` (127.0.0.1:8080) et `miles-companion.service` (127.0.0.1:8787) restent actifs, en boucle locale uniquement.
  4. **Défauts fail-closed** : aucun secret embarqué (`MILES_PROVIDER=local`, jeton web vide), `ssh` installé mais désactivé, exposition du LAN toujours soumise à l'audit B.
  5. **`sudo` sans mot de passe** pour l'utilisateur `miles` : acceptable sur une clé live personnelle, **jamais** sur une machine installée.
- **Alternatives écartées** : live-build (indisponible), session graphique (lente et fragile sur clé), fichier de persistance posé sur la partition ISO (live-boot attend une partition dédiée).
- **Conséquences** : `docs/installation/LIVE_USB.md` fait foi pour l'écriture de la clé, la persistance et le premier `miles --setup` ; la chaîne et ses tests sont documentés dans `.usb-iso-build/README.md`.
"""

STATUS = """
## Image Live USB Debian 13 — livraison de la clé 64 Go (Agent A, DONE 2026-11-24)

- **Tâche** : `TASK-DEV-071` (DONE). **Décision** : `DEC-035`. **Handoff** : `H-021`.
- **Livrable** : `releases/miles-debian13-live-20261124.iso`, 299 892 736 o, SHA256 `e7b5ac8e85311d7886f0084a7704bec44402be2f8cd4d9fbccbc0cbed5201fc1` (inscrit dans `releases/SHA256-ISO-SUMS`). Ancienne `releases/miles-debian13-live.iso` (577 765 376 o, défaillante) supprimée.
- **Guide** : `docs/installation/LIVE_USB.md` — vérification `Get-FileHash`, écriture **DD** (Rufus/balenaEtcher), clés de boot F12/F9/F8, persistance créée depuis la clé, premier `miles --setup`, dépannage, sécurité, intérêt du Companion.
- **Tests QEMU 10.2 / OVMF (WSL)** : UEFI (CD) session ~63 s ; BIOS legacy ~45 s ; **clé USB** — ISO copiée sur disque et présentée en `usb-storage` via `qemu-xhci` → GRUB → session ; **persistance sur 2 démarrages** : `/dev/vda on /run/live/persistence/vda`, `upperdir=/run/live/persistence/vda/rw`, fichier `persistance-ok-…` créé avant reboot **retrouvé** après reboot ; `miles` et `miles-companion` `active`, HTTP **200/200** ; `ssh` inactif ; aucune unité en échec ; `fr_FR.UTF-8` + `XKBLAYOUT="fr"` ; MILES exécuté sur tty1 après autologin `miles`.
- **Correctifs structurants** : `/etc/live/config.conf` porte `LIVE_USERNAME="miles"` (sinon `live-config-getty-generator` écrit `--autologin user`, compte inexistant) ; `MILES_PROVIDER=local` (la valeur `off` mettait le service en boucle) ; le bus USB manquant du `q35` impose `-device qemu-xhci`.
- **Nettoyage** : 87 scripts one-off supprimés, 33 conservés + `.usb-iso-build/README.md` (chaîne de fabrication et tests) ; `hardware/packages/usb-installer/.usb-iso-build/` ajouté à `.gitignore` (contient une ISO de 792 Mo).
- **Reste à faire** : écriture physique de la clé et boot sur matériel réel (utilisateur) ; revue indépendante Agent B ; exposition LAN toujours bloquée sur l'audit B.
"""

HANDOFF = """
## H-021 — 2026-11-24 — Agent A → Agent B — image Live USB Debian 13 (clé 64 Go)

- **De** : Agent A (poste principal, utilisateur `DripMind`).
- **Vers** : Agent B — revue indépendante.
- **Référence** : `TASK-DEV-071` (DONE), `DEC-035`.

### Travail réalisé

1. **Fabrication** : rootfs `debootstrap` trixie → chroot (noyau 6.12, `live-boot`, systemd, locales FR, clavier `fr` pc105) → MILES + Companion dans `/opt/Milescorp` (venv, unités `miles.service` et `miles-companion.service`, utilisateur `miles`) → `mksquashfs -comp xz -e boot` (236 953 600 o) → `xorriso` hybride BIOS/UEFI (menus ISOLINUX et GRUB, timeout 5 s, argument `persistence` présent dans les deux). Chaîne complète documentée dans `.usb-iso-build/README.md`.
2. **Correctifs** : `LIVE_USERNAME="miles"` dans `/etc/live/config.conf` (le générateur `live-config-getty-generator` écrasait l'autologin avec un compte `user` inexistant) ; `MILES_PROVIDER=local` (la valeur `off` provoquait un crash-loop de `miles.service`) ; `MILES_WEB_AUTH_TOKEN` vide ; SSH désactivé ; `miles` en `NOPASSWD:ALL`.
3. **Tests exécutés (QEMU 10.2, OVMF, WSL)** : UEFI ✅ ; BIOS ✅ ; **chemin clé USB** ✅ (ISO copiée, `-device qemu-xhci` + `usb-storage`) ; **persistance 2 démarrages** ✅ — partition `persistence` montée, overlay avec `upperdir` sur le disque de persistance aux deux boots, fichier créé avant reboot retrouvé après reboot, services `active` ; HTTP 200/200 sur `127.0.0.1:8080` et `:8787` ; `ssh` inactif ; aucune unité en échec ; locale FR + AZERTY ; MILES sur tty1 (vérifié par marqueur + process + capture avec redraw forcé).
4. **Livraison** : `releases/miles-debian13-live-20261124.iso` (299 892 736 o, SHA256 `e7b5ac8e85311d7886f0084a7704bec44402be2f8cd4d9fbccbc0cbed5201fc1`), `releases/SHA256-ISO-SUMS` mis à jour, ancienne ISO défaillante supprimée, guide `docs/installation/LIVE_USB.md`.
5. **Nettoyage** : 87 scripts one-off supprimés, 33 conservés (build + tests) avec README ; `.gitignore` complète de l'espace de build de l'installateur.

### Résultats

- ISO prête à être écrite sur la clé 64 Go en **mode DD** ; persistance à créer depuis la clé elle-même (guide §4) ; premier réglage IA par `miles --setup` (guide §5), conservé par la persistance.
- `docs/installation/LIVE_USB.md`, `.usb-iso-build/README.md`, `TASK-DEV-071`, `DEC-035`.

### Points non exécutés

- Écriture réelle sur clé physique et boot sur matériel réel (non disponible ici) ; **Secure Boot non prouvé sur firmware réel** — `EFI/boot/bootx64.efi` (shim) et `grubx64.efi` sont signés `Debian Secure Boot CA` / `Microsoft Corporation UEFI CA 2011`, vérifié par `sbverify`/`strings`, mais la chaîne complète n'a pas été testée sur un vrai firmware.
- Persistance validée sur disque virtuel ; la procédure `fdisk` + `partx` du guide §4 n'a pas été rejouée telle quelle depuis la session live (les outils sont présents, `check-tools.sh`).
- Aucun appel réseau sortant, aucun secret embarqué, aucun push forcé.

### Prochaine action recommandée

Écrire l'ISO en mode DD, créer la partition de persistance selon le guide §4, booter sur machine réelle (F12/F9/F8), vérifier `mount | grep persistence` puis `miles --setup`. Revue Agent B de `.usb-iso-build/README.md`, du guide et des défauts fail-closed (`DEC-035`).
"""

TARGETS = [
    ('TASKS.md', TASKS, 'row'),      # la ligne doit suivre le tableau sans ligne vide
    ('DECISIONS.md', DECISIONS, 'section'),
    ('STATUS.md', STATUS, 'section'),
    ('HANDOFF.md', HANDOFF, 'section'),
]

for name, block, kind in TARGETS:
    path = os.path.join(BASE, name)
    raw = open(path, 'rb').read()
    txt = raw.decode('utf-8', 'replace')
    key = block.strip().splitlines()[0][:24]
    if key in txt:
        print(f'{name} : deja append, ignore')
        continue
    body = block.strip('\r\n')
    if kind == 'row':
        # pas de ligne vide : une ligne vide romprait le tableau Markdown
        prefix = b'' if raw.endswith(b'\r\n') else b'\r\n'
        new_raw = raw + prefix + (body + '\r\n').encode('utf-8')
    else:
        trimmed = raw.rstrip(b'\r\n')
        new_raw = trimmed + ('\r\n\r\n' + body + '\r\n').encode('utf-8')
    with open(path, 'wb') as f:
        f.write(new_raw)
    print(f'{name} : append OK (+{len(new_raw) - len(raw)} octets)')

# verification
for name, _, _ in TARGETS:
    p = os.path.join(BASE, name)
    raw = open(p, 'rb').read()
    raw.decode('utf-8')
    print(f'  {name} : UTF-8 OK, {len(raw)} octets, CRLF={raw.count(b"\r\n")}')
