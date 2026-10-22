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


### H-007 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-029 (correctifs A-α et B-α) ; TASK-DEV-030 (audit) transférée.

**Travail réalisé :** application des deux correctifs minimaux arbitrés lors de l'investigation Phase 6.3g. A-α : validation synchrone de la demande en attente sur la route `/answer` via une nouvelle méthode `MissionRunner.check_answer` (source de vérité unique, appelée par `answer`), avec des réponses explicites (403 + code de raison) et le 409 conservé comme filet ; le contrat de la route est inchangé (aucun jeton exigé). B-α : l'analyse qualitative IA n'est plus demandée pour une mission en attente, ce qui supprime la fenêtre pendant laquelle une autorisation était silencieusement ignorée. 18 tests de régression (7 échouent sans A-α, 1 sans B-α) et un rapport complet.

**Fichiers modifiés :** `app/orchestration/runner.py` ; `app/interface/web.py` ; `tests/test_answer_d1ter_fixes.py` (nouveau) ; `docs/reports/PHASE_6_3H_ANSWER_D1TER_FIX_AGENT_A.md` (nouveau) ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-answer-d1ter` (base `0be08cd`), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'intégration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`) et D3 (`0be08cd`) inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé, aucune base du développeur n'a été écrite.

**Tests exécutés :** 18 tests de régression (7 échouent sans A-α, 1 sans B-α) ; `test_mission_authorize_response` 20/20 ; `test_mission_web_authorization` 6/6 ; `test_web_security_phase6_1` 35/35 ; `test_web_security` 33/33 ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_windows_paths` 21/21 ; `test_tool_policy` 11/11 ; `test_path_security` 21/21 (3 ignorés) ; `test_tool_engine` 26/26 ; `test_tool_integration` 40/40 ; `test_tool_resources` 8/8 (1 ignoré) ; suite complète **633 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (environnement indisponible). Aucun appel API payant, aucune donnée réelle lue ni écrite.

**Problèmes restants :** l'option **A-β** (exiger le jeton sur `/answer`) n'est pas appliquée — c'est un changement de contrat d'API, à arbitrer ; la fenêtre résiduelle « mission occupée » reste couverte par le 409 ; le compte rendu provisoire d'une mission en attente ne comporte plus d'analyse qualitative (effet de bord assumé) ; le refus d'une approbation cross-session dépend du contrôle de session de D1 : **D1 doit être fusionné avant ce correctif**.

**Prochaine action recommandée :** Agent B prend TASK-DEV-030 (audit de `fix/miles-answer-d1ter`) et tranche A-β ; ne pas fusionner avant cet audit ; à la fusion, respecter l'ordre D1 → D2 → D1-bis → D3 → A-α/B-α et résoudre manuellement le conflit de contexte possible sur le bloc d'imports de `web.py` (constantes `REASON_*`).


### H-008 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-031 (D-B05 + validation D-B01) ; TASK-DEV-032 (audit) transférée.

**Travail réalisé :** vérification de l'état Git réel (la branche d'audit d'Agent B a bougé : `ac627df` → `fd25a26` ; nouveau rapport lu, il ne contredit aucun constat et ne signale aucune régression) ; examen des six défauts D-B01 à D-B06 sur le code de la base de travail ; correction de D-B05 (la liste des missions ignorait la base ; le propriétaire n'était pas persisté, ce qui éteignait la séparation entre utilisateurs au redémarrage) ; reproduction exacte du constat D-B01 de l'audit dans un dépôt placé dans un chemin contenant `code` ; ajout du test de non-régression demandé par l'audit.

**Fichiers modifiés :** `app/orchestration/store.py` ; `app/orchestration/runner.py` ; `tests/test_mission_persistence_owner.py` (nouveau) ; `docs/reports/PHASE_6_3I_MISSION_PERSISTENCE_AGENT_A.md` (nouveau) ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-mission-persistence-owner` (base `25baa60`), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'intégration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`) et A-α/B-α (`25baa60`) inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé, aucune base du développeur n'a été écrite.

**Tests exécutés :** 9 tests dédiés (3 échouent sans le correctif) ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_mission_authorize_response` 20/20 ; `test_mission_web_authorization` 6/6 ; `test_windows_paths` 21/21 ; `test_policy_path_typing` 40/40 ; `test_web_security_phase6_1` 35/35 ; suite complète **642 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (environnement indisponible).

**Problèmes restants :** D-B05 conserve deux points ouverts (`results` non persistés, étape `RUNNING` non reprise) ; D-B02 reste une réserve de conception assumée (non touchée) ; les missions antérieures à la migration n'ont pas de propriétaire connu (choix sûr : non listées dans la vue filtrée, visibles dans la vue non filtrée).

**Prochaine action recommandée :** Agent B prend TASK-DEV-032 (audit de la branche) et décide si les deux points D-B05 restants méritent un lot dédié ; ne pas fusionner sans décision explicite ; l'ordre de fusion D1 → D2 → D1-bis → D3 → A-α/B-α → D-B05 est à respecter.


### H-009 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-033 (persistance des résultats et reprise des missions interrompues) ; TASK-DEV-034 (audit) transférée.

**Travail réalisé :** diagnostic des deux points D-B05 restants (dictionnaire `results` local à la boucle d'exécution ; étape `RUNNING` ni rejouée ni signalée) ; correction sans changement de schéma (les résultats sont reconstruits depuis le plan déjà persisté) ; comportement de reprise explicite à deux catégories (rejeu si l'outil est déclaré sans effet, sinon incertitude et aucune réexécution) ; déclaration `read_only` portée par le schéma d'outils, fausse par défaut ; 12 tests déterministes et un rapport complet.

**Fichiers modifiés :** `app/orchestration/runner.py` ; `app/tools/registry.py` ; `app/tools/builtin.py` ; `tests/test_mission_results_recovery.py` (nouveau) ; `docs/reports/PHASE_6_3J_RESULTS_RECOVERY_AGENT_A.md` (nouveau) ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-results-persistence` (base `79692fe`, référence de lecture non modifiée), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'intégration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`) et A-α/B-α (`25baa60`) inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé, aucune base du développeur n'a été écrite.

**Tests exécutés :** 12 tests dédiés (4 échouent sans le correctif) ; `test_mission_persistence_owner` 9/9 ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_mission_authorize_response` 20/20 ; `test_mission_web_authorization` 6/6 ; `test_web_security_phase6_1` 35/35 ; `test_tool_engine` 26/26 ; `test_tool_integration` 40/40 ; `test_tool_policy` 11/11 ; `test_policy_path_typing` 40/40 ; `test_windows_paths` 21/21 ; `test_path_security` 21/21 (3 ignorés) ; suite complète **654 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (environnement indisponible). Aucun appel API payant, aucune donnée réelle lue ni écrite.

**Problèmes restants :** la déclaration `read_only` est une affirmation de l'application (faux par défaut) ; la reprise d'une étape de lecture relit la donnée ; le budget global peut être atteint par la reprise (comportement voulu) ; un outil à effet interrompu laisse la mission en `partial` avec une étape incertaine.

**Prochaine action recommandée :** Agent B prend TASK-DEV-034 ; à la fusion, D3 touche les mêmes fichiers de schéma d'outils (`app/tools/registry.py`, `app/tools/builtin.py`) que cette branche — hunks différents, à vérifier ; ne pas fusionner sans décision explicite.


### H-012 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-029 (mémoire persistante : état des lieux, tests, correction de D-MEM-01) ; TASK-DEV-030 (audit) transférée.

**Travail réalisé :** état des lieux établi sur le code réel des trois commandes de mémoire (console et web), du stockage SQLite, de la persistance après redémarrage et des liens avec l'historique de conversation et l'identité de l'utilisateur ; écriture des 17 tests couvrant les 7 exigences de la mission ; mise en évidence du défaut D-MEM-01 (les souvenirs n'étaient rattachés à aucun utilisateur : tout utilisateur authentifié voyait et pouvait supprimer les souvenirs des autres) ; correction minimale (colonne `owner_user_id` + migration sans perte, filtrage des trois opérations, propagation de l'identifiant de session ; console inchangée) ; mise à jour du catalogue du guide.

**Fichiers modifiés :** `app/memory/persistent.py` ; `app/interface/web.py` ; `tests/test_memory_persistence.py` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/reports/PHASE_6_4A_MEMORY_PERSISTENCE_AGENT_A.md` (nouveau) ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** branche `fix/miles-memory-persistent` (base `54bd138`), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'intégration (`69bf670`) et les branches D1, D2, D1-bis, D3, A-α/B-α, D-B05 et D-B05-restants inchangés. Travail en worktree isolé : l'artefact non suivi du checkout principal est préservé, aucune base du développeur n'a été écrite.

**Tests exécutés :** 17 tests dédiés (4 en erreur sans le correctif) ; `test_memory_persistent` 18/18 ; `test_web` 14/14 ; `test_cli_reliability` 5/5 ; `test_miles_entrypoint` 5/5 ; `test_settings_memory_config` 15/15 ; `test_defects_agent_b` 26/26 ; suite complète **671 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (VM d'audit injoignable — la validation Debian 13 n'est pas déclarée). Aucun appel API payant, aucune donnée réelle lue ni écrite.

**Problèmes restants :** la base n'est pas chiffrée ; les souvenirs « partagés » (propriétaire vide) sont visibles de tous ; le lien souvenirs / historique de conversation n'existe toujours pas ; le filtre anti-secret repose sur une liste de mots.

**Prochaine action recommandée :** Agent B prend TASK-DEV-030 (audit de la branche) et tranche les deux sujets d'architecture ouverts (lien à l'historique, chiffrement) ; ne pas fusionner sans décision explicite.


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
