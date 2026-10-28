
## H-016 — 2026-10-28 — Agent A bis → utilisateur et Agent B — mission site web : vérification, correctifs, spec

**Travail réalisé :** vérification de l'intégration Miles Companion sur pièces
(`TASK-DEV-060`) — 63 tests ciblés, lecture du serveur et des fichiers servis.
Deux écarts réels trouvés : le bundle `assets/index-DSIZJMQZ.js` initialisait
`SourceMapConsumer` sur `unpkg.com` (capacité d'appel externe contraire à
`DEC-014`), et `index.html` exposait `40 °C · 14 ms`, `Éveillé · 40 °C`,
`miles-local-7b` et « build démo » avant remplacement par le pont. Les deux sont
corrigés : URL retirée du bundle, valeurs remplacées par des marqueurs honnêtes
que `miles-bridge.js` traite (trois branches ajoutées). Spécification de
jumelage et de comptes rédigée (`TASK-DEV-062`) sans aucune ligne de code réseau.

**Fichiers modifiés :** `app/interface/companion/index.html`,
`app/interface/companion/miles-bridge.js`,
`app/interface/companion/assets/index-DSIZJMQZ.js`,
`tests/test_companion_static_assets.py` (nouveau),
`docs/reports/COMPANION_INTEGRATION_VERIFICATION_AGENT_ABIS.md` (nouveau),
`docs/specs/SITE_PAIRING_IA_SPEC.md` (nouveau),
`docs/coordination/{MISSIONS_REGISTRY,TASKS,MESSAGES,DECISIONS,STATUS}.md`.

**Tests exécutés :** `test_companion_static_assets` **7 OK** ;
`test_companion_server` + `test_web_device` + `test_web_project_board`
**63 OK** ; suite complète **995 OK, 5 ignorés** (mesure de session sur
`ec9d62c`). **Non exécuté :** aucun navigateur, aucun boîtier réel, aucune
validation Debian 13.

**Problèmes restants :** le rendu navigateur et le remplacement effectif des
marqueurs n'ont pas été observés ; la spec attend la validation utilisateur ;
`TASK-DEV-063` (jumelage V1) est bloquée par cette validation.

**Prochaine action recommandée :** relire `docs/specs/SITE_PAIRING_IA_SPEC.md`,
trancher les quatre points qui appartiennent à l'utilisateur (hébergement,
position, comptes, ordre V1/V2), puis ouvrir `TASK-DEV-063`.
** `app/orchestration/runner.py` ; `tests/test_mission_web_authorization.py` (nouveau) ; `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

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

### H-010 — 2026-10-21 — Agent A → Agent B
**Tâche :** TASK-DEV-035 (frontières `read_only`, branche de tests), TASK-DEV-036 (correctif minimal) ; TASK-DEV-037 (audit) transférée.
**Travail réalisé :** examen préalable (aucun test équivalent n'existait) ; vérification sur le code des six frontières de confiance réelles (modèle, immuabilité du schéma, origine applicative de la propriété, outil inconnu, propriété absente, propriété invalide) ; 11 tests de frontière **sans aucune modification de production** (branche de tests) ; confirmation d'un **défaut réel** sur la seule frontière non garantie (une valeur non booléenne vraie était traitée comme une déclaration « sans effet », la chaîne `"false"` comprise) et correctif minimal d'une ligne (seule la valeur booléenne `True` vaut déclaration) ; 1 test de régression couvrant 6 valeurs invalides.
**Fichiers modifiés :** branche de tests : `tests/test_read_only_trust_boundaries.py` (nouveau) + `docs/coordination/*`. Branche de correctif : `app/orchestration/runner.py` (+11/−1), `tests/test_read_only_trust_boundaries.py` (+26), `docs/reports/PHASE_6_3K_READ_ONLY_TRUST_BOUNDARIES_AGENT_A.md` (nouveau) + `docs/coordination/*`.
**Commits :** `test/miles-read-only-trust-boundaries` = `155dab3` (base `54bd138`) ; `fix/miles-read-only-prudent-type` (base `155dab3`) — les deux poussées sur `origin`. **Aucune fusion** ; `main`, l'intégration, D1, D2, D1-bis, D3, A-α/B-α, D-B05 et D-B05-restants inchangés. Deux worktrees isolés ; artefact non suivi du checkout principal préservé, aucune base du développeur écrite.
**Tests exécutés :** 11 tests (branche de tests) et 12 tests (branche de correctif) — **6 échouent sans le correctif** ; suites complètes **665 tests OK (4 ignorés)** et **666 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)** ; non-régression orchestrateur (73), bornes (20), D1-bis (20), sécurité web (35), moteur (26), intégration outils (40), registre (6), politique (11), D3 (40), reprise (12), persistance (9). Non exécuté : Debian 13 (environnement indisponible). Aucun appel API payant, aucune donnée réelle lue ni écrite.
**Problèmes restants :** la déclaration `read_only` reste une assertion de l'application (le défaut est « à effet ») ; un outil déclaré sans effet mais qui en a un serait rejoué ; l'énumération stricte (plutôt qu'un booléen) reste une option non appliquée.
**Prochaine action recommandée :** Agent B prend TASK-DEV-037 (audit des deux branches) et tranche l'option de l'énumération stricte ; ne pas fusionner sans décision explicite ; à la fusion, traiter `test/miles-read-only-trust-boundaries` avant `fix/miles-read-only-prudent-type` (cette dernière l'empile).

### H-011 — 2026-10-21 — Agent A → Agent B
**Tâche :** TASK-DEV-038 (Mission P1 : `/answer` n'approuve plus) ; TASK-DEV-039 (audit) transférée.
**Travail réalisé :** suppression du contournement P1-6-06 sur la route `/answer`. L'audit Agent B avait signalé que `runner.answer()` transformait une réponse `o`/`oui`/`y`/`yes`/`ok`/`autorise` en approbation d'autorisation sans jeton d'approbation. `MissionRunner.answer` ne transforme plus une réponse textuelle en approbation ; `MissionRunner.check_answer` est mise à jour ; l'interface CLI intercepte l'exception ; la mission n'est ni approuvée ni arrêtée. 8 tests d'invariant vérifient qu'aucune route alternative ne peut approuver ou exécuter l'action sans autorisation valide. Les tests d'observation sont mis à jour pour refléter le nouveau comportement.
**Fichiers modifiés :** `app/orchestration/runner.py` ; `app/interface/cli.py` ; `tests/test_answer_d1ter_fixes.py` ; `tests/test_answer_authorization_invariant.py` (nouveau) ; `docs/reports/PHASE_6_3L_P1_ANSWER_AUTHORIZATION_AGENT_A.md` (nouveau) ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.
**Commits :** branche `fix/miles-answer-authorization-only` (base `25baa60`), poussée sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'intégration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`) et A-α/B-α (`25baa60`) inchangés. Travail en worktree isolé ; artefact non suivi du checkout principal préservé, aucune base du développeur écrite.
**Tests exécutés :** 8 tests d'invariant (9 échouent sans le correctif) ; `test_answer_d1ter_fixes` 19/19 ; `test_mission_authorize_response` 20/20 ; `test_mission_web_authorization` 6/6 ; `test_web_security_phase6_1` 35/35 ; `test_web_security` 33/33 ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; suite complète **655 tests OK (4 ignorés)** ; **70 tests d'audit Agent B rejoués tels quels : OK (2 ignorés)**. Non exécuté : Debian 13 (environnement indisponible). Aucun appel API payant, aucune donnée réelle lue ni écrite.
**Preuves reproductibles :** `/answer` avec `o`, `oui`, `yes`, `ok`, `autorise` → HTTP 403 `authorization_requires_token` ; mission terminée par `/authorize` avec le jeton valide → 200, `completed` ; aucune étape sensible exécutée sans autorisation valide.
**Problèmes restants :** les tests d'observation (`test_investigation_d1ter_answer_path.py`) sont mis à jour pour refléter le nouveau comportement ; ils ne contournent pas la protection.
**Prochaine action recommandée :** Agent B prend TASK-DEV-039 (audit de la branche) ; ne pas fusionner avant cet audit ; si Agent B demande un changement de contrat (exiger le jeton sur `/answer`), c'est un choix d'API à trancher séparément.


---

## H-013 — Miles Companion intégré au dépôt, télémétrie réelle du poste

**Date :** 2026-10-27
**De :** Agent A
**Vers :** Agent B (revue indépendante, `TASK-DEV-044`)
**Tâche :** `TASK-DEV-044` (revue) ; suite de `TASK-DEV-043` (cockpit).
**Travail réalisé :** l'application « Miles Companion » a été copiée dans le dépôt sous `app/interface/companion/`, détachée de Readdy (ressources locales, routes propres, filigrane et analytics neutralisés), servie sur `127.0.0.1:8787` avec relais des routes de l'agent vers MILES. La page « Boîtier » n'affiche plus aucune valeur fabriquée : `GET /api/device` renvoie des mesures réelles du poste (hôte, cœurs, disque, pid, durée du processus, fournisseur, latence loopback mesurée, mémoire) et déclare `available: false` avec une raison pour les capteurs absents ; le pont remplace les tuiles de démonstration et n'allume l'indicateur d'état que si MILES a réellement répondu. Les images relatives du bundle sont servies depuis `/assets/img` (plus aucun 404 local).
**Fichiers modifiés :** `app/interface/device_telemetry.py` (nouveau), `app/interface/web.py` (route `/api/device`), `app/interface/companion/miles-bridge.js`, `app/interface/companion/projet.html`, `app/interface/companion/assets/index-DSIZJMQZ.js`, `tests/test_web_device.py` (nouveau), `docs/coordination/{DECISIONS,MESSAGES,STATUS,HANDOFF,MEMORY-BUFFY,TASKS}.md`.
**Commits :** `b8cb2c8` sur `integration/miles-post-d1` (fusion `f53b03d`). **Aucun push.**
**Tests exécutés :** `tests/test_web.py` + `tests/test_web_project_board.py` + `tests/test_web_device.py` -> **56 OK**. Essai réel : `POST /api/tasks/TASK-DEV-007/status` (via l'interface) -> `TODO -> IN_PROGRESS`, une seule ligne modifiée, entrée horodatée dans `data/project_board_audit.jsonl`, puis restauration manuelle du document. Vérification navigateur réelle sur `127.0.0.1:8787` : toutes les ressources en 200, aucune requête sortante, mesures stables sur 7 s (aucun flottement entre valeur simulée et mesure). Audit du Lab : `AUDIT-TOUS.py` **vert** (49 fichiers) — portée : espace du Lab, **pas le dépôt MILES**.
**Problèmes restants :** capteurs matériels de la Miles Box non exposés (déclarés indisponibles, jamais inventés) ; deux worktrees temporaires conservés car ils portent des modifications locales ; l'identité « Agent A / Agent B » reste déclarée par l'utilisateur, non authentifiée.
**Prochaine action recommandée :** Agent B relit l'intégration et la télémétrie, et tranche sur la présentation des valeurs non mesurées (annotation explicite aujourd'hui).

## H-014 — 2026-10-27 — Agent A → Agent B — lot « tri, `main`, cockpit unique » et revues en attente

- **De** : Agent A (poste principal, utilisateur `DripMind`).
- **Vers** : Agent B (poste secondaire) — revue indépendante.
- **Référence** : branche **`main`**, avance rapide locale depuis
  `integration/miles-post-d1`. Aucun `push` (DEC-004) : le dépôt distant n'a pas
  reçu ces commits.
- **Décision liée** : `DEC-015`. **Message lié** : `M-019`.

### Travail réalisé (Agent A)

1. **Tri prouvé** : FontAwesome (1,05 Mo) supprimé après vérification qu'aucune
   classe `fa-*` n'existe dans le HTML, le CSS ou le JS ; 12 `.gitkeep`
   redondants retirés ; page Projet dupliquée retirée ; `ORGANISATION.md` écrit.
2. **Cockpit unique** : le serveur Companion sert `assets/web/` sous
   `/cockpit/` ; `/projet` redirige ; bandeau de santé visible avant connexion ;
   icônes locales ; surface HTTP bornée par liste blanche.
3. **Worktrees** : rapport unique récupéré dans la référence, 433 lignes de
   travail multi-fournisseurs commitées sur sa branche, puis les deux dossiers
   `%TEMP%` retirés. Les branches sont conservées.
4. **Tests** : 876 exécutés (874 OK, 2 échecs antérieurs au lot, 5 ignorés) ;
   18 tests nouveaux pour le serveur Companion ; suite web complète 74 OK.

### Ce que j'attends d'Agent B

- `TASK-DEV-046` — revue du tri et du cockpit (points 1 à 7 de `M-019`).
- `TASK-DEV-044` — revue du Companion et de la télémétrie réelle.
- `TASK-DEV-019`, `021`, `024`, `027`, `030`, `032`, `034`, `037`, `039`,
  `041` — les dix audits de la Phase 6.3, **toujours en attente** et **non
  approuvés** faute de revue.

### Résultat attendu

Un rapport par revue (`docs/reports/`), l'état des tâches mis à jour dans
`TASKS.md` (`DONE` uniquement si la revue est concluante, sinon `BLOCKED` avec
la raison), et une réponse dans `MESSAGES.md` : ce qui est vérifié, ce qui ne
l'est pas, les désaccords.

### Interdits rappelés

Aucun `push`, aucune fusion dans `main` par Agent B sans accord explicite de
l'utilisateur ; aucune réécriture des rapports datés ; ne pas modifier les
fichiers de production pendant une revue (lecture seule) ; ne pas toucher aux
deux PC hors du dépôt.

## H-015 — 2026-10-28 — Agent A → Agent B — lot boîtier fusionné dans `main`

**Tâche :** `TASK-DEV-047` (fermeture), `TASK-DEV-050`, `TASK-DEV-051` — DONE. Audits `M-024` (Agent B) et `M-025` (Agent A) clos.

**Travail réalisé :** fermeture des deux réserves P3 de l'audit B et d'un défaut adjacent trouvé en les corrigeant : la comparaison de la clé partagée du backend boîtier passe à temps constant (`hmac.compare_digest` sur des **octets** — sur des `str`, la fonction refuse les caractères non ASCII) ; un corps JSON qui n'est pas un objet (`[]`, `null`, `"chaine"`) levait `AttributeError` et produisait une **500 au lieu d'un 401** ; il est désormais refusé sans exception. La convention « tout fichier personnel porte le suffixe `.local` » remplace l'heuristique sur le contenu, écrite à trois endroits où elle sert (en-tête de `scripts/build_release.py`, doc du firmware, test). Comptes de tests revérifiés par comptage des `def test_` : `TestWebServerLocalOnly` = **14** (et non 5 ajoutés), `tests/test_web_lan.py` = **10** (ni les 8 du rapport d'audit, ni les 11 de nos documents).

**Fichiers modifiés :** `hardware/packages/backend-box/boxtelemetry.py`, `tests/test_boxtelemetry.py`, `scripts/build_release.py`, `hardware/packages/esp32-s3/README.md`, `docs/coordination/{TASKS,STATUS,MESSAGES,DECISIONS}.md`.

**Commits :** `209e39f` sur `feat/miles-box-packages`, puis **fusion `--no-ff` dans `main`** = `dcc3130`, poussée sur `origin/main` (exécutée par l'utilisateur sur son poste, l'agent n'ayant plus de shell). Branche conservée.

**Tests exécutés :** contrôles ciblés **25 OK** (`test_boxtelemetry` **9**, `test_web_lan` **10**, `test_build_release` **6**) ; suite complète **936 tests, 0 échec, 5 ignorés** sur la fusion ; `bash -n hardware/packages/pc-miles/install.sh` sans sortie. **Non exécuté :** installation sur Debian 13, flash du firmware sur le boîtier.

**Problèmes restants :** le firmware est compilé (`[SUCCESS]`, 1 103 072 octets) mais **jamais flashé** ; aucune installation n'a tourné sur le M75q ; la clé Gemini du multi-fournisseurs transite en paramètre d'URL (comportement de l'API, non journalisé) et reste à trancher par audit B.

**Prochaine action recommandée :** rebaser `feature/miles-multi-provider` (`b0ba016`) sur `main` et la repasser aux tests, puis exécuter la procédure Debian 13 sur le mini-PC — c'est la dernière preuve manquante pour « installable ».

