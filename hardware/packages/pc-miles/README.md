# Paquet PC — Mini-PC Lenovo ThinkCentre M75q (Debian 13)

## Contenu

| Fichier | Rôle |
|---|---|
| `install.sh` | Installe MILES (dépôt, venv, `.env`, tests) et, sur demande, le service systemd |
| `miles.service` | Unité systemd durcie, écoute locale uniquement |
| `.env.example` | Variables `MILES_*`, dérivées de la racine du dépôt — à copier puis personnaliser |
| `box_preflight.sh` | Contrôle matériel **avant** installation (lecture seule, aucun réseau) |
| `cockpit-launcher.sh` | Lance le cockpit local (127.0.0.1:8787) servi par le dépôt |

## Installation (sur le M75q)

```bash
# 1. Prérequis
sudo apt update && sudo apt install -y python3 python3-venv git

# 2. Diagnostic matériel (lecture seule, rien n'est modifié)
bash box_preflight.sh

# 3. Première passe : clone le dépôt, crée le venv et le .env, puis s'arrête
./install.sh

# 4. Renseigner la configuration (obligatoire avant de continuer)
$EDITOR Milescorp/.env          # permissions 600 déjà appliquées
#   MILES_PROVIDER, MILES_REMOTE_API_KEY, MILES_WEB_AUTH_TOKEN

# 5. Seconde passe : tests du dépôt, puis service si demandé
INSTALL_SERVICE=1 ./install.sh
```

`install.sh` est **idempotent** : le relancer ne supprime ni ne réinitialise
rien. Il refuse de poursuivre tant que `.env` n'existe pas, et n'invente aucune
valeur de configuration.

Le service démarre MILES sur `127.0.0.1:8080`. Journaux : `journalctl -u miles -f`.

## Cockpit

```bash
bash cockpit-launcher.sh        # http://127.0.0.1:8787/cockpit/
```

Le cockpit est `assets/web` du dépôt, servi par le serveur Companion sous
`/cockpit/` (DEC-015 : une seule implémentation). Ce n'est pas un dossier
statique du paquet.

## Sécurité

- Écoute **strictement `127.0.0.1`** par défaut ; le mode LAN exige `--web-lan`,
  un jeton porteur persistant **et** une adresse privée nommée (DEC-016 §2).
- `.env` en `600`, jamais commité, jamais journalisé.
- Aucun appel réseau sortant n'est requis au démarrage.
- `install.sh` n'écrit que dans le répertoire d'installation du dépôt.
