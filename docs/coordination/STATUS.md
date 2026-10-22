# docs/coordination/STATUS.md — État du projet MILES

## État général (2026-10-19)

- **Projet** : MILES — dépôt GitHub privé `https://github.com/Miles-corp/Milescorp.git`
- **Branche** : `main` (à jour avec `origin/main`, working tree propre)
- **Contenu actuel** : `.gitattributes` (initial), documents de coordination (Mission 001, commit c71d3af), prototype DEV-001 (commit 416dc2e), correction Agent B (commit 153bb16), fiabilisation Agent B (commit e156a24), audit Agent A (commit a63609f), MILESTONE-005 (commit 5c63332), MILESTONE-006 (commit fe5a017), Phase 2 fournisseur distant + web + .env (commit 0ad3a41). Code fonctionnel : interface terminal, fournisseurs IA hybride distant connecté, contexte conversationnel, actions locales, tests, configuration, utilitaire GPU, mémoire persistante SQLite, interface web http.server.
- **Mission en cours** : Mission 001 — terminée. Prototype DEV-001 — créé et publié (Agent A). Fiabilisation TASK-DEV-004 — terminée (Agent B, 38 tests OK). Audit final TASK-DEV-003 — terminé (Agent A, rapport AUDIT-TASK-DEV-003). MILESTONE-005 — terminé (Agent A, commit 5c63332). MILESTONE-006 — terminé (Agent A, commit fe5a017). Phase 2 — fournisseur distant connecté, interface web http.server, chargement .env, tests simulés (terminé, commit 0ad3a41, 95 tests OK sur Windows). Phase 3B validation fonctionnelle — terminée (Agent B, commit de ce rapport).

## Prochain objectif

- Poursuivre TASK-002 à TASK-004 (revue indépendante de l'organisation par Agent B).
- Proposition technique fournisseur local hors ligne (TASK-DEV-007) : moteur et modèle adaptés à RTX 3050 4 Go, sans Ollama, sans téléchargement sans accord (Agent A).
- Tests réels sur le fournisseur distant (uniquement après accord utilisateur pour coût API).
- Validation sur Debian 13 des tests Phase 3B (test_env_loading, test_web, test_provider_selection) : à faire sur la VM.

## Tâches actives

| ID | Titre | Statut | Assigné à |
|----|-------|--------|-----------|
| TASK-001 | Mise en place de la structure de coordination | DONE | Agent A |
| TASK-002 | Revue indépendante de l'organisation | TODO | Agent B |
| TASK-003 | Vérification des consignes et tests documentés | TODO | Agent B |
| TASK-004 | Détection des oublis et des ambiguïtés | TODO | Agent B |
| TASK-DEV-001 | Premier prototype fonctionnel MILES | DONE | Agent A |
| TASK-DEV-002 | Revue indépendante des tests et vérification | TODO | Agent B |
| TASK-DEV-003 | Consolidation du prototype et validation sur Debian 13 | DONE | Agent B |
| TASK-DEV-004 | Fiabilisation du prototype (Mission 004B) | DONE | Agent B |
| TASK-DEV-005 | MILESTONE-005 : Assistant personnel hybride distant/local | DONE | Agent A |
| TASK-DEV-006 | MILESTONE-006 : Mémoire persistante locale | DONE | Agent A |
| TASK-DEV-007 | MILESTONE-007 : Fournisseur local hors ligne (RTX 3050) | TODO | Agent A |
| TASK-DEV-009 | MILES V1 : Persistance de conversation + fournisseur distant connecté | DONE | Agent A |
| TASK-DEV-010 | Corrections des défauts D-B1 à D-B5 (audit Agent B) | DONE | Agent A |
| TASK-DEV-011 | Documentation R3 (INSTALL.md) et erreurs fournisseur R6 | DONE | Agent A |
| TASK-DEV-012 | Correctif D-C1 (detection symlink) et documentation D-C2 | DONE | Agent A |
| TASK-DEV-008 | Phase 4 : Moteur d'outils sécurisé | DONE | Agent A |
| TASK-DEV-008 | Phase 3B : validation fonctionnelle (terminal, web, mémoire) | DONE | Agent B |
| TASK-DEV-013 | Phase 5 : intégration du moteur d'outils dans le CLI et l'interface web | DONE | Agent A |

## Phase 6.3b — Correction D1 : autorisation des missions web (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md`
- **Branche** : `fix/miles-d1-web-authorization` (base `fc179ca`, commit de correction `6b736d7`, pousse sur `origin`). **Aucune fusion.** `main` (`b9b7e7d`) et `origin/integration/miles-phases-5-6-6-1` (`69bf670`) sont inchanges.
- **Defaut corrige (D1)** : `app/orchestration/runner.py::_ensure_authorization` interrogeait le registre d'autorisations avec la **session du runner** (session de l'application) alors que le grant est emis pour la **session du client proprietaire** de la mission (`mission.session_id`). Les deux coincident en CLI, mais pas en web : le grant web legitime etait refuse, la mission soulevait une nouvelle demande d'autorisation en boucle jusqu'a l'epuisement du budget d'echanges.
- **Correctif** : une seule ligne — `mission.session_id or self.session_id`. Coherent avec l'emission du grant et avec l'executeur (`app/orchestration/executor.py:221`, `actor_id=mission.session_id or self._session_id`). Aucun autre defaut touche (D2, D3, D4 et le code de securite sont hors perimetre).
- **Tests ajoutes** : `tests/test_mission_web_authorization.py` (6 tests) — regression D1, mission web autorisee qui se termine, mission web sans autorisation valide qui ne continue pas (0 etape, 0 grant), autorisation non reutilisable depuis une autre session, mission d'un autre utilisateur refusee, invariant du runner. Le test de regression **echoue sans le correctif** (verifie explicitement).
- **Controles executes** : 6/6 tests de regression ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security_phase6_1` 35/35 ; suite complete **534 tests OK (4 ignores, plateforme Windows)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; **scenario web reel** (vrai serveur `miles.py --web`) : mission `completed`, 5 etapes, 5 appels d'outils, **1 echange** (avant : boucle jusqu'a `interaction_budget_exceeded`). Bases de test isolees et supprimees.
- **Defaut connexe signale, non corrige (D1-bis)** : `POST /mission/<id>/authorize` renvoie `{"approved": true}` meme avec un jeton d'approbation invalide (validation faite dans le fil d'execution, exception journalisee et non retournee). **Aucune elevation de privilege** : l'autorisation n'est pas accordee, aucun grant n'est emis, la mission ne continue pas. Correctif separe propose (validation synchrone du jeton dans `WebApp.authorize_mission`).
- **Limites** : aucune validation Debian 13 (environnement indisponible) ; les tests ignores sont des limites de plateforme Windows.
- **En attente** : audit independant par Agent B (TASK-DEV-019) avant toute fusion.

## Phase 6.3c — Correction D2 (chemins Windows) et analyse D3 (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3C_D2_WINDOWS_PATHS_AGENT_A.md`
- **Branche** : `fix/miles-windows-paths` (base `3a59dae` = tete de `fix/miles-d1-web-authorization`, qui porte le correctif D1). **Aucune fusion.** `main` (`b9b7e7d`), `origin/integration/miles-phases-5-6-6-1` (`69bf670`) et `fix/miles-d1-web-authorization` (`3a59dae`) sont inchanges. Travail effectue dans un **worktree isole** (`C:\Users\StanC\AppData\Local\Temp\miles-d2`) : le checkout principal et son artefact non suivi (`tatus --short--branch`) n'ont pas ete touches.
- **Defaut corrige (D2)** : `app/orchestration/planner.py::extract_target_path` perdait la lettre de lecteur d'un chemin Windows absolu (`C:/Windows` -> `/Windows`). Un chemin sans lettre de lecteur n'est plus absolu : il est resolu comme racine du lecteur **courant**. Mesure : `D:\donnees\rapports` etait servi par `C:\donnees\rapports` (autre repertoire, parfois dans le perimetre) ; le refus de perimetre citait `/Windows/System32` au lieu de `C:/Windows/System32`.
- **Correctif** : `app/orchestration/planner.py` uniquement — conservation de la lettre de lecteur, restauration du tiret dans les segments, espaces internes (mot contenant un separateur, ou mot capitalise sur un chemin Windows absolu), chemins entre guillemets, prefixe de marqueur ignore, `C:` seul non retenu. **Aucune modification de la politique de securite ni du perimetre** : le confinement (`app/security/paths.py`) reste le seul juge.
- **Tests** : `tests/test_windows_paths.py` (21 tests) — chemins absolus Windows, chemins avec espaces, chemins relatifs, chemins POSIX, non-regression, et confinement (hors perimetre, traversee, entrees malformedes, racines inchangees) ; **9 tests echouent sans le correctif** (verifie par `git stash`). Suite complete **555 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; verification manuelle CLI (chemin absolu -> `completed`, chemin avec espaces -> `completed`, hors perimetre -> `failed` avec le vrai chemin dans le message).
- **D3 — analyse seule, aucune modification** : `app/tools/policy.py` applique un controle par sous-chaine aux VALEURS ; les faux positifs sont confirmes (`source`, `code`, `script`, `python`, `javascript`) **et la meme famille existe dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`)**. Strategie proposee : conserver le controle exact sur les CLES, appliquer au parametre de type chemin un controle structurel (metacaracteres) au lieu du controle par sous-chaine, inchange pour toute valeur non chemin, et sur les trois validateurs. Deux voies : **2-a typage explicite du parametre chemin (recommandee)** ou 2-b heuristique (deconseillee). Cas qui doivent rester bloques et cas qui doivent etre acceptes lists dans le rapport.
- **Limites** : un chemin dont le dernier segment porte des espaces en minuscules n'est reconnu qu'entre guillemets ; aucun test Debian 13 (environnement indisponible) ; D1-bis et D4 toujours non corriges.
- **En attente** : audit independant par Agent B (TASK-DEV-021) et decision sur la voie de correction de D3 (TASK-DEV-022).

## Phase 6.3d / 6.3e — Correction D1-bis et analyse D3 (Agent A, 2026-10-21)

- **Rapports** : `docs/reports/PHASE_6_3D_D1BIS_AGENT_A.md` (D1-bis) et `docs/reports/PHASE_6_3E_D3_ANALYSIS_AGENT_A.md` (D3, analyse seule).
- **Branche** : `fix/miles-d1bis-authorization-response` (base `d3240d2` = tete de `fix/miles-windows-paths`, qui porte D1 et D2). **Aucune fusion.** `main` (`b9b7e7d`), `origin/integration/miles-phases-5-6-6-1` (`69bf670`), `fix/miles-d1-web-authorization` (`3a59dae`) et `fix/miles-windows-paths` (`d3240d2`) sont inchanges. Travail en **worktree isole** (`Temp\miles-d1bis`).
- **D1-bis corrige** : `POST /mission/<id>/authorize` repondait **200 `{"approved": true}`** meme avec un jeton invalide : la validation du jeton avait lieu dans le FIL d'execution, dont l'exception (`MissionAuthorizationError`) etait journalisee et absorbee, et le `try/except` place autour du *demarrage* du fil ne pouvait rien intercepter. Le defaut est **pre-existant** (branches D1 et D2), la propriete de securite n'etait pas violee (0 grant, 0 etape sensible executee).
- **Correctif** : validation **synchrone** du jeton, de l'expiration et de la session via la nouvelle methode `MissionRunner.check_authorization` (source de truth unique, `authorize()` l'appelle) ; `MissionAuthorizationError` porte un code de raison stable et non sensible ; reponses explicites : **403** (jeton invalide / expire / absent, autre session, autre utilisateur, mission terminee ou inconnue) avec `reason`, **409** (`mission_busy`) si l'action n'a pas ete appliquee. Fichiers modifies : `app/interface/web.py`, `app/orchestration/runner.py`.
- **Variante trouvee (D1-ter, signalee, cause racine NON corrigee)** : une autorisation recue pendant que la mission termine son rapport (appel au fournisseur IA) etait **silencieusement ignoree** (`_start_mission_thread` ignore l'action si un fil est actif), et la reponse annoncait un succes. La reponse est desormais honnete (409) ; la correction racine (ne pas interroger le fournisseur pour une mission en attente) est **proposee** dans le rapport D1-bis §6.1.
- **Tests** : `tests/test_mission_authorize_response.py` (20 tests) — autorisation valide, jeton invalide, jeton expire, autre session, autre utilisateur, mission terminee, mission inconnue, jeton d'une autre mission, jeton absent, non-divulgation du jeton/de la session, mission en cours (409) ; aux niveaux appel direct et **HTTP reel**. **15 tests echouent sans le correctif** (verifie par `git stash`). Suite complete **575 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** (dont le test qui inspecte le code source de `authorize_mission`) ; scenario web reel : 403 (jeton invalide) -> 409 x2 -> 200 -> mission `completed`.
- **D3 — analyse seule, AUCUNE modification de securite** : le controle par sous-chaine applique aux VALEURS dans `app/tools/policy.py` refuse les chemins legitimes (`source`, `code`, `script`, `python`, `javascript`) **et la meme famille existe dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`)**. Faits etablis : l'application ne declare que **2 parametres de type chemin** (`action_list_files.path`, `action_read_file.path`) et le moteur dispose deja de la definition d'outil au point ou la politique est appliquee → le **typage explicite est trivialement applicable** ; les tests existants n'echouent pas le comportement fautif (seulement des cas de cles) → le correctif est possible sans changer les attentes. Deux voies proposees (2-a : la politique ignore les valeurs de chemin ; 2-b : filtrage avant la politique, `policy.py` non modifie — **recommandee**) ; matrice de 29 tests (18 doivent rester refuses, 11 doivent etre acceptes) ; 7 risques de contournement analyses. Aucune ecriture dans `app/tools/policy.py`.
- **Limites** : aucune validation Debian 13 ; D3 non corrige (decision d'Agent B requise) ; D1-ter cause racine non corrigee ; le jeton d'approbation reste contournable par le proprietaire via `/mission/<id>/answer` (comportement preexistant, signale).
- **En attente** : audit independant par Agent B (TASK-DEV-024) et decision D3 (TASK-DEV-025).

## Phase 6.3f — Correction D3 : typage explicite des paramètres de chemin (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3F_D3_IMPLEMENTATION_AGENT_A.md`
- **Base retenue** : `1ef4878` (`fix/miles-d1bis-authorization-response`) — la tete la plus recente (D1 + D2 + D1-bis). `main` (`b9b7e7d`) ecartee : elle ne contient pas `app/tools/builtin.py`. Branche d'integration `69bf670` ecartee (anterieure aux correctifs en vol). **Aucune fusion.**
- **Branche** : `fix/miles-policy-path-typing`, poussee sur `origin`. Travail en **worktree isole** (`Temp\miles-d3`) ; le checkout principal, son artefact non suivi et les bases du developeur n'ont pas ete touches.
- **Defaut corrige (D3)** : la politique appliquait un controle par sous-chaine aux VALEURS, y compris aux chemins : `C:\dev\source`, `Documents\code`, `C:\Python39\Lib` etaient refuses, et toute mission sur un tel repertoire etait impossible. Meme famille dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`).
- **Correctif** : 4 fichiers — `app/tools/registry.py` (`ToolParameter.is_path`), `app/tools/builtin.py` (2 marqueurs), `app/tools/policy.py` (controle **structurel** des valeurs de chemin + factorisation des trois validateurs), `app/tools/engine.py` (transmission du typage declare). **`app/security/paths.py` n'est PAS modifie** ; le planificateur n'est pas modifie (son controle porte sur des motifs de commandes, sans faux positif). L'exemption exige **simultanement** un parametre **declare** chemin **et** une chaine directe ; elle ne s'applique ni aux valeurs libres, ni aux structures imbriquees, ni aux parametres non declares.
- **Garanties verifiees (9)** : G1 cles interdites toujours interdites ; G2 valeurs libres toujours controlees ; G3 chemins valides structurellement ; G4 exemption bornee ; G5 confinement inchange (un chemin accepte par la politique est refuse par `resolve_authorized_path` hors racines) ; G6 traversees refusees ; G7 lectures inchangees (fichiers sensibles refusés) ; G8 aucun outil, permission ni racine nouveau ; G9 les trois niveaux (politique / validation du chemin / autorisation effective) sont distincts et testes separement.
- **Tests** : `tests/test_policy_path_typing.py` (40 tests, 3 niveaux) — **3 echouent sans le correctif** (revert de `app/tools/engine.py` : le defect D3 reapparait au niveau outil) ; suite complete **615 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; `test_tool_policy` 11/11, `test_tool_engine` 26/26, `test_tool_integration` 40/40, `test_path_security` 21/21 (3 ignores), `test_web_security_phase6_1` 35/35, `test_web_security` 33/33, non-regression D1 (6), D1-bis (20), D2 (21).
- **Matrice de 29 cas de l'analyse D3 verifiee contre le code reel** : deux attentes etaient erronees (la politique detecte des MOTS, pas des motifs de code ; les cles imbriquees ne sont pas vues par la politique) — corrigees dans la suite et signalees.
- **Points signales, non corriges (hors perimetre)** : (1) `_iter_keys` ne descend pas dans les valeurs : une cle interdite imbriquee n'est pas vue par la politique (fermee par le schema) ; (2) la politique ne detecte pas les fragments de code sans mot interdit (« import os ») ; (3) D1-ter et le contournement du jeton via `/mission/<id>/answer` (rapport D1-bis).
- **Limites** : aucune validation Debian 13 ; aucun appel API payant ; aucun acces a un fournisseur distant ; seule une directory temporaire de test est creee puis supprimee.
- **En attente** : audit independant par Agent B (TASK-DEV-027). L'audit D3 n'est **pas** considere comme approuve.

## Phase 6.3h — Correctifs A-alpha et B-alpha (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3H_ANSWER_D1TER_FIX_AGENT_A.md`
- **Base** : `0be08cd` (`fix/miles-policy-path-typing`, qui porte D1 + D2 + D1-bis + D3). Branche : `fix/miles-answer-d1ter`, poussee sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`) et D3 (`0be08cd`) sont inchanges. Travail en **worktree isole** (`Temp\miles-answer`).
- **A-alpha** : `POST /mission/<id>/answer` repondait 200 `{"answered": true}` meme lorsque la reponse etait **refusee dans le fil** (session differente, budget epuise, demande expiree) : l exception etait absorbee par le fil. Nouvelle methode `MissionRunner.check_answer` (modele D1-bis, source de verite unique, appellee par `answer`) ; l interface web valide **de facon synchrone** avant de lancer le fil et renvoie 403 + `reason` (mission inconnue, mission terminee, aucune demande en attente, autre session, autre utilisateur, demande expiree, budget epuise) ; 409 conserve pour le cas « mission occupee ». **Le contrat de la route est inchange : aucun jeton n est exige (A-beta NON applique).**
- **B-alpha** : l analyse qualitative IA n est plus demandee pour une mission **en attente** (une seule ligne dans `_execute_loop`) : le fil se termine des la demande d autorisation, la fenetre pendant laquelle une autorisation etait ignoree **disparait**. Effet de bord assume : le compte rendu **provisoire** d une mission en attente ne comporte plus la section « Analyse qualitative » ; le compte rendu **definitif** la conserve (verifie par test). Le 409 reste comme filet.
- **Tests** : `tests/test_answer_d1ter_fixes.py` (18 tests de regression, non destructifs : outils simules, fournisseur simule, aucun appel reseau, aucune donnee reelle). **7 tests echouent sans A-alpha** (revert de `app/interface/web.py`) et **1 sans B-alpha** (neutralisation ciblee) : la reintroduction des defauts est donc detectee. Suite complete **633 tests OK (4 ignores)** ; **70 tests d audit Agent B rejoues tels quels : OK (2 ignores)** ; non-regression D1 (6), D1-bis (20), D2 (21), securite web (35 + 33), orchestrateur (73), bornes (20), politique (11), confinement (21, 3 ignores), moteur (26), integration outils (40).
- **Perimetre respecte** : ni la politique de securite, ni les permissions, ni le confinement des chemins (`app/security/paths.py` intact), ni le planificateur, ni les outils. Aucun appel API payant, aucune donnee reelle lue ni ecrite.
- **Interactions avec les audits en cours** : D1 doit etre fusionne **avant** ce correctif (le refus cross-session repose sur son controle de session) ; D1-bis touche les **memes fichiers** (`runner.py`, `web.py`) mais dans des hunks distincts, avec un **conflit de contexte possible sur le bloc d imports** des constantes `REASON_*` (a resoudre manuellement, sans risque semantique) ; D2 et D3 n ont aucun fichier commun.
- **En attente** : audit independant d Agent B (TASK-DEV-030) et decision sur l option **A-beta** (exiger le jeton sur `/answer` : changement de contrat d API, non applique).

## Phase 6.3l — Mission P1 : `/answer` n'approuve plus (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3L_P1_ANSWER_AUTHORIZATION_AGENT_A.md`
- **Base** : `25baa60` (`fix/miles-answer-d1ter` : D1 + D2 + D1-bis + D3 + A-alpha/B-alpha). Branche : `fix/miles-answer-authorization-only`. **Aucune fusion.** `main` (`b9b7e7d`), l'integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`), A-alpha/B-alpha (`25baa60`) sont inchanges. Travail en **worktree isole** (`Temp\miles-answeronly`) ; artefact non suivi et bases du developeur preserves.
- **Correction (P1)** : `MissionRunner.answer` ne transforme **plus** une reponse textuelle (`o`, `oui`, etc.) en approbation d'autorisation : une demande d'autorisation leve `MissionAuthorizationError` (`authorization_requires_token`), et l'approbation exige `/authorize` et un jeton valide (usage unique, expiration, session, proprietaire). `MissionRunner.check_answer` est mise a jour (elle ne valide plus `check_authorization`) ; l'interface CLI intercepte l'exception. La mission n'est **ni approuvee ni tuee** : elle reste en attente.
- **Tests** : `tests/test_answer_authorization_invariant.py` (8 tests d'invariant) : aucun mot d'approbation par `/answer` n'approuve, l'API interne n'approuve pas, `/authorize` sans jeton valide n'approuve pas, le jeton d'une autre mission / d'une autre session / d'un autre utilisateur est refuse, avec un jeton valide l'action est approuvee puis executee (grant unique lie a la session et a la mission), le jeton ne sert qu'une fois. **9 tests echouent sans le correctif** ; 655 tests OK (4 ignores) ; 70 tests d'audit Agent B OK (2 ignores). Verification HTTP reelle : 403 sur tous les mots d'approbation, mission terminee par `/authorize` avec le jeton.
- **Limite** : les tests d'observation (`test_investigation_d1ter_answer_path.py`) sont mis a jour pour refléter le nouveau comportement ; ils ne contournent pas la protection.
- **En attente** : audit independant d'Agent B (TASK-DEV-039). Les audits en cours ne sont pas consideres comme approuves. Aucune fusion.

## Blocages

Aucun blocage à ce jour.

## Phase 5 — Intégration du moteur d'outils (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_5_TOOL_ENGINE_INTEGRATION_AGENT_A.md`
- **Branche** : `feature/miles-tool-engine-integration` (base `bccdc1c` = branche V1). Aucun merge sur `main`.
- **Constat initial** : le moteur d'outils de la Phase 4 existait mais n'était branché nulle part (registre vide en production, `propose_action()` jamais appelé, aucune route web).
- **Livré** : `ToolService` commun (CLI + web, zéro doublon), 4 outils enregistrés réellement implémentés (`status_read`, `action_datetime`, `action_workdir`, `action_list_files`), CLI `/tools` et `/tool`, web `GET /tools` et `POST /tool` + panneau HTML, confirmation humaine explicite pour les actions MEDIUM.
- **Tests** : 40 nouveaux tests (`tests/test_tool_integration.py`), **378 tests OK** sur Windows (0 échec, 4 ignorés — limites plateforme connues).
- **À faire par Agent B** : validation sur Debian 13 (4 tests ignorés + symlink), revue indépendante du câblage de la confirmation.
- **Point de vigilance** : le jeton de confirmation est lié à l'outil et aux paramètres mais **pas à une identité utilisateur** ; à traiter avant toute exposition des outils au modèle. **Corrigé en Phase 6** (voir ci-dessous).

## Phase 6 — Orchestrateur de missions (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_A.md`
- **Branche** : `feature/miles-mission-orchestrator` (base `a11ab4a` = Phase 5, elle-même based on `bccdc1c`). Aucun merge sur `main`.
- **Constat initial** : le moteur d'outils était utilisable mais il n'existait aucune capacité d'orchestration ; le jeton de confirmation n'était lié ni à l'utilisateur ni à un contexte (défaut signalé par le rapport de la Phase 5).
- **Livré** :
  - `app/orchestration/` — mission, plan, planificateur (déterministe + IA validé), exécuteur, observateur, `MissionRunner`, persistance SQLite (`data/missions.db`), compte rendu structuré ;
  - **correctif de sécurité** : `app/tools/grants.py` — autorisations liées à la session **et** à la mission, expirantes, bornées en usages, révocables ; les jetons de confirmation du moteur sont désormais liés au contexte et à la session ;
  - extension lecture encadrée : `action_read_file` (MEDIUM, permission existante `lecture_systeme`, fichiers sensibles refusés, lecture bornée, contenu expurgé) et listing borné en profondeur ;
  - CLI : `/mission`, `/missions`, `/mission-status`, `/mission-answer`, `/mission-cancel`, `/mission-resume` ;
  - web : `POST /mission`, `GET /missions`, `GET /mission/<id>`, `POST /mission/<id>/authorize`, `POST /mission/<id>/answer`, `POST /mission/<id>/cancel` (exécution en fil séparé, anti-double-exécution).
- **Tests** : 73 nouveaux tests (`tests/test_mission_orchestrator.py`), **451 tests OK** sur Windows (0 échec, 4 ignorés — limites plateforme connues).
- **À faire par Agent B** : validation sur Debian 13, revue indépendante de la chaîne d'autorisation (grant → moteur → outil) et de la reprise de mission.
- **Point de vigilance** : l'identité de session est un jeton aléatoire par exécution de l'application, **pas** une identité humaine authentifiée ; le serveur web est local et sans authentification. À traiter avant toute exposition à un utilisateur distant.

## Phase 6.1 — Correction des P1 de sécurité web (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_6_1_WEB_SECURITY_FIX_AGENT_A.md`
- **Branche** : `fix/miles-web-authorization-security` (base `0754032` = Phase 6 auditee par Agent B). Aucun merge sur `main`.
- **Défauts corrigés** :
  - **P1-6-03** — protection des routes modifiantes : contrôle d'origine (403), type de contenu JSON (415), session authentifiée (401), jeton CSRF lié à la session (403) ; refus **avant** toute lecture de corps et tout effet de bord.
  - **P1-6-06** — autorisation de mission : propriétaire authentifié + jeton d'approbation lié à la demande (imprévisible, expirant, à usage unique) ; un jeton n'est jamais déduit d'un identifiant de mission.
  - **P1-6-02 résiduel** — session **par client** (le jeton de confirmation d'un client n'est pas rejouable par un autre).
  - **P2-6-04** — contexte multiprocessing explicite (`forkserver`/`spawn`).
  - **P3-6-11** — table `mission_events` alimentée. **P3-6-12** — `python miles.py --web` lance l'interface web et affiche le jeton d'accès.
- **Modèle d'authentification** : jeton porteur explicite (`MILES_WEB_AUTH_TOKEN` ou `MILES_WEB_USERS_FILE`), session par client (256 bits, 30 min), jeton CSRF distinct par session, comparaison en temps constant, blocage après 5 échecs. **Sans identifiant configuré, l'interface web est fermée.**
- **Tests** : 35 nouveaux tests de sécurité + 2 de non-régression ; **488 tests OK** sur Windows (0 échec, 4 ignorés). Les 47 tests d'audit d'Agent B ont été exécutés tels quels : **5 « unexpected success »** (les P1 sont corrigés), 4 échecs d'adaptation documentés (routes désormais authentifiées), 1 expectedFailure inchangé.
- **Défaut préexistant découvert et corrigé** : tout résultat d'outil > 8 Kio expiraient à tort (tampon de tube) — le moteur consomme désormais la file pendant l'exécution de l'enfant. Mission d'analyse : 21 s → 1,3 s.
- **À faire par Agent B** : adapter les 4 tests d'audit concernés, valider sur Debian 13 (contexte `forkserver`), re-auditer la chaîne d'autorisation.
- **Point de vigilance** : le jeton porteur n'est pas un mot de passe ; pas de rotation ni de 2FA ; le serveur reste local. P2-6-07/P2-6-08 (bornes par mission et non par boucle) restent à traiter dans une branche dédiée.

## Décisions récentes

- DEC-001 à DEC-004 acceptées (voir `docs/coordination/DECISIONS.md`).
- DEC-005 : Architecture hybride distant/local avec sélection explicite (ACCEPTEE, Agent A).
- DEC-006 : Mémoire persistante locale SQLite (ACCEPTEE, Agent A).
- DEC-007 : Interface web http.server sur 127.0.0.1, zéro dépendance supplémentaire (ACCEPTEE, Agent A).
- DEC-008 : Couche métier unique `ToolService` partagée par le CLI et l'interface web pour le moteur d'outils (ACCEPTEE, Agent A).
- DEC-009 : Autorisations liées à la session et à la mission, confirmations contextuelles, mission pilote strictement en lecture seule (ACCEPTEE, Agent A).

## Audit final Agent A (MISSION 004A)

- Rapport : `docs/reports/AUDIT-TASK-DEV-003.md`
- Résultat : TASK-DEV-003 marqué DONE par Agent B avec réserves (tests exécutés sur Windows Python 3.14.7, pas sur Debian 13).
- Critères PASS : tests unitaires (18/18 sur Windows), démarrage `miles.py --help` (code 0), absence de secrets, cohérence des documents, pas de basculement silencieux, pas d'accès shell arbitraire, configuration invalide gérée, dégradation gracieuse voix.
- Critères FAIL : documentation d'installation manquante (résolu par Agent B : `docs/installation/INSTALL.md` créé dans TASK-DEV-004).
- Critères BLOCKED : validation spécifique sur Debian 13 (environnement non disponible sur le poste Windows d'Agent B et de Agent A).
- Recommandation : valider sur Debian 13 avant de considérer le jalon pleinement atteint.

## Notes

- Les deux PC possèdent leur propre clone local du dépôt.
- La communication est asynchrone via GitHub ; aucun mécanisme direct entre les instances OpenCode n'est installé.
- Avant de commencer une tâche, consulter les messages non résolus dans `MESSAGES.md` (statut `[EN ATTENTE]`).
- GPU détecté sur ce poste : NVIDIA GeForce RTX 3050, 4096 MiB VRAM, pilote 617.42, CUDA 13.4 (Windows).
