# docs/coordination/HANDOFF.md — Procédure de transmission entre agents

> Point d'entrée des agents : `AGENT_START.md` à la racine du dépôt ; état courant des missions : `MISSIONS_REGISTRY.md`.

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

## 6. Comptes rendus

### H-002 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-018 (correction D1) ; TASK-DEV-019 (audit independant) transferee.

**Travail réalisé :** diagnostic du défaut D1 (divergence de session entre l'emission du grant et sa verification), correction d'une ligne dans `app/orchestration/runner.py::_ensure_authorization`, jeu de 6 tests de regression, execution du scenario web reel, redaction du rapport de correction.

**Fichiers modifiés :** `app/orchestration/runner.py` ; `tests/test_mission_web_authorization.py` (nouveau) ; `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** `6b736d7` — `fix(orchestrateur): autoriser la mission web avec la session du client (D1)` — branche `fix/miles-d1-web-authorization`, pousse sur `origin`. Base `fc179ca`. **Aucune fusion** ; `main` (`b9b7e7d`) et `origin/integration/miles-phases-5-6-6-1` (`69bf670`) inchanges.

**Tests exécutés :** 6/6 tests de regression D1 (le test de regression echoue sans le correctif, verifie) ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security_phase6_1` 35/35 ; suite complete **534 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; scenario web reel (vrai serveur) : `completed`, 5 etapes, 5 appels, 1 echange. Non execute : Debian 13 (environnement indisponible).

**Problèmes restants :** D1-bis signale et non corrige (reponse HTTP trompeuse sur jeton d'approbation invalide ; aucune elevation de privilege). D2, D3, D4 hors perimetre. Validation Debian 13 en attente.

**Prochaine action recommandée :** Agent B prend TASK-DEV-019, audite `6b736d7` (lien grant/session, non-reutilisabilite, scenario web complet, non-regression, Debian 13) et rend son avis avant toute fusion.

### H-003 — 2026-10-24 — Agent A → Agent B

**Tâche :** TASK-DEV-022 (préparation d'intégration) ; TASK-DEV-019 toujours en attente côté B.

**Travail réalisé :** vérification SHA de la chaîne post-D1, état des tests/audits, ordre d'intégration proposé avec dépendances et risques de conflits (voir STATUS.md, section « Préparation d'intégration des branches en attente »). Aucune fusion, aucun code modifié, aucun push.

**Fichiers modifiés :** `docs/coordination/{TASKS,STATUS,MESSAGES,HANDOFF}.md` uniquement.

**Commits :** commit de coordination local (branche `fix/miles-d1-web-authorization`), pas de push.

**Tests exécutés :** aucun (mission de documentation) ; enseignée néanmoins de la date du 24/10 : suite complète 685 tests OK (4 ignorés) au sommet `78ac05c` pour la mission diagnostics `/status`/`/provider`.

**Problèmes restants :** `fix/miles-paths-posix-spaces` pointe sur `25baa60` sans commit dédié (branche non poussée) ; `fix/miles-diagnostics` non poussé ; aucun audit B postérieur à `6b736d7` ; Debian 13 toujours indisponible.

**Prochaine action recommandée :** B audite `6b736d7` (TASK-DEV-019) puis, dans l'ordre, `1ef4878` (D1-bis) et `8b9ab15` (contournement P1-6-06) ; ensuite seulement TASK-DEV-023 (intégration ordonnée).

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
