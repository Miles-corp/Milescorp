# docs/coordination/TASKS.md — Tableau de suivi des tâches MILES

Convention :
- ID : `TASK-###`
- Statuts : `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`
- Agents : `Agent A`, `Agent B`
- Une tâche est terminée uniquement quand son statut est `DONE`, le résultat attendu produit, et les contrôles exécutés.
- Règle anti-conflit : un agent ne passe une tâche en `IN_PROGRESS` qu'après avoir commis la ligne dans ce fichier. Seul le propriétaire d'une tâche en `IN_PROGRESS` ou `BLOCKED` peut la modifier.

## Tâches en cours / initiales (Mission 001)

| ID | Titre | Description | Statut | Assigné à | Fichiers concernés | Résultat attendu | Bloqué par | Créé le | Mis à jour le |
|----|-------|-------------|--------|-----------|--------------------|------------------|------------|---------|---------------|
| TASK-001 | Mise en place de la structure de coordination | Créer AGENTS.md et les documents de docs/coordination/ | IN_PROGRESS | Agent A | AGENTS.md, docs/coordination/*.md | Documents de coordination cohérents, règles définies, workflow Git documenté | — | 2026-10-19 | 2026-10-19 |
| TASK-002 | Revue indépendante de l'organisation | Vérifier que les consignes sont claires, complètes et applicables par Agent B | TODO | Agent B | docs/coordination/*.md, AGENTS.md | Liste des oublis, ambiguïtés et suggestions d'amélioration | — | 2026-10-19 | — |
| TASK-003 | Vérification des consignes et tests documentés | Exécuter les contrôles réalisables sur les documents de coordination et consigner les résultats | TODO | Agent B | docs/coordination/*.md | Rapport de vérification (contrôles exécutés et résultats) | — | 2026-10-19 | — |
| TASK-004 | Détection des oublis et des ambiguïtés | Identifier ce qui manque ou ce qui est mal défini dans l'organisation | TODO | Agent B | docs/coordination/*.md, AGENTS.md | Liste d'éléments à corriger ou préciser | — | 2026-10-19 | — |

## Règles d'attribution

- Une tâche `TODO` peut être prise par l'agent désigné ou, à défaut, par l'agent disponible après coordination explicite.
- Une tâche `IN_PROGRESS` appartient à l'agent indiqué dans `assigned-to` ; l'autre agent ne doit pas y travailler sans accord.
- Une tâche `BLOCKED` doit faire l'objet d'une explication dans `STATUS.md` avant toute réassignation.
