# docs/coordination/MISSIONS_REGISTRY.md — Registre global des missions actives

Source de vérité pour l'état des missions. Les détails vivent dans
`docs/coordination/continuations/MI-###.md` (une fiche autonome par mission),
les preuves dans `docs/reports/` et `docs/coordination/STATUS.md`/`HANDOFF.md`.

## Règles

- Une ligne par mission active ; passage en archive (table du bas) après clôture,
  jamais de suppression de ligne.
- Chaque changement de statut met à jour cette table ET la continuation.
- Une mission AWAITING_AUDIT reste non approuvée tant que l'audit B manque.

## Missions actives

| ID | Résumé | Statut | Prio | Responsable | Prochaine action | Continuation |
|----|--------|--------|------|-------------|------------------|--------------|
| MI-001 | Audit indépendant de la correction D1 (`6b736d7`) | TODO (EN ATTENTE, M-006/M-007) — **analyse interne effectuée** (voir `SECURITY_AUDIT_E3_AGENT_A.md` §3 : correctif cohérent, SANS AUDIT INDÉPENDANT) | Haute | Agent B | Conclure l'audit TASK-DEV-019 | `continuations/MI-001.md` |
| MI-002 | Intégration ordonnée de la chaîne post-D1 (TASK-DEV-023) | IN_PROGRESS (chaîne + 2 divergences intégrées : `99b722c` ; INSTALL.md à jour : `0fcff9f` ; suite 719 OK/4 ignorés) | Haute | Agent A | Audit D1 (MI-001) ; ensuite décision utilisateur pour toute suite d'intégration | `continuations/MI-002.md` |
| MI-003 | Publier + faire auditer la branche diagnostics `78ac05c` | IMPLEMENTED → PUBLICATION AUTORISÉE (push accordé par l'utilisateur le 24/10) | Moyenne | Agent A | Push effectué ; ensuite audit B | `continuations/MI-003.md` |
| MI-004 | Trancher le sort de `fix/miles-paths-posix-spaces` (branche sans commit) | BLOCKED (décision humaine) | Basse | Utilisateur + Agent A | Décider : conservation ou suppression explicite | `continuations/MI-004.md` |
| MI-005 | Corriger l'octet NULL du blob D3 `0be08cd` (sans réécriture d'historique) | DONE dans la copie fusionnée (`99b722c` : NUL remplacé par littéral, blobs sources intacts) ; audit interne E3 : `SECURITY_AUDIT_E3_AGENT_A.md` (`982c065`) | Basse | Agent A | Revue B sur l'ensemble | `continuations/MI-005.md` |
| MI-006 | Validation complète sur Debian 13 | VALIDATED (audit B 2026-10-25 : 773 tests OK, 0 échec, 0 ignoré sur Debian 13, SHA d60ce99) | Haute | Agent B | Conclu — Debian 13 maintenant validé | `continuations/MI-006.md` |
| MI-007 | S5 — Journal d'activité visible `/log` (idée utilisateur 24/10) | IMPLEMENTED (`/log` CLI + `GET /log` web, committé `f66e89c`, suite 738 OK/4 ignorés) — SANS AUDIT INDÉPENDANT | Moyenne | Agent A | Revue B à l'occasion de l'audit de la chaîne | `continuations/MI-007.md` |
| MI-008 | S6 — Raccourcis de connexion fournisseurs (clé API min. de clics, comptes partagés) — catalogue v1.3 + cahier 0.1 | TESTED (S6.1 `dd3e90e` + **S6.2 `82d3143`** : groupes d'identité google→gemini/mistral, étapes réduites « clé seule », clés stockées par fournisseur `MILES_API_KEY_<NOM>`, 10 tests, suite 752 OK/4 ignorés) — SANS AUDIT INDÉPENDANT ; raccourci OAuth navigateur NON implémenté (hors périmètre réseau) | Haute | Agent A | Revue B ; élargissement éventuel OAuth si accord | `continuations/MI-008.md` |
| MI-009 | Refonte UI web — IA de conception spécialisée (parallèle) | TODO (prompt de lancement livré) | Moyenne | Utilisateur + Agent A | Utilisateur lance l'IA design (prompt : `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md`) ; revue Agent A à réception | `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md` |
| MI-010 | E2 — Étude fournisseur local (RTX 3050 4 Go) | TESTED-conclusion (rapport `LOCAL_PROVIDER_FEASIBILITY_STUDY.md` `79f8552`) — SANS AUDIT ; décision utilisateur attendue (llama.cpp vs Ollama) | Moyenne | Agent A + utilisateur | Décision moteur local, puis test de connectivité réel | `docs/reports/LOCAL_PROVIDER_FEASIBILITY_STUDY.md` |
| MI-011 | E3 (audit interne + S-E3-04 `6d8f42c`), E4 démarrage/arrêt web, P3 `POST /logout` | AUDITÉ B (2026-10-25) : VALIDÉ SOUS RÉSERVES (sessions/grants solides ; S-E3-04 corrigé `6d8f42c`, S-E3-04b context_id corrigé `167dd1d`, logout `d0ed840`) | Moyenne | Agent A | Revue B opportuniste | `docs/reports/E4_WEB_STARTUP_CHECK_AGENT_A.md` |
| MI-012 | S3 - Première action d'écriture confirmée `action_write_note` | AUDITÉ B (2026-10-25) : VALIDÉ (12/12 critères, mutation anti-écrasement discriminante) ; réserve MI-017 (stem) corrigée `167dd1d` | Haute | Agent A | Élargissement du périmètre d'écriture interdit sans décision humaine | `app/tools/local_actions.py`, `tests/test_write_note.py` |
| MI-017 | P3 audit B S3 - is_sensitive_filename elargi + test limite 4000 car. | TESTED (d60ce99 : 9 tests, suite 773 OK/4 ignores) - SANS AUDIT | Moyenne | Agent A | Revue B | app/tools/local_actions.py |
| MI-016 | P3 audit B mémoire - filtres owner_user_id sur clear_all/get_context | VALIDÉ (audit B : filtres conformes, 772 OK Win+Debian) | Moyenne | Agent A | Conclu | app/memory/persistent.py |
| MI-018 | Renforcement paths.py - regex espacement (4 contournements corrigés) | VALIDÉ (audit B sur `abb14c7` : 19/19 refusées, 774 OK/5 ign. Win, 774 OK/0 ign. Debian) | Moyenne | Agent A | Conclu | app/security/paths.py |
| MI-019 | Réserves audits B : S-E3-04b fail-closed (context_id=None) + MI-017 stem sensible (`secret.md`) | TESTED (`167dd1d` : 776 OK/5 ignorés Windows, 765 OK/0 échec Linux) - EN ATTENTE REVUE B | Haute | Agent A | Revue B (zone autorisations) | app/tools/grants.py, app/tools/local_actions.py |
| MI-021 | Réconciliation mémoire Debian/Windows (transfert 2026-10-26, branche `origin/audit/agent-b-phase6-1-web-security-review` : 8977a17, c0f495a, ee5e63d) | TRAITÉ (correction 26/10) — preuves : `git show ee5e63d --stat` = **2 suppressions uniquement** (`memory.close()`) ; `git diff c74c215 <tip audit> -- miles.py` = +3/−2 (avertissement dégradé = +3, déjà porté en `34a401b`) ; **l'absence des bornes Phase 6.2 sur cette branche est un artefact de lignée** (branche née avant la Phase 6.2) : les bornes `max_tool_calls`/`max_interactions` SONT présentes dans l'intégration (`ba1ead5`) ; `close()` conservé (23/23 tests ciblés OK côté Windows) | Haute | Agent A | **PROPOSITIONS de B** : B a modifié du code de production (8977a17, c0f495a, ee5e63d) — à revue par A, **NON AUDÉS**, aucune absorption avant revue | miles.py |
| MI-022 | Mémoire avancée (résumés, contradictions, faits/hypothèses) - SPÉCIFICATION proposée, 0 code | SPEC livrée (`docs/specs/MEMOIRE_AVANCEE_SPEC.md`) — en attente de validation utilisateur puis audit B de persistent.py ; règles étroites anti-faux-positif, kind inconnu par défaut, zéro réseau par défaut | Moyenne | Agent A | Décision : valider ou amendé la spec | docs/specs/MEMOIRE_AVANCEE_SPEC.md |
| MI-015 | Correction sécurité paths.py - refus chemins Windows absolus sur Linux | VALIDÉ (audit B sur `abb14c7` : 19/19 variantes refusées, 774 OK Win+Debian) | Moyenne | Agent A | Conclu | app/security/paths.py |
| MI-014 | Portabilite Linux/WSL - compteur deterministe (forkserver-safe), chemins externes adaptes, extraction POSIX avec espaces, dedup par prefixe | VALIDATED (audit B : 772 tests OK Win+Debian, 0 echec) | Moyenne | Agent A | Audit B conclu - confirme forkserver sur Debian 13 | app/orchestration/planner.py, tests concernes |
| MI-013 | Premieres fonctions d'assistant : `/memory-search` + `/export` conversation | TESTED (`3357de3` : recherche mémoire en lecture seule ; export markdown confiné `data/notes/` avec confirmation, réutilisant S3 ; 9 tests, suite **761 OK/4 ignorés**) — SANS AUDIT INDÉPENDANT | Moyenne | Agent A | Suite logique : exports enrichis, résumés (dès qu'un fournisseur IA réel sera autorisé) | `tests/test_cli_assistant_functions.py` |
| MI-009 | Refonte UI web — IA de conception spécialisée (parallèle) | TODO (prompt de lancement livré) | Moyenne | Utilisateur + Agent A | Utilisateur lance l'IA design (prompt : `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md`) ; revue Agent A à réception | `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md` |

## Archives

| ID | Daté de clôture | H-### | Branche / SHA | Rapport |
|----|-----------------|-------|---------------|---------|
| (vide — aucune mission clôturée depuis la création du registre) | | | | |

Index détaillé : `archive/INDEX.md`.






