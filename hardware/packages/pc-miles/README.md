# Paquet PC — Mini-PC Lenovo ThinkCentre M75q (Debian 13)

## Contenu
| Fichier | Rôle |
|---|---|
| `install.sh` | Installe MILES sur Debian 13 (venv, service systemd) |
| `miles.service` | Unité systemd durcie (lecture seule sauf data/) |
| `.env.example` | Variables MILES_* à copier puis personnaliser |
| `box_preflight.sh` | Contrôle matériel AVANT installation (lecture seule) |
| `cockpit-launcher.sh` | Lance le cockpit web local (8787) |

## Installation (sur le M75q)
1. Copier l'archive sur le M75q, la décompresser.
2. `chmod +x box_preflight.sh && ./box_preflight.sh` — vérifier OS/Python/RAM/GPU.
3. `cp .env.example .env && chmod 600 .env` puis `python3 miles.py --setup`.
4. `sudo INSTALL_SERVICE=1 ./install.sh` — installe le service, démarre MILES sur `127.0.0.1:8080`.
5. `./cockpit-launcher.sh` — ouvre le cockpit sur `127.0.0.1:8787`.

## Sécurité
- Écoute **strictement 127.0.0.1** (mode LAN : voir `docs/installation/BOX_DEBIAN_SETUP.md`).
- `.env` en 600, jamais commité, jamais journalisé.
- Aucun appel réseau sortant n'est requis au démarrage.
