# Site Miles Companion propriétaire — rapport de livraison

- **Agent** : Agent A
- **Date** : 2026-10-29
- **Tâche** : `TASK-DEV-064` (implémentation), revue demandée en `TASK-DEV-065`
- **Décision** : `DEC-027`
- **Message** : `M-037`
- **Compte rendu** : `H-017`

## 1. Ce qui a été remplacé

Le Companion était un export Readdy retouché : page pré-rendue, pont
`miles-bridge.js`, relais générique `/api/*`, jeton MILES demandé dans le
navigateur, aucune notion de compte. Le site servi est désormais notre code.

| Avant (Readdy) | Maintenant |
|---|---|
| `index.html` pré-rendu + `miles-bridge.js` | coque React/TypeScript dans `frontend/src/**`, build `dist/` |
| relais `/api/*` générique | `miles_client.py` : liste blanche de routes, session MILES côté serveur |
| jeton MILES saisi dans le navigateur | jeton lu côté serveur (`MILES_WEB_AUTH_TOKEN`), jamais renvoyé |
| `/api/box` public | capteurs lus côté serveur, session exigée |
| aucune identité | comptes locaux, rôles, sessions, CSRF, audit |

L'ancien export reste dans le dossier pour historique, mais **n'est plus
servi** : `/index.html` et `/miles-bridge.js` répondent 404, `/` sert la coque
construite.

## 2. Architecture livrée

- **Serveur** : `app/interface/companion/server.py` (bibliothèque standard).
  Routes `/`, `/connexion`, `/app/*` (bundle), `/assets/*` (polices, icônes),
  `/api/companion/*`, `/setup`, `/cockpit/*`.
- **Comptes** (`auth.py`, `store.py`) : `scrypt` + sel, sessions opaques dont
  seul le SHA-256 est stocké, cookie `HttpOnly` `SameSite=Strict`, CSRF
  synchronisé, verrouillage après 5 échecs, **deux administrateurs maximum**
  garantis par transaction. Base `data/companion.db` (ignorée par Git).
- **Capteurs** (`sensors.py`) : `/proc/stat`, `meminfo`, `loadavg`, `uptime`,
  `net/dev`, `/sys/class/hwmon`, `/sys/class/power_supply`, disque. Chaque
  valeur porte sa source et son horodatage ; une lecture absente renvoie
  `available: false` avec une raison.
- **Boîtier** : `fetch_box()` lit `http://127.0.0.1:8095/box/telemetry`,
  refuse toute cible non locale, et déclare « backend muet » sans inventer de
  valeur.
- **Applets** (`applets.py`) : trois types explicites — `system`, `render`,
  `action`. Toute action exige un jeton de confirmation à usage unique lié au
  compte et à la charge utile.
- **Fournisseurs** (`providers.py`) : catalogue dérivé de la fabrique réelle,
  état « configuré » et modèle seulement ; aucune clé, aucune longueur de clé.
- **Journal** (`audit.py`) : événements expurgés en base + JSONL, anneau
  d'accès HTTP en mémoire (500 entrées), visible en mode développeur.
- **Coque** : neuf vues (Accueil, Boîtier, Missions, Détail de mission,
  Conversation, Mémoire, Routines, IA, Découvrir, Réglages, Journal), navigation
  responsive, confirmation d'action, mode développeur.

## 3. Garanties vérifiées par les tests

| Garantie | Test |
|---|---|
| Mot de passe jamais stocké en clair, sessions hachées | `tests/test_companion_auth.py` |
| Deux administrateurs maximum, élévation refusée | `tests/test_companion_auth.py` |
| CSRF et origine exigés sur les écritures | `tests/test_companion_auth.py` |
| Verrouillage après échecs répétés | `tests/test_companion_auth.py` |
| Mesures réelles, absence motivée, aucun chiffre inventé | `tests/test_companion_sensors.py` |
| Backend boîtier limité à la boucle locale | `tests/test_companion_sensors.py` |
| Routes retirées (`/api/box`, sources du serveur) et coque servie | `tests/test_companion_server.py` |
| Aucun hôte distant dans le build, références locales uniquement | `tests/test_companion_static_assets.py` |

## 4. Résultats exécutés

- **Suite complète** : `python -m unittest discover -s tests -t .`
  → **1038 tests, 0 échec, 5 ignorés** (183,9 s, Windows 11, Python 3.12.10),
  exécutée sur l'arbre final. Les quatre modules Companion ont aussi été
  rejoués seuls : **64 tests OK** (`test_companion_auth`,
  `test_companion_sensors`, `test_companion_server`,
  `test_companion_static_assets`).
- **Build** : `npm run build` → 59 modules, JS 328 Ko (100,3 Ko gzip),
  CSS 19,7 Ko, empreinte `6ae6b924905c9bc1`.
- **Vérification navigateur réelle** sur `http://127.0.0.1:8787` :
  - page de connexion rendue, connexion administrateur acceptée, cookie de
    session posé, redirection vers l'accueil ;
  - accueil : MILES « non configuré », fournisseur « non configuré »,
    backend boîtier « muet », disque réellement mesuré (96,1 %, 17,5 Gio
    libres), CPU/RAM/température « non mesuré » avec leur raison ;
  - bascule du mode développeur depuis les réglages : bandeau, lien Journal,
    détails techniques bruts sur `/boitier` ;
  - journal : 2 événements d'audit (`auth.login`, `dev_mode`) et 25 accès HTTP ;
  - aucune erreur console hors `401` d'avant-connexion (attendu) et `503`
    missions (MILES absent, attendu).

## 5. Ce qui n'a pas été vérifié

- **MILES réel** : processus non démarré ; les états « non configuré » sont
  affichés tels quels, aucune mission n'a été créée ni reléguée.
- **Backend boîtier réel** : non démarré ; la lecture est couverte par un
  serveur factice dans `tests/test_companion_sensors.py`.
- **Fournisseur IA réel** : aucun appel réseau payant effectué ; seule la
  lecture d'état est testée.
- **Écoute LAN** : volontairement refusée sans audit indépendant
  (`COMPANION_LAN_AUDITED=1`) ; elle n'a donc pas été testée.
- **Debian 13** : la vérification a eu lieu sous Windows 11. Les capteurs
  `/proc` et `/sys` y sont indisponibles par conception ; c'est le comportement
  attendu, pas une mesure de la box.
- **Audit de design du Lab** : non exécuté, le Lab est en travaux et la
  consigne utilisateur était de ne pas le lancer complètement.
- **Jumelage box ↔ site (V1)** : non implémenté ici. La spec
  `docs/specs/SITE_PAIRING_IA_SPEC.md` et `TASK-DEV-063` appartiennent à Agent
  A bis ; ce lot livre les comptes locaux et l'onglet IA sans clé côté site,
  pas le jumelage.

## 6. Limites et points ouverts

1. `DEC-026` était déjà pris par Agent A bis (clé API hors du site) : la
   décision de ce lot est **`DEC-027`**.
2. L'export Readdy reste sur disque, non servi. Sa suppression définitive
   demande un accord explicite (il contient l'historique de la refonte).
3. Le changement de mot de passe révoque toutes les sessions, y compris la
   session courante : l'utilisateur doit se reconnecter (comportement annoncé
   dans l'interface).
4. Aucun push n'a été effectué.
