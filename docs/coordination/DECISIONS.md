# docs/coordination/DECISIONS.md — Registre des décisions MILES

Convention : chaque décision reçoit un ID `DEC-###` (ou `D-###`), une date, un auteur, un contexte, la décision et un statut (`PROPOSEE`, `ACCEPTEE`, `REJETEE`, `OBSOLETE`). Journal append-only : les décisions ne sont jamais modifiées rétroactivement.

## DEC-001 — Système de coordination asynchrone par fichiers Markdown

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Deux instances OpenCode sur deux PC distincts, aucun serveur permanent, aucun service payant, pas de communication directe entre agents.
- **Décision** : La coordination s'appuie exclusivement sur des fichiers Markdown dans `docs/coordination/` (`AGENTS.md`, `WORKFLOW.md`, `TASKS.md`, `DECISIONS.md`, `STATUS.md`, `HANDOFF.md`, `REPORT_TEMPLATE.md`), synchronisés via Git et GitHub. La communication est asynchrone.
- **Statut** : ACCEPTEE

## DEC-002 — Identifiants des agents et format des tâches

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Il faut distinguer clairement les deux agents et tracer chaque tâche.
- **Décision** : Les agents sont `Agent A` (PC principal, git `DripMind`) et `Agent B` (second PC). Les tâches utilisent l'identifiant `TASK-###` avec les statuts `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`.
- **Statut** : ACCEPTEE

## DEC-003 — Pas de développement fonctionnel dans la Mission 001

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : La mission 001 concerne uniquement l'organisation, la documentation et les règles de collaboration.
- **Décision** : Aucune fonctionnalité de l'assistant MILES n'est développée durant cette mission.
- **Statut** : ACCEPTEE

## DEC-004 — Aucun push automatique vers GitHub

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : L'utilisateur a demandé de ne rien publier sans son autorisation.
- **Décision** : Les documents sont créés localement. Aucun commit ni push n'est effectué sans accord explicite pour publier.
- **Statut** : ACCEPTEE

## DEC-005 — Architecture hybride distant/local avec sélection explicite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande un fournisseur local sur PC avec GPU NVIDIA (RTX 3050, 4 Go VRAM détectés via nvidia-smi).
- **Décision** : Réutiliser `LocalProvider` existant (serveur local HTTP type Ollama/llama.cpp). Aucune réécriture des fournisseurs distants. Sélection explicite via `MILES_PROVIDER` ou `--provider`. Pas de basculement silencieux. Diagnostic GPU via `nvidia-smi` (lecture seule, optionnel). MILES ne télécharge aucun modèle.
- **Statut** : ACCEPTEE
