# AGENT_START.md — Point d'entrée pour tout agent OpenCode travaillant sur MILES

## Ordre minimal de lecture (environ 10 minutes)

1. `AGENTS.md` — règles permanentes (obligatoires).
2. `docs/coordination/MISSIONS_REGISTRY.md` — registre global des missions actives.
3. Les messages `[EN ATTENTE]` de `docs/coordination/MESSAGES.md`.
4. La continuation de la mission visée : `docs/coordination/continuations/MI-###.md`.
5. Si nécessaire : la section datée correspondante de `docs/coordination/STATUS.md`
   et/ou `docs/coordination/HANDOFF.md` (H-###), en lecture ciblée (recherche, jamais
   relecture complète).

## Règles critiques

- `git status` avant toute modification ; vérifier `TASKS.md` avant d'attribuer un travail.
- Ne jamais fusionner une branche qui attend un audit indépendant (Agent B).
- Ne jamais présenter un rapport d'Agent A comme un audit d'Agent B.
- Une mission `AWAITING_AUDIT` ne devient `DONE` qu'après un rapport d'audit B vérifiable.
- « Debian 13 » reste `NON VALIDÉ` tant que les tests n'y ont pas été exécutés.
- Jamais `git push --force`, `git reset --hard`, ni nettoyage de worktree sans accord.
- Un seul worktree par tâche ; tout artefact de coordination en fin de session
  (H-### + mise à jour du registre).
- Ne jamais supprimer un rapport historique ; archiver, ne pas effacer.

## Aide mémoire du dépôt

- Statuts : `TODO`, `IN_PROGRESS`, `IMPLEMENTED`, `TESTED`, `AWAITING_AUDIT`, `BLOCKED`, `DONE`, `CANCELLED`.
- Documentation : `docs/coordination/` (coordination) et `docs/reports/` (rapports).
- Registre individuel de chaque agent : `docs/coordination/agents/AGENT_*.md`.
- Statut d'archivage : `docs/coordination/archive/INDEX.md`.
