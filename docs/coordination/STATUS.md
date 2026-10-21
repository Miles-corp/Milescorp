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
