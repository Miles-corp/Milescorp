# docs/coordination/STATUS.md — État du projet MILES

## État général (2026-10-19)

- **Projet** : MILES — dépôt GitHub privé `https://github.com/Miles-corp/Milescorp.git`
- **Branche** : `main` (à jour avec `origin/main`, working tree propre)
- **Contenu actuel** : uniquement `.gitattributes` (commit initial `f4c525e`). Aucun code fonctionnel, aucune documentation de coordination existante avant cette mission.
- **Mission en cours** : Mission 001 — terminée (documents de coordination publiés, commit c71d3af).
- **Mission suivante** : Mission DEV-001 — premier prototype fonctionnel MILES : création initiale terminée par Agent A (statut DONE). En attente de publication sur GitHub, puis revue et tests par Agent B (TASK-DEV-002).

## Prochain objectif

- Publier les documents de coordination et le prototype DEV-001 sur GitHub (après autorisation).
- Faire relire et valider l'organisation par Agent B (TASK-002 à TASK-004).
- Faire exécuter et vérifier les tests par Agent B sur Debian 13 (TASK-DEV-002).

## Tâches actives

| ID | Titre | Statut | Assigné à |
|----|-------|--------|-----------|
| TASK-001 | Mise en place de la structure de coordination | DONE | Agent A |
| TASK-002 | Revue indépendante de l'organisation | TODO | Agent B |
| TASK-003 | Vérification des consignes et tests documentés | TODO | Agent B |
| TASK-004 | Détection des oublis et des ambiguïtés | TODO | Agent B |
| TASK-DEV-001 | Premier prototype fonctionnel MILES | DONE | Agent A |
| TASK-DEV-002 | Revue indépendante des tests et vérification | TODO | Agent B |

## Blocages

Aucun blocage à ce jour.

## Décisions récentes

- DEC-001 à DEC-004 acceptées (voir `docs/coordination/DECISIONS.md`).

## Notes

- Les deux PC possèdent leur propre clone local du dépôt.
- La communication est asynchrone via GitHub ; aucun mécanisme direct entre les instances OpenCode n'est installé.
- Avant de commencer une tâche, consulter les messages non résolus dans `MESSAGES.md` (statut `[EN ATTENTE]`).
