# Checklist — test de l'ISO MILES sous VirtualBox

> **Objectif** : valider l'installation AUTOMATIQUE avant de toucher au vrai
> mini-PC. Rien n'est installé sur la machine qui exécute la VM.
> **Durée** : ~25 min. **Intervention humaine attendue : aucune.**

## Prérequis (sur le PC qui teste)

- [ ] VirtualBox installé (virtualbox.org, version 7.x)
- [ ] Fichier `miles-debian13-autoinstall-<date>.iso` reçu + `SHA256-ISO-SUMS`
- [ ] Vérifier l'intégrité de l'ISO :
      PowerShell → `cd <dossier> ; Get-FileHash .\miles-...iso -Algorithm SHA256`
      = valeur de `SHA256-ISO-SUMS` (sinon : ISO corrompue, on la retransfère)
- [ ] Ethernet (ou WiFi) **connecté** sur cette machine (l'install Debian
      télécharge les paquets)

## Création de la VM

- [ ] VirtualBox → **Nouvelle** → Type : **Linux** / Version : **Debian (64-bit)**
- [ ] Mémoire : **2048 Mo** ; CPU : **2**
- [ ] Disque virtuel : **25000 Mo** (dynamique) — *sera effacé par l'install, c'est la VM*
- [ ] **Système → Accélération** : cocher **EFI** (désactiver le disque disquette)
- [ ] **Stockage** → contrôleur IDE → cliquer le **CD vide** → glisser
      l'ISO `miles-debian13-autoinstall-*.iso`
- [ ] **Réseau** : adaptateur 1 → **NAT** (ou pont)

## Test d'exécution (le cœur du test)

Démarrer la VM et **ne rien toucher** :

| # | Observation attendue | ☐ |
|---|---|---|
| 1 | Le menu de démarrage apparaît et **démarre tout seul** (< 3 s, aucune touche) | ☐ |
| 2 | L'installateur démarre en **français**, puis enchaîne **sans poser aucune question** | ☐ |
| 3 | Aucune fenêtre « écrire sur le disque ? » ou autre confirmation n'apparaît | ☐ |
| 4 | Écran « Exécution de late_command » avec au final `MILES : payload depose...` (ou écran sombre puis redémarrage) | ☐ |
| 5 | La VM **redémarre seule** sur un écran de connexion Debian | ☐ |

> Durée totale observée : ______ min (comptez 15-20 min avec une bonne
> connexion)

## Premier boot (après le redémarrage)

Se connecter : utilisateur **`miles`**, mot de passe choisi à la construction.

| # | Commande / Action | Résultat attendu | ☐ |
|---|---|---|---|
| 6 | `systemctl status miles` | **active (running)** (ou `activating` 1 min le temps des tests) | ☐ |
| 7 | `ls /opt/Milescorp` | `miles.py`, `app/`, `tests/` présents | ☐ |
| 8 | `tail -30 /var/log/miles-provision.log` | ligne `MILES provision — fin` **et** `Suite de tests : code retour 0` | ☐ |
| 9 | `python3 -m unittest discover -s tests -q` (dans `/opt/Milescorp`) | **OK** (0 échec) | ☐ |
| 10 | `systemctl is-enabled miles` | `enabled` (démarre à chaque boot) | ☐ |
| 11 | Redémarrer la VM (`sudo reboot`), se reconnecter, `systemctl status miles` | **active (running)** — le service survit au reboot | ☐ |
| 12 | Depuis la machine hôte : ouvrir `http://127.0.0.1:8080` **dans la VM** | le serveur répond (jeton affiché au lancement via `--web`) | ☐ |
| 13 | `python3 miles.py --setup` dans la VM | l'assistant demande fournisseur + clé API (saisie masquée) | ☐ |

## Sécurité (2 contrôles)

| # | Contrôle | Attendu | ☐ |
|---|---|---|---|
| 14 | `grep -r "API_KEY" /opt/Milescorp/.env 2>/dev/null` AVANT `--setup` | **aucune clé en clair présente** | ☐ |
| 15 | `ss -ltnp` | MILES n'écoute que sur **127.0.0.1** (pas `0.0.0.0`) | ☐ |

## Dépannage éventuel

| Symptôme | Cause probable |
|---|---|
| Menu qui attend une touche | `isolinux.cfg`/`grub.cfg` non modifiés → reconstruire l'ISO |
| Question d'installation qui apparaît | preseed non lu dans l'initrd → reconstruire l'ISO |
| « No space left » | disque VM trop petit : 25 Go minimum |
| Échec de téléchargement des paquets | pas de réseau → connecter la VM |
| `miles` en échec | `journalctl -u miles -f` ; souvent `.env` absent (normal tant que `--setup` n'est pas fait) |

## Verdict

- [ ] **VERT** — tout est conforme → on grave sur la clé et on passe au HP ProDesk.
- [ ] **ROUGE** — au moins un point en échec → **ne pas graver la clé** ;
      transmettre la checklist remplie + capture d'écran des anomalies.

Nom du testeur : ______________  Date : __________  Verdict : ☐ VERT ☐ ROUGE
