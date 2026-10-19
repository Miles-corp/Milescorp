# docs/coordination/STATUS.md — État du projet MILES

## État général (2026-10-19)

- **Projet** : MILES — dépôt GitHub privé `https://github.com/Miles-corp/Milescorp.git`
- **Branche** : `main` (à jour avec `origin/main`, working tree propre)
- **Contenu actuel** : `.gitattributes` (initial), documents de coordination (Mission 001, commit c71d3af), prototype DEV-001 (commit 416dc2e), correction Agent B (commit 153bb16). Code fonctionnel : interface terminal, fournisseurs IA hybride, contexte conversationnel, actions locales, tests, configuration.
- **Mission en cours** : Mission 001 — terminée. Prototype DEV-001 — créé et publié (Agent A, commit 416dc2e). Révision Agent B — intégrée (commit 153bb16, Agent B). Consolidation Debian 13 (TASK-DEV-003) — en préparation (Agent B).

## Prochain objectif

- Valider le prototype sur Debian 13 : démarrage de `miles.py`, exécution des tests (`python3 -m unittest discover -s tests -v`), vérification de l'absence de secrets, confirmation de la documentation d'installation.
- Poursuivre TASK-002 à TASK-004 (revue indépendante de l'organisation par Agent B).

## Tâches actives

| ID | Titre | Statut | Assigné à |
|----|-------|--------|-----------|
| TASK-001 | Mise en place de la structure de coordination | DONE | Agent A |
| TASK-002 | Revue indépendante de l'organisation | TODO | Agent B |
| TASK-003 | Vérification des consignes et tests documentés | TODO | Agent B |
| TASK-004 | Détection des oublis et des ambiguïtés | TODO | Agent B |
| TASK-DEV-001 | Premier prototype fonctionnel MILES | DONE | Agent A |
| TASK-DEV-002 | Revue indépendante des tests et vérification | TODO | Agent B |
| TASK-DEV-003 | Consolidation du prototype et validation sur Debian 13 | TODO | Agent B |

## Blocages

Aucun blocage à ce jour.

## Décisions récentes

- DEC-001 à DEC-004 acceptées (voir `docs/coordination/DECISIONS.md`).

## Notes

- Les deux PC possèdent leur propre clone local du dépôt.
- La communication est asynchrone via GitHub ; aucun mécanisme direct entre les instances OpenCode n'est installé.
- Avant de commencer une tâche, consulter les messages non résolus dans `MESSAGES.md` (statut `[EN ATTENTE]`).
