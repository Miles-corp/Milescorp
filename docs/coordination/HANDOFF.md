# docs/coordination/HANDOFF.md — Procédure de transmission entre agents

Procédure à suivre par chaque agent à la fin de sa session de travail, afin que l'autre agent puisse reprendre le contexte sans perte d'information.

## 1. Avant de quitter

1. Lire `AGENTS.md` (règle 10 et 14) pour s'assurer que les erreurs, limites et éléments restants sont documentés.
2. Mettre à jour `docs/coordination/TASKS.md` :
   - Statut de chaque tâche travaillée (`TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`).
   - `assigned-to`, `fichiers-concernes`, `resultat-attendu`, `date-debut`, `date-fin`.
   - `bloque-par` si une tâche est bloquée, avec explication.
3. Mettre à jour `docs/coordination/STATUS.md` :
   - État général du projet.
   - Prochain objectif clair.
   - Liste des tâches actives et blocages.
4. Consigner toute décision d'architecture dans `docs/coordination/DECISIONS.md` (règle AGENTS.md n°7).
5. Rédiger un compte rendu suivant `docs/coordination/REPORT_TEMPLATE.md` si un livrable est produit.
6. Relire son propre diff (`git diff`) avant de committer localement.
7. Committer localement les documents modifiés (pas de push sans accord explicite).

## 2. Format de compte rendu de transfert (H-###)

### H-001 — 2026-10-19 — Agent X → Agent Y
**Tâche :** TASK-### — …
**Travail réalisé :** …
**Fichiers modifiés :** …
**Commits :** …
**Tests exécutés :** …
**Problèmes restants :** …
**Prochaine action recommandée :** …

## 3. Transmission de la main

- Prévenir l'autre agent (par le canal convenu hors dépôt, ex. message) qu'une mise à jour est disponible sur GitHub ou dans le clone partagé.
- L'autre agent doit alors :
  1. Lire `AGENTS.md`, `STATUS.md`, `TASKS.md` et les décisions pertinentes.
  2. `git fetch origin` et comparer avec son état local.
  3. Ne pas reprendre une tâche `IN_PROGRESS` attribuée à l'autre agent sans coordination explicite.

## 4. Ce qui doit être transmis (minimum)

- Quelles tâches sont terminées, en cours, bloquées.
- Quels fichiers ont été modifiés ou créés.
- Quels contrôles ont été exécutés et avec quel résultat.
- Quelles questions restent ouvertes pour l'autre agent.
- Quelles décisions doivent être prises par un humain.

## 5. Interdictions

- Ne jamais considérer une conversation OpenCode comme la source de vérité partagée.
- Ne jamais écraser le travail local de l'autre agent.
- Ne jamais publier de secrets, clés API, mots de passe ou données personnelles.
