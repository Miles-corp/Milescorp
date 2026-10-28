# usb-installer — la clé USB qui installe Debian 13 **et** MILES, tout seul

## Principe (4 actes)

```
build-iso.sh (ton PC, WSL)  →  Rufus (écrit la clé)  →  test VirtualBox (ami)
                                                          →  HP ProDesk (F9, ~20 min)
```

Une **ISO unique** fait tout : Debian 13 s'installe automatiquement (zéro
question), puis au **premier boot** le script `miles-provision.sh` dépose
MILES dans `/opt/Milescorp`, exécute les tests, installe et active le service.

## Contenu du paquet

| Fichier | Rôle |
|---|---|
| `build-iso.sh` | Fabrique l'ISO (télécharge, **vérifie le SHA256 officiel**, injecte le preseed, coupe les délais, régénère l'ISO hybride) |
| `preseed.cfg` | Réponses de l'installateur Debian (français, UEFI, disque cible auto-détecté, utilisateur `miles`) |
| `miles-provision.sh` | Au 1er boot : code MILES, venv, tests, service systemd |
| `miles-provision.service` | Unité oneshot (ne tourne qu'une fois) |
| `CHECKLIST_TEST_VM.md` | La checklist à donner à ton ami pour VirtualBox |

---

## 1. Construire l'ISO (ton PC, ~10 min)

Ouvre **WSL Ubuntu** et lance, depuis le dépôt :

```bash
sudo apt install -y xorriso cpio        # une seule fois
bash hardware/packages/usb-installer/build-iso.sh
```

Le script te **demande les mots de passe** (compte `miles` + secours root) :
ils sont hashés SHA-512 sur place, jamais écrits en clair, jamais commités.

Sortie :

- `releases/miles-debian13-autoinstall-<date>.iso` (~760 Mo)
- `releases/SHA256-ISO-SUMS`

> **Aucun secret dans l'ISO** : la clé API IA se saisit *après*
> l'installation, sur la machine : `python3 miles.py --setup`.

## 2. Écrire la clé (5 min, Windows)

**Prérequis** : clé USB **8 Go** minimum.

1. Branche la clé.
2. Lance **Rufus** → *Appareil* = ta clé (ex. PHILIPS 58 Go) ⚠️ vérifie le nom.
3. *Sélection d'amorçage* → **Démarrer** → choisis l'ISO de `releases/`.
4. Laisse les défauts → **Démarrer** → *Mode ISO* → attendre la fin.

⚠️ **Rufus efface tout ce qui est sur la clé** (c'est voulu).

## 3. Tester chez ton ami (VirtualBox) — OBLIGATOIRE avant le HP

Le PC de ton ami n'a rien à installer : seul le fichier ISO lui est nécessaire.
Suis **`CHECKLIST_TEST_VM.md`**. Point de sortie attendu :

- l'installation démarre **toute seule** (aucune touche) ;
- le mini-PC redémarre sur un login `miles` ;
- `systemctl status miles` = **active (running)** ;
- la checklist remplie et transmise.

## 4. Installer sur le HP ProDesk 400 G5

> ⚠️ **EFFACEMENT INTÉGRAL** du SSD 250 Go (décision : sacrifiable).

1. **Ethernet branché** (indispensable : la netinst télécharge les paquets).
2. Clé branchée → allumer → **F9** (menu de boot HP ; **F10** = BIOS).
3. Choisir la clé en **UEFI** → lancer → **ne plus rien toucher** (~15-20 min).
4. Le PC redémarre seul → login `miles` (mot de passe choisi à la construction).
5. Vérifications :

```bash
systemctl status miles          # active (running)
sudo python3 scripts/box_preflight.py
python3 -m unittest discover -s tests -q
```

6. **Configurer l'IA** (clé API) : `python3 miles.py --setup` → saisie masquée.
7. Interface locale : `python3 miles.py --web` → `http://127.0.0.1:8080`
   (le jeton s'affiche une fois). **Écoute strictement 127.0.0.1** —
   l'ouverture réseau reste interdite tant que l'audit B ne l'a pas validée.

### Dépannage HP

| Symptôme | Que faire |
|---|---|
| La clé n'apparaît pas au F9 | F10 → BIOS : activer l'amorçage USB, désactiver le *Secure Boot* si besoin, F10 = sauvegarder |
| L'installation s'arrête sur une question | Le preseed n'a pas été lu → reconstruire l'ISO et ré-écrire la clé |
| « Installation failed » sur le disque | Vérifier qu'aucun autre support de stockage n'est branché |
| `miles` ne démarre pas | `journalctl -u miles -f` ; cause fréquente : `.env` absent (normal avant `--setup`) |

## 5. Récupérer ta clé (revenir à une clé USB normale)

Après usage, la clé contient l'image d'installation : Windows la voit mal et
tu perds l'accès aux 58 Go. Pour tout récupérer :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore-usb.ps1
```

Il ne s'agit que sur un **disque amovible de 4 à 256 Go** (jamais un disque
fixe du PC), et il te fait taper **OUI** avant d'effacer. En fin de course :
clé NTFS, tous les Go de nouveau exploitables.

*(Alternative manuelle : Gestion des disques → Supprimer le volume → Nouveau
volume simple → format NTFS.)*

---

## Sécurité — ce qui est respecté

- **Aucun secret dans l'ISO** (pas de clé API, pas de mot de passe en clair) ;
- disque cible **auto-détecté**, la clé d'installation est exclue de
  l'effacement (Debian bug #847166) ;
- `preseed/late_command` ne dépose que la payload, sans réseau sortant ;
- le service MILES écoute **127.0.0.1** uniquement ;
- `releases/` (ISO) n'est **jamais commité** (`.gitignore`).

## Limites assumées

- ISO **non testée sur machine réelle avant la phase VirtualBox** (tu lèves
  ce risque chez ton ami) ;
- l'installation Debian exige le **réseau** (miroir officiel) ;
- firmware ESP32 : hors périmètre ici (compilation séparée, DEC-016 §3).
