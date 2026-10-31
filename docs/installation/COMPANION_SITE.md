# Ouvrir Miles Companion

Guide vérifié sur ce dépôt (Python 3.12.10, Node 26.13.0, Windows 11) : chaque
commande ci-dessous a été exécutée depuis un build refait de zéro et une base
vierge. Le site est servi par la box, en boucle locale, sans compte public.

## 1. En trois commandes

Prérequis : **Python >= 3.12** (vérifié sur 3.12.10) et **Node >= 22**
(vérifié sur 26.13.0) pour reconstruire la coque ; aucune dépendance Python
n'est nécessaire au-delà de la bibliothèque standard.

Depuis la **racine du dépôt** :

```bash
# 1. Construire la coque servie (Node >= 22 ; une seule fois, puis après
#    chaque modification de l'interface).
cd app/interface/companion/frontend
npm ci
npm run build
cd -

# 2. Créer l'administrateur si la base est neuve (interactif).
python -m app.interface.companion.auth add admin --role admin

# 3. Servir.
python -m app.interface.companion.server
```

Puis ouvrir **http://127.0.0.1:8787/**.

Sans session, `/` affiche la présentation publique. Le bouton
« Ouvrir le cockpit » mène à `/connexion` ; après connexion, on arrive sur
`/` (accueil du cockpit). Les pages sont en français :

| Page | Adresse |
| --- | --- |
| Accueil | `/` |
| Missions | `/missions`, détail `/missions/<id>` |
| Routines | `/routines` |
| Conversation MILES | `/miles` |
| Mémoire | `/memoire` |
| Boîtier et capteurs | `/boitier` |
| Fournisseurs IA | `/ia` |
| Réglages | `/reglages` |
| Journal (mode développeur) | `/journal` |
| Découvrir / Appairer | `/decouvrir`, `/appairer` |
| Présentation publique | `/presentation` |
| Ancien cockpit (servi tel quel) | `/cockpit/` |

Toutes les données passent par une seule base d'API, `/api/companion`
(par exemple `/api/companion/me`, `/api/companion/auth/login`). Sans session,
chaque route répond `401 {"error":"Session requise."}` : c'est le moyen le plus
rapide de vérifier qu'un serveur tourne **sans** ouvrir de navigateur.

## 2. Comptes et base

- La base est **`data/companion.db`**, ignorée par Git. Sauvegarde : copier ce
  fichier (et `data/companion-audit.jsonl` si présent).
- `COMPANION_DB=/autre/chemin.db` isole une instance (tests, démonstration).
  La variable n'est lue qu'à la **première** création de la base dans le
  processus : la changer après coup est ignorée sans message (voir piège 10).
- Lister les comptes : `python -m app.interface.companion.auth list`.
- Changer un mot de passe : `python -m app.interface.companion.auth password <identifiant>`.
- Deux administrateurs maximum ; les autres comptes sont utilisateurs.
- Le mot de passe fait **12 caractères minimum**. La commande `add` et
  `password` demandent la saisie **deux fois**, dans un vrai terminal.

## 3. Ce qui fonctionne sans MILES

Sans MILES démarré, le site reste utilisable et le dit :

- capteurs réels du poste (`/boitier`), comptes, sessions, appairage,
  installation de l'application, présentation ;
- l'accueil affiche « MILES non connecté — jeton absent » et
  « backend muet » pour le boîtier ;
- `/missions` et les actions passent par un état lisible
  « MILES non configuré sur la box. » — code HTTP 503 côté API, jamais une
  valeur inventée ;
- `/ia` affiche « non configuré » et ne propose aucun champ de clé : la clé
  se saisit uniquement sur la page locale `/setup`, ouverte sur la box.

Pour activer MILES : lancer `python miles.py --web` (défaut
`127.0.0.1:8080`), puis fournir le jeton à Companion. Il est lu dans
l'environnement, puis dans le `.env` du dépôt :

```bash
export COMPANION_MILES_TOKEN=...   # ou MILES_WEB_AUTH_TOKEN=... dans .env
python -m app.interface.companion.server
```

`COMPANION_MILES_URL` (défaut `http://127.0.0.1:8080`) et `COMPANION_BOX_URL`
(défaut `http://127.0.0.1:8095`) permettent de viser une autre instance.

## 4. Installer le cockpit comme application

Le site embarque un manifeste et un service worker : Chrome ou Edge proposent
« Installer Miles Companion », qui ouvre le cockpit dans sa propre fenêtre et
garde la coque en cache. Cela fonctionne sur `http://127.0.0.1` (ou HTTPS),
**pas** sur une adresse LAN en `http://`. Le service worker ne met jamais
`/api/` en cache : les mesures et les missions demandent toujours la box.

### Vérifié le 30 octobre 2026

Sur ce dépôt, serveur relancé sur `--port 8791` (base existante) :

```
/healthz                                 200
/                                        200
/presentation                            200
/connexion                               200
/assets/c8cede45891b...c3a7.mp4          200, 10 124 713 octets
/api/companion/me                        401 {"error":"Session requise."}
POST /api/companion/auth/login (faux)    401 {"error":"Identifiant ou mot de passe incorrect."}
pytest (5 fichiers Companion)            84 passed in 40.92s
```

La base de ce worktree contient déjà trois comptes (`admin`, `agent-test`,
`admin_a`) : inutile d'en recréer un pour ouvrir le site.

## 5. Après une modification de l'interface

```bash
cd app/interface/companion/frontend && npm run build
```

Le serveur relit `dist/` à chaque requête : pas besoin de le redémarrer pour un
changement d'interface. En revanche, un changement **Python** exige de
redémarrer le serveur (voir les pièges).

Contrôles utiles :

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/healthz   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/          # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/cockpit/  # 200
```

Tests Companion (aucun réseau, base temporaire) :

```bash
python -m pytest tests/test_companion_auth.py tests/test_companion_pairing.py \
  tests/test_companion_sensors.py tests/test_companion_server.py \
  tests/test_companion_static_assets.py -q
# 84 passed (mesuré)
```

## 6. Pièges réels, mesurés

1. **Deux serveurs sur le même port, sans erreur (Windows).** Un second
   `server.py --port 8787` démarre et affiche son message de succès : le port
   est partagé (`SO_REUSEADDR`), et les requêtes tombent sur l'un ou l'autre
   processus. Symptôme observé : mot de passe refusé alors qu'il est correct,
   parce que la requête arrivait sur une instance utilisant une autre base.
   Avant de lancer, vérifier :
   `netstat -ano | findstr :8787` puis arrêter l'ancien PID.
2. **Le serveur déjà lancé garde l'ancien code Python.** Après une correction
   côté serveur, arrêter (Ctrl+C) puis relancer. Sinon les routes répondent
   comme avant.
3. **`auth add` / `password` sont interactifs.** Sans terminal (stdin redirigé,
   script, tâche planifiée), la commande reste bloquée sur la saisie. Utiliser
   un vrai terminal, ou créer le compte par le module `auth` pour un test.
4. **Build absent → 503 « Build absent ».** C'est voulu : la page indique la
   commande `npm ci && npm run build`. Vérifié : `/` renvoie 503 sans `dist/`,
   200 après reconstruction.
5. **Le film n'a pas de son.** Le MP4 livré ne contient qu'une piste vidéo
   H.264 (14 s, 1920×1080, 10,1 Mo). Les textes « quatorze secondes, sans son »
   sont exacts ; ils devront changer avec l'ajout d'une piste audio.
6. **Pas de requêtes `Range` sur les médias.** Le serveur ignore l'en-tête :
   une requête `Range: bytes=0-1023` sur le MP4 renvoie `200` et les 10,1 Mo
   complets. Le film se lit, mais il est toujours téléchargé en entier et la
   lecture repart du début lors d'un déplacement.
7. **Les cookies ne tiennent pas compte du port.** Une session ouverte sur
   `127.0.0.1:8787` est envoyée à tout autre serveur local (`:8791`, etc.).
   Pour tester une instance avec un autre compte, utiliser une fenêtre de
   navigation privée, ou `localhost` au lieu de `127.0.0.1`.
8. **L'écoute réseau est fermée par défaut.** `--lan` exige à la fois
   `COMPANION_ALLOW_LAN=1`, `COMPANION_LAN_HOST=<adresse privée>` et
   `COMPANION_LAN_AUDITED=1` ; sans cela le serveur refuse et reste sur
   `127.0.0.1`.
9. **Avertissements de build attendus.** `assets/fonts.css` et
   `assets/remixicon/remixicon.min.css` sont référencés en absolu
   (`/assets/...`) et ne sont pas copiés dans `dist/` : Vite les signale comme
   « resolved at runtime », et le serveur les sert bien (200 mesuré).
10. **Changer `COMPANION_DB` dans un processus déjà démarré est sans effet.**
   La base est un singleton créé à la première utilisation
   (`store.get_store()`) : affecter `COMPANION_DB` après ce point laisse
   l'instance existante en place, silencieusement, et les commandes
   continuent d'écrire dans `data/companion.db`. Définir la variable **avant**
   de lancer Python, ou repasser par `store.reset_store()`. Si deux shells
   visent des chemins différents, vérifier avec
   `python -m app.interface.companion.auth list` que le compte attendu est là.
