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
| MI-006 | Validation complète sur Debian 13 lorsque disponible | BLOCKED (environnement indisponible) | Haute | Agent B | Exécuter la suite `python -m unittest discover -s tests` dès qu'un environnement existe | `continuations/MI-006.md` |
| MI-007 | S5 — Journal d'activité visible `/log` (idée utilisateur 24/10) | IMPLEMENTED (`/log` CLI + `GET /log` web, committé `f66e89c`, suite 738 OK/4 ignorés) — SANS AUDIT INDÉPENDANT | Moyenne | Agent A | Revue B à l'occasion de l'audit de la chaîne | `continuations/MI-007.md` |
| MI-008 | S6 — Raccourcis de connexion fournisseurs (clé API min. de clics, comptes partagés) — catalogue v1.3 + cahier 0.1 | TESTED (S6.1 `dd3e90e` + **S6.2 `82d3143`** : groupes d'identité google→gemini/mistral, étapes réduites « clé seule », clés stockées par fournisseur `MILES_API_KEY_<NOM>`, 10 tests, suite 752 OK/4 ignorés) — SANS AUDIT INDÉPENDANT ; raccourci OAuth navigateur NON implémenté (hors périmètre réseau) | Haute | Agent A | Revue B ; élargissement éventuel OAuth si accord | `continuations/MI-008.md` |
| MI-009 | Refonte UI web — IA de conception spécialisée (parallèle) | TODO (prompt de lancement livré) | Moyenne | Utilisateur + Agent A | Utilisateur lance l'IA design (prompt : `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md`) ; revue Agent A à réception | `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md` |
| MI-010 | E2 — Étude fournisseur local (RTX 3050 4 Go) | TESTED-conclusion (rapport `LOCAL_PROVIDER_FEASIBILITY_STUDY.md` `79f8552`) — SANS AUDIT ; décision utilisateur attendue (llama.cpp vs Ollama) | Moyenne | Agent A + utilisateur | Décision moteur local, puis test de connectivité réel | `docs/reports/LOCAL_PROVIDER_FEASIBILITY_STUDY.md` |
| MI-011 | E3 (audit interne + correctif S-E3-04 fail-closed `6d8f42c`), E4 démarrage/arrêt web, P3 `POST /logout` | TESTED (E4 vérifié en réel : 200 OK, écoute 127.0.0.1, jeton affiché, arrêt propre ; logout `d0ed840`, 741 tests OK/4 ignorés) — SANS AUDIT INDÉPENDANT | Moyenne | Agent A | Revue B opportuniste ; test d'accès externe (refus attendu) si VM dispo | `docs/reports/E4_WEB_STARTUP_CHECK_AGENT_A.md` |
| MI-012 | S3 — Première action d'écriture confirmée `action_write_note` | TESTED (`a802715` : confinée à `data/notes/`, anti-écrasement, confirmation humaine MEDIUM + permission `ecriture_note`, 8 tests ; 5 gardes anti-régression mises à jour volontairement ; suite **749 OK/4 ignorés**) — SANS AUDIT INDÉPENDANT | Haute | Agent A | Revue B (zone permissions d'écriture) ; élargissement du périmètre d'écriture interdit sans décision humaine | `app/tools/local_actions.py` (handler), `tests/test_write_note.py` |
| MI-013 | Premières fonctions d'assistant : `/memory-search` + `/export` conversation | TESTED (`3357de3` : recherche mémoire en lecture seule ; export markdown confiné `data/notes/` avec confirmation, réutilisant S3 ; 9 tests, suite **761 OK/4 ignorés**) — SANS AUDIT INDÉPENDANT | Moyenne | Agent A | Suite logique : exports enrichis, résumés (dès qu'un fournisseur IA réel sera autorisé) | `tests/test_cli_assistant_functions.py` |
| MI-009 | Refonte UI web — IA de conception spécialisée (parallèle) | TODO (prompt de lancement livré) | Moyenne | Utilisateur + Agent A | Utilisateur lance l'IA design (prompt : `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md`) ; revue Agent A à réception | `docs/web_design/PROMPT_DE_LANCEMENT_WEB.md` |

## Archives

| ID | Daté de clôture | H-### | Branche / SHA | Rapport |
|----|-----------------|-------|---------------|---------|
| (vide — aucune mission clôturée depuis la création du registre) | | | | |

Index détaillé : `archive/INDEX.md`.
