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

## 6. Comptes rendus

### H-002 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-018 (correction D1) ; TASK-DEV-019 (audit independant) transferee.

**Travail réalisé :** diagnostic du défaut D1 (divergence de session entre l'emission du grant et sa verification), correction d'une ligne dans `app/orchestration/runner.py::_ensure_authorization`, jeu de 6 tests de regression, execution du scenario web reel, redaction du rapport de correction.

**Fichiers modifiés :** `app/orchestration/runner.py` ; `tests/test_mission_web_authorization.py` (nouveau) ; `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** `6b736d7` — `fix(orchestrateur): autoriser la mission web avec la session du client (D1)` — branche `fix/miles-d1-web-authorization`, pousse sur `origin`. Base `fc179ca`. **Aucune fusion** ; `main` (`b9b7e7d`) et `origin/integration/miles-phases-5-6-6-1` (`69bf670`) inchanges.

**Tests exécutés :** 6/6 tests de regression D1 (le test de regression echoue sans le correctif, verifie) ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security_phase6_1` 35/35 ; suite complete **534 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; scenario web reel (vrai serveur) : `completed`, 5 etapes, 5 appels, 1 echange. Non execute : Debian 13 (environnement indisponible).

**Problèmes restants :** D1-bis signale et non corrige (reponse HTTP trompeuse sur jeton d'approbation invalide ; aucune elevation de privilege). D2, D3, D4 hors perimetre. Validation Debian 13 en attente.

**Prochaine action recommandée :** Agent B prend TASK-DEV-019, audite `6b736d7` (lien grant/session, non-reutilisabilite, scenario web complet, non-regression, Debian 13) et rend son avis avant toute fusion.

### H-003 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-020 (correction D2) ; TASK-DEV-021 (audit D2) et TASK-DEV-022 (D3, analyse) transférées.

**Travail réalisé :** diagnostic du défaut D2 (perte de la lettre de lecteur d'un chemin Windows absolu, avec mesure de l'impact sur un autre lecteur), correction de `app/orchestration/planner.py` (fidélité de l'extraction : lettre de lecteur, tiret, espaces internes, chemins entre guillemets, marqueur), 21 tests de régression et de confinement, vérification manuelle en CLI, mise à jour du guide utilisateur, analyse D3 complète sans aucune modification de sécurité.

**Fichiers modifiés :** `app/orchestration/planner.py` ; `tests/test_windows_paths.py` (nouveau) ; `docs/reports/PHASE_6_3C_D2_WINDOWS_PATHS_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-windows-paths` (base `3a59dae` = tete de la branche D1), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), `origin/integration/miles-phases-5-6-6-1` (`69bf670`) et `fix/miles-d1-web-authorization` (`3a59dae`) inchangés. Travail effectué dans un worktree isolé : l'artefact non suivi `tatus --short--branch` du checkout principal est préservé.

**Tests exécutés :** 21 tests dédiés (9 échouent sans le correctif, vérifié par `git stash`) ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_mission_web_authorization` 6/6 (non-régression D1) ; `test_web_security_phase6_1` 35/35 ; `test_tool_policy` 11/11 ; `test_web_security` 33/33 ; suite complète **555 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)** ; CLI : chemin absolu → `completed`, chemin avec espaces → `completed`, hors périmètre → `failed` avec le vrai chemin cité. Non exécuté : Debian 13 (environnement indisponible).

**Problèmes restants :** D3 non corrigé (analyse et proposition seulement, §5 du rapport) ; D1-bis et D4 toujours non corrigés ; un chemin dont le dernier segment porte des espaces en minuscules n'est reconnu qu'entre guillemets (limite assumée).

**Prochaine action recommandée :** Agent B prend TASK-DEV-021 (audit du commit D2) et tranche la voie de correction de D3 pour TASK-DEV-022 ; ne pas fusionner avant ces validations.


### H-004 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-023 (correction D1-bis) ; TASK-DEV-024 (audit D1-bis) et TASK-DEV-025 (D3, analyse) transférées.

**Travail réalisé :** reproduction du défaut D1-bis sur le vrai serveur HTTP (200 mensonger), correction de la réponse d'autorisation (validation synchrone via `MissionRunner.check_authorization`, codes HTTP et corps explicites, code de raison non sensible), 20 tests de régression, analyse approfondie de D3 (moteur, typage applicable, matrice de 29 tests, 7 risques de contournement, deux voies proposées) **sans aucune modification du code de sécurité**.

**Fichiers modifiés :** `app/interface/web.py` ; `app/orchestration/runner.py` ; `tests/test_mission_authorize_response.py` (nouveau) ; `docs/reports/PHASE_6_3D_D1BIS_AGENT_A.md` (nouveau) ; `docs/reports/PHASE_6_3E_D3_ANALYSIS_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-d1bis-authorization-response` (base `d3240d2`), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), la branche d'intégration auditée (`69bf670`), la branche D1 (`3a59dae`) et la branche D2 (`d3240d2`) inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé.

**Tests exécutés :** 20 tests dédiés (15 échouent sans le correctif, vérifié par `git stash`) ; `test_mission_web_authorization` 6/6 (non-régression D1) ; `test_web_security_phase6_1` 35/35 ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security` 33/33 ; `test_windows_paths` 21/21 (non-régression D2) ; suite complète **575 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)** ; scénario web réel : 403 (jeton invalide) → 409 ×2 → 200 → mission `completed`. Non exécuté : Debian 13 (environnement indisponible).

**Problèmes restants :** D1-ter (une autorisation peut être silencieusement ignorée pendant que la mission construit son rapport) — réponse rendue honnête (409), cause racine **proposée, non appliquée** ; D3 non corrigé (analyse et proposition seulement) ; le jeton d'approbation reste contournable par le propriétaire via `/mission/<id>/answer` (préexistant, signalé).

**Prochaine action recommandée :** Agent B prend TASK-DEV-024 (audit du commit D1-bis) et tranche la voie de correction de D3 pour TASK-DEV-025 ; ne pas fusionner avant ces validations.


### H-005 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-026 (correction D3) ; TASK-DEV-027 (audit D3) transférée.

**Travail réalisé :** correction du défaut D3 par typage explicite des paramètres de chemin (marqueur `is_path` dans le schéma d'outils, contrôle structurel des valeurs de chemin dans la politique, transmission du typage par le moteur), 40 tests de régression à trois niveaux (politique / validation du chemin / autorisation effective), vérification de 9 garanties de sécurité, reprise et correction de la matrice de 29 cas de l'analyse préalable après vérification du code réel.

**Fichiers modifiés :** `app/tools/policy.py` ; `app/tools/engine.py` ; `app/tools/registry.py` ; `app/tools/builtin.py` ; `tests/test_policy_path_typing.py` (nouveau) ; `docs/reports/PHASE_6_3F_D3_IMPLEMENTATION_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-policy-path-typing` (base `1ef4878` = tete D1-bis), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), la branche d'intégration auditée (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`) et D1-bis (`1ef4878`) inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé, aucune base du développeur n'a été écrite.

**Tests exécutés :** 40 tests D3 (3 échouent sans le correctif, vérifié par revert du seul moteur) ; `test_tool_policy` 11/11 ; `test_tool_engine` 26/26 ; `test_tool_integration` 40/40 ; `test_tool_resources` 8/8 (1 ignoré) ; `test_path_security` 21/21 (3 ignorés) ; `test_web_security_phase6_1` 35/35 ; `test_web_security` 33/33 ; non-régression D1 6/6, D1-bis 20/20, D2 21/21 ; suite complète **615 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (environnement indisponible). Aucun appel API payant.

**Problèmes restants :** audit D3 non effectué (TASK-DEV-027) ; trois points signalés hors périmètre (clés imbriquées non vues par la politique, fragments de code non détectés, D1-ter) ; D1-ter et le contournement du jeton via `/mission/<id>/answer` toujours non corrigés.

**Prochaine action recommandée :** Agent B prend TASK-DEV-027 et audite la branche `fix/miles-policy-path-typing` (caractère borné de l'exemption, choix des caractères bloqués, maintien des garanties G1-G9, Debian 13) ; ne pas fusionner avant cet audit.


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
