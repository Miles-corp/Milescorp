# MILES Live USB — guide de la clé 64 Go (Debian 13)

> Image **live** : rien n'est installé sur le disque dur de la machine.
> Tout tourne depuis la clé, en **français (AZERTY)**, avec **MILES qui démarre
> automatiquement** et la **persistance** (vos données survivent aux
> redémarrages).

---

## 1. Fichier de l'image

| Élément | Valeur |
|---|---|
| Fichier | `releases/miles-debian13-live-20261124.iso` |
| Taille | ~286 Mo (clé de 64 Go largement suffisante) |
| Empreinte | `releases/SHA256-ISO-SUMS` |
| Base | Debian 13 (trixie), noyau 6.12, MILES + Companion |

Vérification sous Windows (PowerShell) :

```powershell
Get-FileHash .\releases\miles-debian13-live-20261124.iso -Algorithm SHA256
```

La valeur doit correspondre à celle de `releases/SHA256-ISO-SUMS`.

---

## 2. Écriture sur la clé

⚠ **La clé sera entièrement effacée.**

**Méthode recommandée — Rufus** (Windows) :

1. Insérer la clé 64 Go, lancer Rufus.
2. **Sélectionner** → choisir l'ISO `miles-debian13-live-20261124.iso`.
3. Lorsque Rufus demande le mode d'écriture, choisir **DD Image**
   (« Écrire en mode image disque ») — **pas** « Mode ISO ».
4. Démarrer l'écriture, attendre la fin (vérification comprise).

**Alternative** : balenaEtcher (écriture image disque, identique).

> L'image est **hybride** : la même clé démarre en **UEFI** (menu GRUB) et en
> **BIOS legacy** (menu ISOLINUX), avec un timeout de 5 s sur l'entrée
> « Live MILES (Francais, AZERTY) ».

---

## 3. Premier démarrage

1. Clé branchée, démarrer la machine dessus.
   - Menu de démarrage : **F12** (Dell, Lenovo), **F9** (HP), **F8** (ASUS),
     **Échap** (Samsung) — sinon régler l'ordre de boot dans le BIOS/UEFI.
2. Choisir **« Live MILES (Francais, AZERTY) »** (sinon lancé tout seul après 5 s).
3. Après ~45 à 60 s : la session s'ouvre **sans mot de passe** sur `miles`.
4. **MILES s'affiche et tourne déjà** sur la console principale (tty1).

```
======================================================================
  MILES live — assistant personnel (Debian 13, clavier AZERTY)
======================================================================
  * MILES demarre automatiquement ci-dessous.
  * Apres sortie de MILES : 'miles' pour relancer,
    'miles --setup' pour renseigner la cle IA (persiste sur la cle).
  * Services locaux : http://127.0.0.1:8080 (interface web)
                      http://127.0.0.1:8787 (Companion)
======================================================================
```

### Commandes utiles

| Action | Commande |
|---|---|
| Sortir de MILES, obtenir un shell | `/quit` (ou `exit` dans MILES) |
| Relancer MILES | `miles` |
| Renseigner la clé IA (fournisseur + clé) | `miles --setup` |
| État des services | `systemctl status miles miles-companion` |
| Redémarrer MILES après configuration | `sudo systemctl restart miles` |
| Droits administrateur | `sudo …` (sans mot de passe sur cette clé) |
| Éteindre | `sudo poweroff` |

### Ce qui tourne au démarrage

| Composant | Adresse | État |
|---|---|---|
| `miles.service` (interface web) | `127.0.0.1:8080` | **localhost uniquement** |
| `miles-companion.service` (site de contrôle) | `127.0.0.1:8787` | **localhost uniquement** |
| `ssh` | — | **désactivé** (fail-closed) |
| Console MILES (tty1) | — | démarrage automatique |

Clavier **fr (AZERTY)**, locale **fr_FR.UTF-8**, fuseau `Europe/Paris`.

---

## 4. Persistance (fortement recommandé)

Sans partition de persistance, **tout est effacé à chaque redémarrage**
(conversations, configuration, clé IA). Avec elle, la clé devient un vrai
poste de travail.

La persistance se crée **depuis la clé elle-même** — aucun logiciel Windows
supplémentaire n'est nécessaire.

### Étape 1 — ouvrir un shell

Dans MILES : `/quit`, ou `Ctrl+D`.

### Étape 2 — identifier la clé

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
```

La clé se reconnaît à ses deux petites partitions :

```
NAME   SIZE FSTYPE   LABEL      MOUNTPOINT
sda    286M iso9660  MILES-LIVE /run/live/medium
├─sda1 286M iso9660  MILES-LIVE /run/live/medium
└─sda2 3,6M vfat
```

> ⚠ Ne pas confondre avec le disque interne (`nvme0n1`, `sdb`… toujours
> monter sur le bon périphérique : **l'opération efface la partition**).
> Le nom ci-dessus (`sda`) est un exemple : utiliser celui de votre clé.

### Étape 3 — créer la partition

```bash
sudo fdisk /dev/sdX        # remplacer sdX par la clé
```

Dans `fdisk` :

| Touche | Action |
|---|---|
| `n` | nouvelle partition |
| `p` | primaire (si proposé) |
| `3` (ou le numéro proposé) | numéro de partition |
| `Début` (Entrée) | premier secteur libre proposé |
| `Fin` (Entrée) | dernier secteur → toute la place restante |
| `w` | écrire la table et sortir |

Puis rendre la nouvelle partition visible au noyau :

```bash
sudo partx -u /dev/sdX      # (partprobe n'existe pas sur cette image)
lsblk                       # la nouvelle partition doit apparaître
```

### Étape 4 — formater et déclarer la persistance

```bash
sudo mkfs.ext4 -L persistence /dev/sdXN     # sdXN = la NOUVELLE partition
sudo mkdir -p /mnt/pers
sudo mount /dev/sdXN /mnt/pers
echo '/ union' | sudo tee /mnt/pers/persistence.conf
sudo umount /mnt/pers
```

### Étape 5 — redémarrer et vérifier

```bash
sudo reboot
```

Au redémarrage, la persistance est active si le montage l'indique :

```bash
mount | grep -E 'persistence|overlay'
```

Ligne attendue (l'upperdir est sur la clé, plus sur un tmpfs) :

```
overlay on / type overlay (rw,...,upperdir=/dev/sdXN/union,...)
```

Contrôle simple : créer un fichier, redémarrer, vérifier qu'il est toujours là.

```bash
echo "test" > ~/persistance.txt && sync
sudo reboot
# après redémarrage :
cat ~/persistance.txt
```

---

## 5. Configurer l'intelligence artificielle

L'image ne contient **aucun secret** : elle démarre en fournisseur `local`
(`http://localhost:11434`, sans serveur installé) — MILES répond donc avec un
message d'erreur tant qu'aucun fournisseur n'est déclaré.

```bash
miles --setup
```

L'assistant enregistre le fournisseur et la clé dans `/opt/Milescorp/.env`
(saisie masquée, rien n'est affiché), puis :

```bash
sudo systemctl restart miles
```

Avec la persistance (§4), **la clé est conservée d'un redémarrage à l'autre** :
une seule configuration est nécessaire.

---

## 6. Dépannage

| Symptôme | Cause / solution |
|---|---|
| `Secure Boot violation` ou arrêt avant GRUB | Désactiver **Secure Boot** dans le BIOS/UEFI (les binaires EFI sont signés shim Microsoft + GRUB Debian, mais pas tous les firmwares acceptent la chaîne complète) |
| Le menu n'apparaît pas, clé ignorée | Forcer le menu de boot (F12/F9/F8), désactiver « Fast Boot » |
| `persistence` absent du montage | La partition n'est pas étiquetée `persistence` : `sudo tune2fs -L persistence /dev/sdXN` |
| Tout repart à zéro au redémarrage | Persistance absente ou `persistence.conf` manquant (§4) |
| MILES affiche « Impossible de joindre le fournisseur » | Aucune clé IA : `miles --setup` (§5) |
| Clavier anglo-saxon | `sudo dpkg-reconfigure keyboard-configuration` (défaut : `fr`, pc105) |
| Écran noir après le menu | Essayer l'entrée « Live MILES (mode texte) » |
| Diagnostiquer un démarrage | La console série est active (`console=ttyS0,115200n8`) : brancher un câble série ou utiliser `journalctl -b` depuis le shell |

---

## 7. Sécurité (défauts volontairement « fail-closed »)

- MILES et Companion écoutent **uniquement sur `127.0.0.1`** : aucun accès
  réseau distant, même sur le LAN.
- `ssh` est **installé mais désactivé**, aucun port 22 ouvert.
- Aucun secret n'est embarqué dans l'image (clé IA à saisir sur la clé).
- `sudo` est sans mot de passe : acceptable sur une clé live personnelle,
  **à ne jamais faire sur une machine installée**.
- Exposer MILES ou Companion sur le LAN exige l'**audit B** et une
  décision consignée dans `docs/coordination/DECISIONS.md`.

---

## 8. Utile : Companion sur cette image ?

**Companion est embarqué et actif** (`miles-companion.service`,
`127.0.0.1:8787`, HTTP 200 vérifié au démarrage).

- **Utile** : site de contrôle local (état de MILES, missions, fournisseurs,
  journal d'appairage) consultable depuis la machine elle-même **si un
  navigateur est présent**.
- **Limite sur la clé live** : l'image ne contient **ni serveur graphique ni
  navigateur** (parti pris : démarrage rapide et fiable). Companion est donc
  joignable depuis la machine live seulement via un navigateur ajouté
  ultérieurement, ou depuis un autre poste **si** l'exposition LAN est
  explicitement autorisée (audit B).
- **Recommandation** : le garder (coût nul : un process Python sur
  `127.0.0.1`, arrêté en < 1 s), il deviendra pleinement utile dès qu'un
  navigateur ou une exposition LAN sera en place.

---

## 9. Résumé des tests effectués (QEMU 10.2, WSL)

| Test | Résultat |
|---|---|
| Démarrage **UEFI** (CD) | ✅ session en ~55 s |
| Démarrage **BIOS legacy** (CD) | ✅ session en ~45 s |
| Démarrage **clé USB** (image écrite sur disque, OVMF) | ✅ session, services actifs |
| Autoconnexion `miles` + démarrage auto de MILES sur tty1 | ✅ (marqueur + process + capture d'écran) |
| `miles.service` / `miles-companion.service` | ✅ `active`, HTTP **200** / **200** sur `127.0.0.1` |
| Échecs systemd (`systemctl --failed`) | ✅ aucun |
| SSH fermé (port 22) | ✅ 0 socket |
| Locale FR + clavier `fr` pc105 | ✅ |
| Overlay live monté | ✅ |
| Persistance (2 démarrages, fichier conservé) | ✅ partition `persistence` montée aux 2 boots, `upperdir` sur la clé, fichier retrouvé après reboot |
| Chaîne de fabrication et scripts de test | ✅ `.usb-iso-build/README.md` (33 scripts conservés) |
