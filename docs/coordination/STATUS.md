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
| TASK-DEV-008 | Phase 4 : Moteur d'outils sécurisé | DONE | Agent A |
| TASK-DEV-008 | Phase 3B : validation fonctionnelle (terminal, web, mémoire) | DONE | Agent B |

## Blocages

Aucun blocage à ce jour.

## Décisions récentes

- DEC-001 à DEC-004 acceptées (voir `docs/coordination/DECISIONS.md`).
- DEC-005 : Architecture hybride distant/local avec sélection explicite (ACCEPTEE, Agent A).
- DEC-006 : Mémoire persistante locale SQLite (ACCEPTEE, Agent A).
- DEC-007 : Interface web http.server sur 127.0.0.1, zéro dépendance supplémentaire (ACCEPTEE, Agent A).

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
