# MEMORY-BUFFY.md — mémoire de travail de l'agent (Agent A)

> Espace mémoire versionné. Il survit aux changements de session : une nouvelle
> instance lit ce fichier **avant** de proposer quoi que ce soit, puis le met à
> jour en fin de tâche. Ce n'est pas un rapport (voir `docs/reports/`) ni une
> décision d'architecture (voir `DECISIONS.md`) : c'est l'état de travail.

## 1. Comment reprendre

1. Lire `AGENTS.md`, puis `TASKS.md`, `STATUS.md`, `DECISIONS.md` (au moins DEC-013).
2. Vérifier `git status` et la branche courante.
3. Lire la section « Prochaine action » ci-dessous.
4. Ne jamais supposer qu'une conversation précédente fait foi : elle n'est pas partagée avec l'autre PC.

## 2. État au 2026-10-27 (session cockpit)

- **Branche de travail** : `feat/miles-cockpit-ui`, créée depuis `origin/integration/miles-post-d1` (`05b7b82`).
- **Vérité du code** : `integration/miles-post-d1`. `main` (`b9b7e7d`) est à **69 commits de retard** et ne doit plus servir de base.
- **Base de tests** : 816 tests, **814 OK**, 5 ignorés, **2 échecs environnementaux** dus au `.env` du poste (`tests/test_status_provider_diagnostics.py`). Sans `.env`, le module passe 14/14.
- **Coordination** : doublons d'identifiants corrigés (DEC-013), `STATUS.md` remis à l'heure, `M-004` → `M-017`, ligne Phase 3B réparée.
- **Tri Git** : inventaire dans `docs/reports/REPO_TRIAGE_AGENT_A.md` ; **aucune suppression exécutée**, liste soumise à accord.

## 3. Décisions de méthode prises cette session

| Sujet | Choix | Pourquoi |
|---|---|---|
| Base de travail | `integration/miles-post-d1` | seule branche à jour ; `main` est un vestige de la Phase 4 |
| Tri Git | liste d'abord, suppression après accord | deux branches locales portent du travail unique non poussé |
| Cockpit | dans l'interface existante, pas un second service | une seule origine, une seule session, zéro dépendance (DEC-007) |
| Écriture des statuts | autorisée, avec garde-fous | demande explicite de l'utilisateur, risque maîtrisé par un fichier unique et des transitions bornées |
| Design | audit via le Lab sur copie de travail | le dépôt n'est pas monté dans le conteneur `devbox` |

## 4. Ce qui a été vérifié (pas supposé)

- `git rev-list --left-right --count HEAD...origin/main` → `0 0` avant création de branche.
- `git for-each-ref` : 29 branches distantes hors `main`, 22 fusionnées, 7 non.
- `git worktree list` : 16 worktrees, 14 sous `%TEMP%`, 2 sales.
- `python -m unittest discover -s tests` : 816 tests, 2 échecs reproduits et expliqués par `.env`.
- Unicité des identifiants : `grep | sort | uniq -d` vide sur `TASKS.md` et `MESSAGES.md` ; 46 lignes de tâches à 10 colonnes.

## 5. Prochaine action

1. ~~Terminer la Phase 7~~ — **fait** : cockpit livré sur `feat/miles-cockpit-ui`, 31 tests dédiés, `TASK-DEV-043` DONE.
2. ~~Audit design du Lab~~ — **fait** : 100/100 sur `Lab/workspaces/miles-cockpit/`.
3. Reste : fusion de la branche dans l'intégration (à décider), alignement de `main`, nettoyage Git.
4. **Attendre l'accord de l'utilisateur** avant toute suppression de branche ou de worktree, et avant tout push.

## 6. Points de vigilance durables

- Ne pas modifier `app/tools/policy.py`, `app/security/paths.py` ni les routes d'autorisation de mission : hors périmètre, audités.
- Ne pas committer `.env`, `data/*.db`, ni les journaux d'audit.
- `main` reste en retard tant que l'utilisateur n'a pas autorisé le réalignement.
- Les audits Agent B en attente (TASK-DEV-019, 021, 024, 027, 030, 032, 034, 037, 039, 041) ne sont **pas** approuvés : ne pas les considérer comme validés.


## 7. Session du 2026-10-27 (suite) — façade unique et télémétrie réelle

**État** : `integration/miles-post-d1` = référence, commit `b8cb2c8` (fusion `f53b03d`). Serveurs relancés depuis le dépôt : MILES `127.0.0.1:8080`, Companion `127.0.0.1:8787` (le jeton d'accès s'affiche au démarrage de MILES).

**Fait dans cette session**
1. Miles Companion (React) copié dans le dépôt, détaché de Readdy : ressources locales, routes propres, filigrane et analytics neutralisés, vidéo d'initialisation conservée.
2. Page « Boîtier » : plus aucune valeur fabriquée — `GET /api/device` (module `device_telemetry.py`, stdlib) renvoie des mesures réelles ou `available: false` + raison ; le pont remplace les tuiles de démonstration et n'allume l'indicateur que sur réponse réelle de MILES.
3. Pièges rencontrés à retenir : (a) les libellés de l'app sont en minuscules dans le DOM (majuscules par CSS) ; (b) une session web MILES est liée au **User-Agent** — une session créée en ligne de commande est refusée dans le navigateur ; (c) remplacer le texte d'un élément animé sans marqueur relance la réparation d'`aria-label` et **bloque le fil principal** (boucle de micro-tâches) : toujours marquer l'élément (`data-mts-live`) et ne jamais ressusciter une valeur simulée.
4. Nettoyage Git (sur accord) : 11 worktrees temporaires propres supprimés, 21 branches distantes fusionnées supprimées. Conservés : `miles-merge`, `miles-diag`.

**Prochaine action**
1. Attendre la revue d'Agent B (`TASK-DEV-044`).
2. Ne rien pousser sans accord (DEC-004) ; `main` reste en retard sur l'intégration.
3. Questions ouvertes posées à l'utilisateur : présentation des valeurs non mesurées, réalignement de `main`, sort des deux worktrees restants, périmètre du prochain lot.

## 8. Session du 2026-10-27 (suite 2) — `main`, tri prouvé, cockpit unique

**État** : référence **`main`**, alignée par avance rapide sur
`integration/miles-post-d1` ; aucun `push`. Serveurs : MILES
`127.0.0.1:8080` (processus démarré avant ce lot), Companion `127.0.0.1:8787`
(relancé avec le code de ce lot).

**Fait**

1. **Tri** : FontAwesome (1,05 Mo, zéro référence) supprimé, 12 `.gitkeep`
   redondants retirés, page Projet dupliquée retirée, `ORGANISATION.md` écrit
   (carte du dépôt, preuves de suppression, où regarder pour chaque changement).
2. **Cockpit unique** : `assets/web/` servi sous `/cockpit/` par le Companion,
   `/projet` redirige, bandeau de santé visible **avant** connexion, icônes
   locales, surface HTTP bornée par liste blanche (`/server.py` → 404).
3. **Worktrees** : rapport unique récupéré (`PHASE_6_4B_DIAGNOSTICS_AGENT_A.md`),
   433 lignes de travail multi-fournisseurs figées sur
   `feature/miles-multi-provider`, puis les deux dossiers `%TEMP%` retirés.
4. **Vérifié, pas supposé** : 876 tests (874 OK, 2 échecs reproduits dans une
   copie de `HEAD` sans `.env` → antérieurs au lot) ; 18 tests nouveaux ;
   navigateur sur 8787 (nav Projet, onglets, bandeau, 0 ressource en échec,
   0 erreur console, 0 débordement à 390 px) ; `git worktree list` propre ;
   audit design du Lab **100/100** sur la copie de travail rafraîchie ;
   audit de fin de tâche `AUDIT-TOUS.py` **vert** (portée : l'espace du Lab).

**Prochaine action**

1. Attendre les revues `TASK-DEV-044` et `TASK-DEV-046` ; mega prompt remis à
   l'utilisateur pour Agent B (`H-014` + `M-019`).
2. `push` de `main` **uniquement** sur accord explicite (DEC-004) : 77 commits
   d'avance sur `origin/main`.
3. Redémarrer `miles.py --web` pour servir l'icône du cockpit sur 8080 —
   attention : un nouveau jeton d'accès est affiché et les sessions en cours
   tombent.
4. Sujets ouverts : cause exacte des 2 échecs de
   `tests/test_status_provider_diagnostics.py` ; intégration (ou abandon) du
   travail multi-fournisseurs ; branche `feature/miles-memoire-avancee`.

**Pièges à retenir**

- Ne jamais poser une valeur sans la marquer : le pont répare les textes depuis
  `aria-label` et une valeur remplacée sans marqueur déclenche une boucle qui
  **bloque le fil principal**.
- Une session web MILES est liée à l'**agent utilisateur** du client.
- Un fichier du dossier Companion n'est pas public par défaut : la liste
  blanche est la seule autorisation.

## Lane 2026-10-28 — lot paquets (revue seule)

- Le lot « paquets téléchargeables (Mode C/WiFi) » appartient à un **second agent**
  (DEC-016). Cette instance ne code pas ce lot : elle relit, arbitre et documente.
- Les six arbitrages sont en DEC-016 ; le message d'application est **M-020**.
- `git push` est **impossible depuis ce shell** (gestionnaire d'identifiants en échec) :
  ne pas promettre une publication ; demander à l'utilisateur de pousser lui-même.
