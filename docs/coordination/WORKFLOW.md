# docs/coordination/WORKFLOW.md — Procédure de collaboration MILES

Procédure complète pour les deux agents travaillant sur deux PC distincts avec chacun un clone local du dépôt.

## 0. Convention d'identification

- Agents : `Agent A` et `Agent B`.
- Identifiant de tâche : `TASK-###` (exemple `TASK-001`).
- Identifiant de décision : `DEC-###`.
- Statuts de tâche : `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`.
- Une tâche est considérée terminée uniquement quand son statut est `DONE`, que le résultat attendu est produit, et que les contrôles pertinents ont été exécutés.

## 1. Workflow Git (deux clones locaux)

1. **Vérifier l'état local** : `git status` et `git log --oneline -5`. Ne travailler que sur un working tree propre ou avec uniquement ses propres modifications en cours.
2. **Récupérer les changements distants** avant de commencer, sans écraser les modifications locales :
   - `git fetch origin`
   - `git status` pour comparer `main` et `origin/main`
   - Si des changements distants existent et ne sont pas en conflit avec son travail : les intégrer via un rebase ou une merge selon l'usage de l'équipe, puis vérifier `git status`.
3. **Vérifier que la tâche n'est pas déjà attribuée** dans `docs/coordination/TASKS.md` (statut différent de `TODO` ou `assigned-to` renseigné par l'autre agent).
4. **Prendre la tâche** : passer son statut à `IN_PROGRESS`, renseigner `assigned-to`, `fichiers-concernes`, `resultat-attendu`, `date-debut`.
5. **Travailler uniquement dans le périmètre défini** (fichiers autorisés listés dans la tâche).
6. **Exécuter les vérifications** pertinentes après chaque modification (tests, lint, relecture du diff).
7. **Relire le diff** : `git diff` avant de committer.
8. **Préparer un compte rendu** suivant `docs/coordination/REPORT_TEMPLATE.md`.
9. **Proposer un commit clair** lorsque le changement est cohérent (message descriptif, pas de secrets).
10. **Synchroniser les changements via GitHub** selon la procédure définie ci-dessous, uniquement après accord pour publier.
11. **Vérifier l'état final** et transmettre la main à l'autre agent via `STATUS.md` / `TASKS.md`.

### Sauvegarder localement vs committer vs pousser

- **Sauvegarder localement** : écrire un fichier sur le disque. Seul l'agent qui l'a écrit le voit. Rien n'est enregistré dans l'historique Git.
- **Committer** : enregistrer une modification dans l'historique local du dépôt (`git commit`). L'historique existe uniquement sur le PC de l'agent qui a commité. L'autre PC ne le voit pas tant qu'il n'est pas poussé.
- **Pousser vers GitHub** : envoyer les commits locaux vers le dépôt distant (`git push`). Seul alors l'autre agent peut les récupérer (`git fetch` / `git pull`).

Règle : dans cette mission, aucun changement n'est poussé automatiquement vers GitHub. Un push n'intervient qu'après accord explicite.

### Règles de non-destruction

N'exécuter jamais : `git reset --hard`, `git clean -fd`, `git push --force`, ni toute commande destructive équivalente. Ne jamais écraser le travail local d'un développeur.

## 2. Attribution et suivi des tâches

- Créer une entrée par tâche dans le tableau de `docs/coordination/TASKS.md`.
- Seule l'agent à qui la tâche est attribuée peut la passer en `IN_PROGRESS`.
- Si un agent est bloqué, il passe la tâche en `BLOCKED` et renseigne `bloque-par` + une description dans `STATUS.md` / `TASKS.md`.
- Une tâche terminée passe en `DONE` avec `date-fin` et, si pertinent, `verifie-par`.
- Aucun agent ne doit reprendre une tâche `DONE` sans créer une nouvelle tâche et en informer l'autre.

## 3. Décisions

- Toute décision d'architecture ou d'organisation doit être enregistrée dans `docs/coordination/DECISIONS.md` avec `id`, `date`, `auteur`, `decision`, `contexte`, `statut`.
- Aucun changement structurant ne doit être implémenté avant que la décision associée ne soit consignée.

## 4. Transmission de main (handoff)

À la fin de sa session, chaque agent :
1. Met à jour `docs/coordination/TASKS.md` (statuts, assignations, blocages).
2. Met à jour `docs/coordination/STATUS.md` (état du projet, prochain objectif).
3. Rédige un compte rendu suivant `docs/coordination/REPORT_TEMPLATE.md` si un livrable est produit.
4. Commite localement ses documents (sans pousser sans accord).
5. Prévient l'autre agent par le canal convenu hors dépôt (ex. message) qu'une mise à jour est disponible sur GitHub, afin qu'il puisse `git fetch`.

## 5. Reprise après interruption

À la reprise de travail sur un PC :
1. Lire `AGENTS.md`, `STATUS.md`, `TASKS.md` et `DECISIONS.md`.
2. `git fetch origin` puis comparer avec l'état local.
3. Identifier les tâches en `IN_PROGRESS` ou `BLOCKED` et décider de les reprendre ou de les réassigner.
4. Ne jamais reprendre une tâche marquée `IN_PROGRESS` par l'autre agent sans coordination explicite.
