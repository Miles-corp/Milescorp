# `.usb-iso-build/` — fabrication et tests de l'image Live USB MILES

Chantier **Agent A** (Mission : clé USB live Debian 13 + MILES + Companion).
Tout tourne sous **WSL Ubuntu** (`wsl -d Ubuntu -u root`), le dépôt étant monté
sur `/mnt/c/Users/StanC/Desktop/Milescorp`.

> ⚠ Les commandes contenant `$`, des guillemets ou `&&` sont cassées par
> PowerShell : **toujours** écrire le script puis exécuter
> `wsl -d Ubuntu -u root -- bash /mnt/c/.../<script>.sh`.

---

## 1. Chaîne de fabrication (dans l'ordre)

| # | Script | Rôle |
|---|--------|------|
| 1 | `install-live-tools.sh` | installe `debootstrap`, `live-boot`, `live-config`, noyau sur la machine hôte (WSL) |
| 2 | `debootstrap.sh` | rootfs Debian 13 `trixie` **minbase** → `/root/live-rootfs` |
| 3 | `setup-live-rootfs.sh` | en chroot : noyau, `live-boot`, systemd, python3, locales `fr_FR.UTF-8`, clavier `fr` pc105 (AZERTY) |
| 4 | `setup-live-miles.sh` | copie de MILES + Companion dans `/opt/Milescorp`, venv, unités `miles.service` (8080) et `miles-companion.service` (8787), utilisateur `miles`, `.env` **sans secret** |
| 5 | `fix-packages.sh` | complète les paquets d'init (`systemd-sysv`, `udev`, `dbus`, `kmod`, `iproute2`…) |
| 6 | `fix-init.sh` | `/sbin/init` → systemd |
| 7 | `fix-env.sh` | `MILES_PROVIDER=local` (la valeur `off` plantait le service en boucle) |
| 8 | `fix-ownership.sh` | ramène tout à `1000:1000`, nettoyage `apt` et `/run` + `/tmp` du chroot |
| 9 | `setup-autologin.sh` | autologin `miles` sur la console série (et tty1 via live-config) |
| 10 | `fix-liveconfig-user.sh` | **essentiel** : `/etc/live/config.conf` porte `LIVE_USERNAME="miles"` — sans cela, le générateur `live-config-getty-generator` écrit `--autologin user` (compte inexistant) |
| 11 | `setup-autostart.sh` | `~/.bash_profile` → lancement auto de MILES sur tty1, wrapper `/usr/local/bin/miles`, `/etc/motd` |
| 12 | `gen-initrd.sh` | `apt-get clean` + `update-initramfs -u` |
| 13 | `build-squashfs.sh` | `mksquashfs -comp xz -e boot` → `/root/live-build/live/filesystem.squashfs` (~227 Mo) |
| 14 | `build-live-iso4.sh` | assemble l'arbre (noyau + initrd **validés**, squashfs, isolinux/grub/EFI repris de l'ISO installateur), écrit les menus, fabrique l'ISO **hybride** BIOS+UEFI avec xorriso |
| 15 | `full-rebuild.sh` | 13 + 14 + empreinte SHA-256 |
| 16 | `deliver-iso.sh` | copie datée vers `releases/`, met à jour `releases/SHA256-ISO-SUMS`, supprime l'ISO obsolète |

Les étapes 5 à 12 sont des **correctifs** appliqués au rootfs : elles sont
idempotentes et peuvent être rejouées.

---

## 2. Tests (QEMU 10.2 + OVMF)

| Script | Ce qu'il prouve |
|--------|-----------------|
| `test-live3.py uefi` / `bios` | démarrage complet, services actifs, HTTP 200/200, SSH fermé, locale FR + clavier `fr`, autoconnexion `miles`, MILES lancé sur tty1 (avec **redraw forcée** avant la capture d'écran) |
| `test-usb-boot.py` | l'ISO copiée sur un disque et présentée en **`usb-storage`** (i.e. le vrai chemin « clé USB ») démarre sous OVMF → GRUB → session |
| `test-persistence.py` | **2 démarrages** : partition `persistence` montée, `overlay` avec `upperdir` sur la clé, fichier créé avant reboot **toujours présent** après |
| `diag-getty.py`, `diag-tty.py` | diagnostic de l'autologin et du contenu de tty1 |
| `check-secureboot.sh`, `check-signature.sh` | présence de shim + GRUB signés (`Debian Secure Boot CA`, `Microsoft Corporation UEFI CA 2011`) |
| `check-tools.sh` | outils disponibles dans l'image pour la procédure de persistance (`fdisk`, `partx`, `mkfs.ext4` — `partprobe` absent) |
| `show-menus.sh` | contenu des menus ISOLINUX / GRUB |
| `diag-persistence*.sh` | lecture du code `live-boot` dans l'initrd (cause du non-montage) |

### Piège connu : la persistance exige `persistence.conf`

`live-boot` détecte une partition **étiquetée `persistence`**, la monte, puis la
**referme** si `/persistence.conf` est absent. Une image de test recréée sans ce
fichier donne l'illusion que « la persistance ne marche pas ».

### Piège connu : captures d'écran QEMU

`screendump` renvoie une image **périmée** tant que le virtual terminal n'est
pas redessiné : forcer avec `printf … > /dev/tty1` ou `chvt 3; chvt 1`.

---

## 3. Résultat

| Élément | Valeur |
|---------|--------|
| ISO | `releases/miles-debian13-live-20261124.iso` |
| Taille | 299 892 736 o (~286 Mo) |
| SHA-256 | `e7b5ac8e85311d7886f0084a7704bec44402be2f8cd4d9fbccbc0cbed5201fc1` |
| Base | Debian 13 (trixie), noyau 6.12.117 |
| Guide utilisateur | `docs/installation/LIVE_USB.md` |

L'ISO et les images de test (`/root/live-*.img`, `/root/live-rootfs`,
`/root/live-build*`) ne sont **jamais** commitées : `releases/` est ignoré par
Git et aucun secret n'est embarqué.
