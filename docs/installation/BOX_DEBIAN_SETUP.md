# Installation MILES sur la box Debian 13 (pas-à-pas)

> **Statut** : document d'installation **texte, non exécuté** sur du matériel
> réel (aucune validation Debian 13 du logiciel MILES à ce jour — MI-006 reste
> la validation de référence). Ce guide ne doit être suivi qu'après validation
> de la chaîne d'intégration par les audits.
>
> **Règle de sécurité permanente** : MILES écoute sur `127.0.0.1` par défaut.
> **Toute ouverture au réseau local (LAN) est INTERDITE tant qu'une
> authentification réelle côté client n'existe pas** (jeton porteur +
> session = l'interface actuelle est locale uniquement).

## 1. Prérequis

- Debian 13 (testé ici : document rédigé sur la base des rapports du projet ;
  **non vérifié sur le matériel**).
- Python ≥ 3.10 (le projet cible Python 3 ; vérifié sur Windows 3.14 et
  Debian 3.13 dans les rapports d'audit).
- Paquets système : aucun requis pour le mode texte (aucune dépendance
  Python externe obligatoire). La voix est optionnelle (voir INSTALL.md).

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
python3 --version   # >= 3.10 attendu
```

## 2. Récupération et installation

```bash
cd /opt
git clone https://github.com/Miles-corp/Milescorp.git
cd Milescorp
python3 -m venv .venv
. .venv/bin/activate
# aucune dépendance externe obligatoire : requirements.txt documentaire
```

## 3. Configuration initiale (assistant intégré)

```bash
cd /opt/Milescorp
python3 miles.py --setup
```

L'assistant (mode `--setup`) :

1. demande le fournisseur (Groq, Gemini, Mistral, OpenAI, Claude) ;
2. demande la clé API avec **saisie masquée** (jamais affichée) ;
3. écrit le fichier `.env` de façon atomique (`MILES_PROVIDER`,
   `MILES_REMOTE_*`, `MILES_API_KEY_<NOM>`).

```bash
chmod 600 .env     # permissions restrictives recommandées
```

Vérifications :
```bash
python3 -m unittest discover -s tests     # suite complète attendue verte
python3 scripts/box_preflight.py          # diagnostic lecture seule du matériel
```

## 4. Lancement manuel (test)

```bash
python3 miles.py            # mode terminal
python3 miles.py --web      # interface locale (jeton affiché une fois)
```

L'interface web n'écoute que sur `127.0.0.1` (`LOCAL_ONLY_HOST`, refus
explicite de toute autre adresse) — **ne jamais modifier cet hôtesse sans
décision écrite et authentification réelle**.

## 5. Service systemd (exemple — texte, NON installé)

Fichier ` /etc/systemd/system/miles.service` (exemple à adapter) :

```ini
[Unit]
Description=MILES - Assistant personnel (interface locale)
After=network.target

[Service]
Type=simple
User=miles
WorkingDirectory=/opt/Milescorp
ExecStart=/opt/Milescorp/.venv/bin/python3 miles.py --web --web-port 8080
Restart=on-failure
RestartSec=5
# Durcissements systèmes
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/Milescorp/data /opt/Milescorp/.env

[Install]
WantedBy=multi-user.target
```

Activation (une fois, après validation humaine) :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now miles
systemctl status miles
journalctl -u miles -f
```

### Points de vigilance de l'unité

- `User=miles` : jamais root pour le service.
- `ReadWritePaths` : le service ne peut écrire que dans `data/` (bases) ;
  le `.env` n'est écrit que par `--setup`, manuellement.
- **Écoute** : `--web-port` sans argument d'hôte = `127.0.0.1` uniquement
  (le serveur refuse tout autre hôte par conception).
- **Ouverture réseau locale (LAN) : INTERDITE** tant que :
  - l'authentification par jeton/session n'est pas complétée par une
    vérification d'identité réelle côté client ;
  - une décision écrite du responsable ne l'autorise pas.
  Si un jour nécessaire : reverse-proxy + TLS + comptes — hors de ce guide.

## 6. Mise à jour

```bash
cd /opt/Milescorp
git pull                      # après validation des audits
. .venv/bin/activate
python3 -m unittest discover -s tests
sudo systemctl restart miles
```

## 7. Dépannage rapide

| Symptôme | Piste |
|---|---|
| `journalctl` montre « Authentification non configurée » | `--setup` non exécuté ou `.env` illisible (permissions) |
| Mémoire « indisponible » | `MILES_MEMORY_ENABLED` et `MILES_MEMORY_DB_PATH` ; voir `box_preflight.py` |
| Le service refusera tout le monde (403) | Comportement voulu sans jeton configuré — fermé par défaut |
| Ports absents du préflight | `ss -ltnp` pour vérifier (diagnostic, lecture seule) |

---
*Référence : `docs/installation/INSTALL.md` (config des 19 variables MILES_*),
`scripts/box_preflight.py` (diagnostic matériel), rapports d'audit B pour la
validation réelle.*
