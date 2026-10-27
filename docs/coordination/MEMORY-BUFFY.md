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
