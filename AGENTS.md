# AGENTS.md — MILES

Règles permanentes applicables à tous les agents OpenCode travaillant sur le projet MILES.

## 1. Identifiants des agents

- `Agent A` : PC principal, utilisateur git `DripMind` (`sellisphere@hotmail.com`). Responsable initial de la structure de coordination.
- `Agent B` : second PC, développeur indépendant. Responsable de la revue indépendante, des vérifications et des tests documentés.

Chaque agent doit s'identifier dans chaque modification de document de coordination (champ `author` / `modifié-par`).

## 2. Règles obligatoires

1. Avant toute tâche, lire `AGENTS.md`, `docs/coordination/TASKS.md`, `docs/coordination/STATUS.md` et les décisions pertinentes dans `docs/coordination/DECISIONS.md`.
2. Vérifier l'état Git (`git status`) avant toute modification.
3. Prendre une tâche attribuée avant de travailler : passer son statut à `IN_PROGRESS` et renseigner `assigned-to` dans `TASKS.md`.
4. Définir les fichiers autorisés et le résultat attendu de chaque tâche avant de commencer.
5. Ne jamais modifier simultanément les mêmes fichiers qu'un autre agent sans coordination explicite via `TASKS.md` / `STATUS.md`.
6. Ne pas considérer une conversation OpenCode comme une source de vérité partagée entre les deux PC.
7. Documenter toute décision d'architecture dans `docs/coordination/DECISIONS.md`.
8. Exécuter les contrôles pertinents après chaque modification.
9. Ne jamais prétendre qu'un test a réussi s'il n'a pas réellement été exécuté.
10. Documenter les erreurs, les limites et les éléments restant à faire.
11. Ne pas écraser le travail local d'un développeur.
12. Ne jamais publier de secrets, clés API, mots de passe ou données personnelles.
13. Ne pas modifier des fichiers hors du périmètre attribué.
14. En cas de conflit ou d'incertitude structurante, arrêter uniquement l'action concernée et expliquer le problème.

## 3. Communication entre agents

- Asynchrone uniquement, via les fichiers Markdown de `docs/coordination/` et GitHub.
- Aucun mécanisme de communication directe entre les deux instances OpenCode n'est installé.
- Les assignations de tâches transitent par `docs/coordination/TASKS.md`.
- L'état du projet et les prochains objectifs transitent par `docs/coordination/STATUS.md`.
- Les questions, blocages et résultats transitent par `docs/coordination/TASKS.md` et, le cas échéant, par un compte rendu suivant `docs/coordination/REPORT_TEMPLATE.md`.

## 4. Périmètre de la mission en cours (Mission 001)

- Organisation, documentation et règles de collaboration uniquement.
- Aucun développement fonctionnel de l'assistant MILES.
- Aucun secret, aucune donnée personnelle dans les documents.

## 5. Répartition initiale (provisoire)

| Rôle | Agent | Responsabilités |
|------|-------|-----------------|
| Coordination | Agent A | structure de coordination, règles communes, cohérence des documents, intégration des changements validés |
| Revue et vérification | Agent B | revue indépendante de l'organisation, vérification des consignes, tests et contrôles documentés, détection des oublis et ambiguïtés |

Cette répartition est modifiable explicitement dans `docs/coordination/TASKS.md`.
