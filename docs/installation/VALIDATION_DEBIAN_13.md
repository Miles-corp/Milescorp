# Validation Debian 13 — installation complète sur le mini-PC

> **Statut du document** : procédure **écrite**, **jamais exécutée** sur le
> M75q. Ce document ne prouve rien par lui-même : il décrit ce qu'il faut
> exécuter et ce qu'on doit observer. Les cases ne se cochent qu'avec une
> sortie réelle.
>
> **Ce que cette procédure valide** : une installation neuve de MILES sur
> Debian 13, depuis l'archive livrée jusqu'au cockpit authentifié, y compris
> le refus du mode réseau.
>
> **Ce qu'elle ne valide pas** : le flash du firmware ESP32 (voir
> [`hardware/packages/esp32-s3/README.md`](../../hardware/packages/esp32-s3/README.md)),
> la justesse métrologique des capteurs, la tenue en charge sur 24 h, et
> **l'ouverture au réseau local** — interdite tant que l'audit B de `DEC-019`
> n'a pas eu lieu.

---

## 0. Règle de preuve

Une étape n'est validée que si sa **sortie réelle** est conservée. Toute case
cochée sans sortie est une affirmation, pas une vérification.

```bash
mkdir -p ~/miles-validation && cd ~/miles-validation
set -o pipefail     # pour que `commande | tee` conserve le VRAI code de sortie
# Chaque commande importante : ... | tee NOM-etape.log
```

Sans `pipefail`, un `| tee` renvoie le code de `tee` (toujours 0) : un échec
passerait inaperçu. C'est précisément le genre de faux positif que cette
procédure doit empêcher.

Deux interdits pendant toute la session :

- **ne jamais** recopier `.env` ailleurs, ni l'afficher (`cat .env`) : il
  contient la clé API et le jeton ;
- **ne jamais** ajouter `--web-lan` : ce n'est pas l'objet de cette validation.

Prérequis : Debian 13 fraîchement installée, accès `sudo`, archive du paquet
décompressée dans `~/miles-paquet`, connexion réseau pour `git clone` et pour
le fournisseur IA.

---

## 1. Phase 1 — Préflight matériel (lecture seule)

```bash
cd ~/miles-paquet
bash box_preflight.sh | tee ~/miles-validation/01-preflight.log
```

| Attendu | Pourquoi |
|---|---|
| `OS : Linux ... x86_64` et un noyau Debian 13 | socle conforme |
| `Python : Python 3.1x` (≥ 3.10) | prérequis du code |
| `Disque : ... libres` non nul | place pour `data/` |
| `GPU : non détecté` **acceptable** | MILES n'exige aucun GPU |
| Dernière ligne `=== Terminé — aucun fichier modifié ===` | le diagnostic n'écrit rien |

---

## 2. Phase 2 — Première passe d'installation (doit s'arrêter)

Le mini-PC est validé **avec service systemd** : l'installation cible donc
`/opt/Milescorp`, pas le répertoire courant. C'est aussi le chemin que
l'unité `miles.service` attend.

```bash
cd ~/miles-paquet
INSTALL_SERVICE=1 ./install.sh | tee ~/miles-validation/02-install-passe1.log
echo "code de sortie = $?"      # attendu : 1
```

L'arrêt en **code 1** n'est pas un échec : le script refuse de continuer tant
que la configuration n'existe pas. C'est le comportement voulu. À ce stade il
a déjà : créé l'utilisateur système `miles`, cloné le dépôt, créé le venv et
généré un `.env` vide en 600.

Contrôles :

```bash
ls -l /opt/Milescorp/.env       # attendu : -rw------- miles miles
test -d /opt/Milescorp/.venv && echo "venv ok"
sudo -u miles test -w /opt/Milescorp/data && echo "data inscriptible par miles"
```

---

## 3. Phase 3 — Configuration (le seul endroit avec des secrets)

```bash
sudo -e /opt/Milescorp/.env
```

Renseigner **au minimum** :

| Variable | Valeur attendue |
|---|---|
| `MILES_PROVIDER` | `remote` ou `local` — **jamais** autre chose (`off` est refusé) |
| `MILES_REMOTE_API_KEY` | la clé du fournisseur (ou `MILES_LOCAL_API_KEY`) |
| `MILES_WEB_AUTH_TOKEN` | un jeton long et aléatoire |
| `MILES_BOX_KEY` | la clé partagée du boîtier (si capteurs) |

Générer les deux secrets sans les afficher :

```bash
python3 - <<'EOF'
import secrets
print("MILES_WEB_AUTH_TOKEN=" + secrets.token_urlsafe(32))
print("MILES_BOX_KEY=" + secrets.token_urlsafe(32))
EOF
```

Vérifier que la configuration est réellement lue **par l'utilisateur du
service** (aucun secret affiché) :

```bash
cd /opt/Milescorp
sudo -u miles ./.venv/bin/python3 -c "from app.config.settings import Settings; s=Settings(); print('provider =', s.provider)"
```

| Attendu | Signification |
|---|---|
| `provider = remote` (ou `local`) | `.env` lu et valide |
| `SettingsError: Fournisseur inconnu` | valeur refusée : corriger `MILES_PROVIDER` |

---

## 4. Phase 4 — Seconde passe et service

```bash
cd ~/miles-paquet
INSTALL_SERVICE=1 ./install.sh | tee ~/miles-validation/04-install-passe2.log
echo "code de sortie = $?"      # attendu : 0
```

Cette seconde passe retrouve le dépôt et le `.env` en place, lance **la suite
de tests complète** sous `/opt/Milescorp`, puis installe et démarre l'unité
systemd.

| Attendu | Remarque |
|---|---|
| `Ran N tests` puis `OK` | **0 échec** exigé ; le nombre exact et les ignorés varient selon la plateforme |
| `Service 'miles' activé` | unité installée et démarrée |
| Code de sortie `0` | installation terminée |

Si des tests échouent : **arrêter ici**, consigner la sortie, ne pas activer
le service.

---

## 5. Phase 5 — Le service tourne et n'écoute qu'en local

```bash
systemctl is-active miles                        # attendu : active
systemctl show miles -p User -p ProtectSystem -p NoNewPrivileges
```

| Propriété | Attendu |
|---|---|
| `User` | `miles` (jamais `root`) |
| `ProtectSystem` | `strict` |
| `NoNewPrivileges` | `yes` |

**La preuve d'écoute locale** — c'est le contrôle central :

```bash
ss -ltnp | grep -E ':(8080|8787|8095)' | tee ~/miles-validation/05-ports.log
```

| Attendu | Interdit |
|---|---|
| `127.0.0.1:8080` | `0.0.0.0:8080` ou `[::]:8080` |
| `127.0.0.1:8787` (si cockpit lancé) | `0.0.0.0:8787` |
| `127.0.0.1:8095` (si backend lancé) | `0.0.0.0:8095` |

Journaux, sans secret :

```bash
journalctl -u miles -n 30 --no-pager | tee ~/miles-validation/05-journal.log
```

Aucune clé API ni jeton ne doit y apparaître.

---

## 6. Phase 6 — Interface web et authentification réelle

```bash
BASE=http://127.0.0.1:8080

# a) Sans session : refus attendu
curl -s -o /dev/null -w "sans session : %{http_code}\n" $BASE/status

# b) Ouverture de session (jeton lu depuis .env, jamais affiché)
TOKEN=$(grep -E '^MILES_WEB_AUTH_TOKEN=' /opt/Milescorp/.env | cut -d= -f2-)
curl -s -X POST $BASE/session -H "Content-Type: application/json" \
  -d "{\"token\":\"${TOKEN}\"}" | tee ~/miles-validation/06-session.json

# c) Avec session : consultation autorisée
SID=$(python3 -c "import json;print(json.load(open('$HOME/miles-validation/06-session.json'))['session_id'])")
curl -s $BASE/status -H "X-MILES-Session: $SID" | tee ~/miles-validation/06-status.json
```

| Contrôle | Attendu |
|---|---|
| (a) sans session | **401** |
| (b) session | `200` avec `session_id` et `csrf_token` |
| (c) avec session | `200`, JSON avec `provider`, `model`, `availability` |
| (c) `availability` | `non testée (aucune requête réseau effectuée)` — MILES ne contacte pas le fournisseur sans demande |

Mauvais jeton : doit répondre **401**, et non ouvrir une session.

```bash
curl -s -o /dev/null -w "jeton faux : %{http_code}\n" -X POST $BASE/session \
  -H "Content-Type: application/json" -d '{"token":"faux"}'
```

---

## 7. Phase 7 — Le mode réseau se refuse (preuve de sécurité)

Cette phase vérifie que l'exposition réseau **ne peut pas** s'activer par
accident. Elle n'ouvre rien.

```bash
cd /opt/Milescorp

# a) Sans jeton configuré : refus, code 1
env -u MILES_WEB_AUTH_TOKEN MILES_ENV_FILE=/dev/null \
  python3 miles.py --web --web-lan --web-port 8098
echo "code de sortie = $?"

# b) Avec jeton mais sans adresse privée nommée : refus, code 1
MILES_WEB_AUTH_TOKEN=jeton-de-test MILES_ENV_FILE=/dev/null \
  python3 miles.py --web --web-lan --web-port 8098
echo "code de sortie = $?"

# c) Avec une adresse publique : refus, code 1
MILES_WEB_AUTH_TOKEN=jeton-de-test MILES_WEB_LAN_HOST=8.8.8.8 MILES_ENV_FILE=/dev/null \
  python3 miles.py --web --web-lan --web-port 8098
echo "code de sortie = $?"

# d) --web-lan sans --web : refus, code 1
python3 miles.py --web-lan
echo "code de sortie = $?"
```

| Cas | Message attendu | Code |
|---|---|---|
| (a) | « aucun jeton porteur n'est configuré (`MILES_WEB_AUTH_TOKEN`) » | **1** |
| (b) | « `MILES_WEB_LAN_HOST` doit nommer une adresse privée explicite » | **1** |
| (c) | « n'est pas une adresse privée » | **1** |
| (d) | « `--web-lan` n'a de sens qu'avec `--web` » | **1** |

Aucun de ces cas ne doit faire apparaître `Interface web MILES sur
http://192.168` ni laisser un port ouvert (`ss -ltnp | grep 8098` → rien).

---

## 8. Phase 8 — Backend boîtier

```bash
cd /opt/Milescorp
python3 hardware/packages/backend-box/boxtelemetry.py &   # ou via le service dédié
sleep 1
curl -s http://127.0.0.1:8095/box/telemetry | tee ~/miles-validation/08-box.json
```

| Champ | Attendu |
|---|---|
| `source` | `"boxtelemetry"` |
| `cpu.charge` | liste de 3 nombres (Linux) |
| `temperatures` / `ventilos` | mesures **ou** `[{"etat": "non disponible"}]` — jamais une valeur inventée |
| `injection_esp32.etat` | `"aucun"` tant qu'aucun boîtier n'a envoyé |

Refus sans clé (si vous testez une écoute non locale) :

```bash
MILES_BOX_HOST=192.168.1.10 env -u MILES_BOX_KEY python3 hardware/packages/backend-box/boxtelemetry.py
echo "code de sortie = $?"     # attendu : 1 (REFUS)
```

---

## 9. Phase 9 — Cockpit et télémétrie du boîtier

```bash
MILES_DIR=/opt/Milescorp bash /opt/Milescorp/hardware/packages/pc-miles/cockpit-launcher.sh &
sleep 1
curl -s -o /dev/null -w "cockpit  : %{http_code}\n" http://127.0.0.1:8787/cockpit/
curl -s http://127.0.0.1:8787/api/box | tee ~/miles-validation/09-api-box.json
```

| Situation | Attendu |
|---|---|
| cockpit | `200` (page HTML servie depuis `assets/web`) |
| backend joignable | `200`, JSON `boxtelemetry` |
| backend arrêté | **503** avec `{"etat": "indisponible"}` — **aucune mesure affichée** |

Puis, dans un navigateur sur le mini-PC : `http://127.0.0.1:8787/cockpit/`.
Ouvrir la vue Boîtier. Chaque valeur affichée doit porter un **âge**
(« il y a 3 s »), et un backend arrêté doit afficher « aucune valeur
affichée », jamais un chiffre.

---

## 10. Phase 10 — Boîtier ESP32-S3 (si le matériel est disponible)

1. Créer `platformio.local.ini` (non versionné) avec `WIFI_SSID`,
   `WIFI_PASS`, `BACKEND_URL=http://<IP_privée_du_PC>:8095`, `BOX_KEY`.
2. Démarrer le backend en écoute privée : `MILES_BOX_HOST=<IP_du_PC>`
   (la clé `MILES_BOX_KEY` est alors **obligatoire**, sinon refus au
   démarrage).
3. Flasher : `pio run -c platformio.local.ini -t upload`.
4. Observer : LED **verte** si le backend répond, **rouge** sinon ; puis

```bash
curl -s http://127.0.0.1:8095/box/telemetry | python3 -m json.tool | grep -A4 injection
```

| Attendu | Signification |
|---|---|
| `"etat": "recu"` avec `age_s` faible | le boîtier pousse bien ses relevés |
| `"etat": "recu mais perime"` | backend vivant, boîtier muet depuis > 60 s |
| `"etat": "aucun"` | rien reçu : vérifier `BOX_KEY`, `BACKEND_URL`, WiFi |

---

## 11. Phase 11 — Intégrité des archives livrées

```bash
cd ~/miles-paquet           # là où l'archive a été décompressée
sha256sum -c SHA256SUMS | tee ~/miles-validation/11-archives.log
```

| Attendu | Interdit |
|---|---|
| une ligne `OK` par archive, aucune `FAILED` | toute divergence |
| `tar tzf miles-esp32-s3-*.tar.gz` sans `.pio/` | artefacts de compilation |
| aucun `.env`, `*.pem`, `box_state.json` | secrets |

---

## 12. Phase 12 — Redémarrage (l'étape qu'on oublie)

```bash
sudo reboot
# après redémarrage :
systemctl is-active miles                       # attendu : active
ss -ltnp | grep 8080                            # attendu : 127.0.0.1:8080
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/status   # 401
```

> **Limite connue** : le backend boîtier (`boxtelemetry.py`) et le cockpit
> (`cockpit-launcher.sh`) ne sont **pas** fournis comme unités systemd. Ils se
> relancent à la main. C'est un manque identifié, pas un comportement voulu.

---

## 13. Grille de résultats (à remplir sur le mini-PC)

| # | Contrôle | Attendu | Observé | OK |
|---|---|---|---|---|
| 1 | Préflight | aucune écriture, OS/Python conformes | | ☐ |
| 2 | Première passe | code 1, `.env` en 600 | | ☐ |
| 3 | Configuration lue | `provider` = remote/local | | ☐ |
| 4 | Seconde passe | code 0, tests 0 échec | | ☐ |
| 5 | Service | `active`, `User=miles` | | ☐ |
| 6 | Écoute | `127.0.0.1` seulement | | ☐ |
| 7 | Web sans session | 401 | | ☐ |
| 8 | Web avec session | 200 + JSON | | ☐ |
| 9 | Jeton faux | 401 | | ☐ |
| 10 | Refus LAN (4 cas) | code 1, aucun port ouvert | | ☐ |
| 11 | Backend boîtier | `source: boxtelemetry` | | ☐ |
| 12 | Cockpit | 200 ; `/api/box` 200 ou 503 | | ☐ |
| 13 | Télémétrie | valeur **avec âge**, ou rien | | ☐ |
| 14 | Archives | `OK` partout, aucun secret | | ☐ |
| 15 | Redémarrage | service actif, 401 | | ☐ |

**Conclusion** : à remplir en une phrase, en distinguant explicitement ce qui
a été observé de ce qui n'a pas pu l'être.

---

## 14. Repli (si quelque chose casse)

Aucune étape ne détruit de données, mais pour revenir à l'état antérieur :

```bash
sudo systemctl disable --now miles
sudo rm -f /etc/systemd/system/miles.service
sudo systemctl daemon-reload
```

Le répertoire `/opt/Milescorp` et son `.env` sont conservés : les supprimer
effacerait la configuration et les bases `data/`. Ne le faire qu'en
connaissance de cause.

---

*Références : [`INSTALL.md`](INSTALL.md) (variables reconnues),
[`BOX_DEBIAN_SETUP.md`](BOX_DEBIAN_SETUP.md) (installation pas-à-pas et règle
d'exposition), [`hardware/packages/pc-miles/README.md`](../../hardware/packages/pc-miles/README.md)
(paquet PC), `DEC-016`, `DEC-019`, `DEC-020`.*
