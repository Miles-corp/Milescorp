# Phase 7 — Cockpit web de contrôle du projet

- **Auteur** : Agent A
- **Date** : 2026-10-27
- **Tâche** : `TASK-DEV-043` — statut **DONE** (clôturée par le cockpit lui-même, journal d'audit à l'appui)
- **Branche** : `feat/miles-cockpit-ui`, créée depuis `origin/integration/miles-post-d1` (`05b7b82`)
- **Fusion** : aucune. **Push** : aucun.

## 1. Objectif

Le pilotage du projet n'était visible nulle part : il fallait ouvrir `TASKS.md`, `STATUS.md`, `DECISIONS.md` et `MESSAGES.md` à la main. L'interface web existante ne montrait que la conversation, la mémoire et les outils, et son HTML/CSS/JS vivaient dans une `f-string` de 290 lignes dans `app/interface/web.py`.

Livrable : **un cockpit de pilotage dans l'interface existante**, avec lecture des documents de coordination et écriture strictement bornée du statut des tâches.

## 2. Ce qui a été livré

| Fichier | Rôle |
|---|---|
| `app/interface/project_board.py` (nouveau, stdlib) | Lecture de `TASKS.md`, `STATUS.md`, `DECISIONS.md`, `MESSAGES.md` ; synthèse ; écriture garde-fous du statut |
| `app/interface/web.py` | 3 routes API + service des ressources statiques ; `_build_index_html` lit désormais `assets/web/index.html` (290 lignes de `f-string` supprimées) |
| `assets/web/index.html` (nouveau) | Coque de page : connexion, 4 onglets, panneaux du cockpit |
| `assets/web/app.css` (nouveau) | Thème sombre/clair, responsive, focus visible, cible 44 px |
| `assets/web/app.js` (nouveau) | Session en mémoire, onglets accessibles, rendu du pilotage, écriture des statuts, chat, mémoire, outils |
| `tests/test_web_project_board.py` (nouveau) | 31 tests : lecture, garde-fous, routes HTTP, traversée de chemin, ressources |
| `.gitignore` | `data/*.jsonl` (journal d'audit hors Git) |

### Routes ajoutées

| Méthode | Route | Protection | Rôle |
|---|---|---|---|
| GET | `/api/project` | session | Pilotage complet + santé du service |
| GET | `/api/tasks` | session | Tâches + synthèse + anomalies |
| POST | `/api/tasks/<id>/status` | session + CSRF + JSON | Écriture du seul statut |
| GET | `/app.css`, `/app.js` | public (aucune donnée) | Ressources statiques, liste blanche stricte |

Les 18 routes existantes sont inchangées.

## 3. Les garde-fous de l'écriture

Écrire dans les documents de coordination depuis une page web est la partie risquée. Sept barrières, toutes testées :

1. **Un seul fichier modifiable** (`TASKS.md`). Aucun chemin ne vient de la requête ; l'identifiant est validé par `^TASK(?:-DEV)?-\d{3}$` avant toute lecture.
2. **Transitions bornées** : `TODO → IN_PROGRESS/BLOCKED/CANCELLED`, `IN_PROGRESS → DONE/BLOCKED/CANCELLED`, `BLOCKED → IN_PROGRESS/CANCELLED`. Une tâche `DONE` ou `CANCELLED` n'est plus modifiable depuis l'interface (réouverture manuelle assumée).
3. **Propriétaire vérifié** : une tâche `IN_PROGRESS` ou `BLOCKED` appartenant à l'autre agent est refusée (HTTP 403, règle anti-conflit d'`AGENTS.md` §4).
4. **Refus plutôt que corruption** : ligne à moins de 10 colonnes, identifiant présent deux fois, statut ou agent illisible → refus explicite, fichier intact.
5. **Écriture atomique** : fichier temporaire dans le même répertoire, `fsync`, `os.replace`. Fins de ligne CRLF préservées.
6. **Audit avant écriture** : une ligne JSONL horodatée (horodatage, tâche, agent, ancien statut, nouveau statut, ligne) est écrite **avant** la modification ; si le journal est inaccessible, l'écriture est refusée. Le journal vit dans `data/`, ignoré par Git.
7. **Session + CSRF** : la route d'écriture passe par les contrôles existants (`do_POST` : origine, `application/json`, session, jeton CSRF) avant tout effet de bord.

## 4. Vérifications exécutées

| Contrôle | Résultat |
|---|---|
| Tests dédiés (`tests.test_web_project_board`) | **31/31 OK** |
| Suites web existantes (`test_web`, `test_web_security`, `test_web_security_phase6_1`) | **82/82 OK** |
| Suite complète (`python -m unittest discover -s tests`) | **845/847 OK**, 5 ignorés, **2 échecs environnementaux préexistants** |
| Audit design du Lab (`competences/web-design/AUDIT.py`) | **100/100 — excellente** |
| Syntaxe JavaScript (`node --check`) | OK |
| Vérification navigateur réelle | session, CSRF, **46 tâches** affichées, santé, décisions, un seul `h1`, colonne terminée repliée |

Les 2 échecs (`test_status_provider_diagnostics`) sont antérieurs à cette phase : le `.env` du poste écrase les valeurs par défaut attendues par deux tests. Preuve : avec `MILES_ENV_FILE` pointant sur un fichier absent, le module passe **14/14**.

### Défauts trouvés et corrigés pendant la vérification

- **Routes statiques derrière le contrôle de session** : `/app.css` répondait 401. Les ressources publiques sont désormais servies avant l'authentification, comme la coque de page.
- **Comparaison de liste blanche** : `path` valait `/app.css` alors que la clé valait `app.css` — la condition ne matchait jamais.
- **`hidden` écrasé par `display: flex`** : la barre de session restait visible avant connexion. Règle `[hidden] { display: none !important; }`.
- **Titre du tableau dans la grille** : le `h2` occupait une colonne de la grille à deux colonnes et décalait le tableau.
- **Sélecteur présélectionné sur « Bloqué »** : une fausse manipulation pouvait bloquer une tâche. Remplacé par un choix explicite (« Changer… ») et un bouton inactif tant qu'aucun statut n'est choisi.
- **Colonne « Terminé » de 30 cartes** : repliée à 6 avec un bouton « Afficher les autres ».

## 5. Design

- Un seul `<h1>` (« MILES »), hiérarchie `h2`/`h3` sans saut.
- Thème sombre par défaut, thème clair via `prefers-color-scheme`, aucune police distante, aucune dépendance.
- Cibles cliquables ≥ 44 px, `:focus-visible` explicite, `aria-live` sur la synthèse et les messages, onglets au clavier (flèches, Home/End), lien d'évitement.
- Responsive : 4 colonnes → 2 → 1 ; barre supérieure qui se replie.

## 6. Limites

- L'identité « Agent A / Agent B » est **déclarée dans l'interface**, pas authentifiée : le serveur ne sait pas quel agent est l'utilisateur du jeton. Le garde-fou anti-conflit est donc une protection contre l'erreur, pas contre l'usurpation. Toute correspondance compte ↔ agent demanderait une décision d'architecture.
- La réouverture d'une tâche `DONE` reste manuelle (choix assumé : pas de clic qui efface une clôture).
- Le cockpit **écrit** dans `TASKS.md` mais ne crée ni ne supprime de tâche : hors périmètre.
- Aucun test sous Debian 13 (VM d'audit injoignable), comme pour les phases précédentes.
- `STATUS.md` est lu par sections nommées ; un renommage de section fait retomber le panneau sur `## Blocages`.

## 7. Prochaine action

1. Décider de la fusion de `feat/miles-cockpit-ui` dans `integration/miles-post-d1`.
2. Aligner `main` (69 commits de retard) — local d'abord, push sur accord.
3. Exécuter la liste de nettoyage Git de `docs/reports/REPO_TRIAGE_AGENT_A.md` §7 après accord explicite.
4. Faire auditer la Phase 7 par Agent B (garde-fous d'écriture et journal d'audit en priorité).
