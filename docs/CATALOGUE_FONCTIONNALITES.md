# Catalogue des fonctionnalités MILES — Version 1.4 (mise à jour du 1.3)

> **Suivi partagé** : Agent A (développement) — Agent B (tests et validation).
> **Règle** (section 11) : chaque ligne porte un statut, une preuve et le SHA
> ou la date testée. Une ligne sans preuve = « NON VÉRIFIÉ », jamais « validée ».
> Ce document évolue avec le code réel ; dernière mise à jour : 2026-10-27 (Agent A).

**Statuts utilisés** : `Implémentée` (code existe) · `Testée` (test pertinent exécuté) ·
`Validée` (résultat confirmé, avec preuve citée) · `Partielle` · `Prévue` ·
`À vérifier` · `Non commencée`.

**Branche de référence des preuves** : `integration/miles-post-d1` @ `3836b41`
(807 tests OK Windows — 807 tests OK Linux/WSL, 27/10/2026).

---

## 1. Conversation et intelligence artificielle

- Interface conversationnelle en ligne de commande — **Implémentée, Testée** (CLI, `807 OK`, 27/10).
- Envoi de messages à un fournisseur d'IA distant — **Implémentée, Testée** (tests faux fournisseurs) ; réponse d'un vrai fournisseur : **Validée par B sur Debian** (rapport de transfert 26/10 : `hello`, `MILES OK`, `17×8`, accents — **NON VÉRIFIÉ sur ce SHA/Windows**).
- Sélection du fournisseur remote ou local au lancement — **Implémentée, Testée** (`--provider`, `tests/test_provider_selection.py`).
- Chargement d'un fichier de configuration — **Implémentée, Testée** (`tests/test_settings.py`, `.env` + JSON).
- Historique de conversation conservée pendant la session — **Implémentée, Testée**.
- Erreur de connexion affichée clairement — **Implémentée, Testée** (`tests/test_provider_errors.py`).
- Fournisseur distant testé avec une connexion fonctionnelle — **Validée (Debian, B, 26/10)** ; ce SHA : **NON VÉRIFIÉ**.
- Fournisseur local réellement testé — **Non commencée** ; étude de faisabilité livrée : `docs/reports/LOCAL_PROVIDER_FEASIBILITY_STUDY.md` (`79f8552`).
- Reconnaissance vocale intégrée et testée — **Non commencée**.
- Synthèse vocale intégrée et testée — **Prévue** (stubs `app/voice/base.py` uniquement).
- Conversation vocale complète testée de bout en bout — **Non commencée**.

## 2. Mémoire et personnalisation

- `/remember` — **Validée** (tests + validation fonctionnelle réelle : souvenir après redémarrage, Debian, rapport B 26/10, `/root/Milescorp`).
- `/memory` — **Validée** (idem).
- `/forget` — **Implémentée, Testée**.
- `/clear` — **Implémentée, Testée**.
- Souvenirs conservés après fermeture et redémarrage — **Validée** (B Debian 26/10 + `tests/test_memory_persistence.py`).
- Informations pertinentes retrouvées au bon moment — **Partielle** (`get_context_memories` + filtre propriétaire `bb82341` ; pas de recherche pertinente sémantique).
- Mémoire à long terme organisée — **Partielle** (catégories + importance ; pas de structure avancée).
- Contradictions entre souvenirs détectées ou signalées — **Non commencée**.
- Faits confirmés distingués des hypothèses et inconnues — **Non commencée**.
- Personnalisation durable vérifiée — **Partielle** (préférences persistantes testées ; **non isolées par utilisateur** — P3 documenté, `d60ce99`/audit B).

## 3. Planification et autonomie

- Orchestrateur et boucle d'exécution présents — **Implémentée, Testée** (Phase 6, `0754032`).
- Objectif décomposé en étapes — **Testée** (`tests/test_mission_orchestrator.py`).
- Tâches complexes planifiées — **Testée**.
- Plusieurs actions exécutées successivement — **Testée**.
- Résultats des outils vérifiés — **Testée** (source → lecture, persistance des résultats).
- Erreurs et nouvelles tentatives gérées — **Testée**.
- Tâche interrompue reprise correctement — **Validée** (`test_mission_results_recovery`, Linux `765 OK` MI-019).
- État d'avancement conservé après redémarrage — **Validée** (missions SQLite).
- Confirmation demandée avant les actions sensibles — **Validée** (grants + confirmations, audits B `69bf670`).
- Compte rendu fidèle des actions réellement accomplies — **Implémentée, Testée** (`report.py`).

## 4. Outils et interaction avec le système

- Lecture de fichiers testée — **Validée** (`action_read_file`, refus des fichiers sensibles).
- Écriture de fichiers testée — **Validée** (`action_write_note` : audit B « VALIDÉ », `d60ce99`, 9 tests).
- Commandes système autorisées testées — **Non commencée** (décision actuelle : **aucun accès shell** — politique MILES refuse l'exécution arbitraire ; à clarifier avant tout ajout).
- Scripts et programmes exécutés de façon contrôlée — **Non commencée** (idem).
- Plusieurs outils utilisés dans une même tâche — **Testée** (missions multi-étapes).
- Permissions vérifiées avant une action — **Validée** (ToolPolicy + grants, audits B).
- Actions et résultats consignés dans des journaux — **Validée** (`GET /log` + audit `AuditLogger`, tests `f66e89c`).
- Erreurs diagnostiquées et corrections vérifiées — **Testée** (campagnes de corrections D1→D3, MI-014/015).

## 5. Fiabilité et sécurité

- `/status` vérifiée — **Validée** (tests + diagnostic `/health` `cf7a97e`, sonde sans réseau).
- `/provider` vérifiée — **Testée** (`78ac05c`).
- Conversation préservée après un échec du fournisseur — **Validée**.
- Filtrage des clés secrètes testé — **Validée** (redaction + tests dédiés ; audits B).
- Protection contre les instructions malveillantes testée — **Partielle** (refus secrets/injections de chemins testés ; pas de campagne adversariale complète).
- Permissions contrôlées avant les actions système — **Validée**.
- Durées d'exécution et boucles limitées — **Validée** (bornes Phase 6.2, `tests/test_mission_bounds.py`).
- Coûts des services IA maîtrisés — **Prévue** (charte + interdiction des appels sans accord ; **plafond S1 pas encore instauré**).
- Erreurs gérées sans perte injustifiée de données — **Validée**.
- Diagnostic automatique testé — **Testée** (`availability_probe`, causes distinctes, `cf7a97e`).

## 6. Box physique — calcul et système

Mini-PC Lenovo M75q, RAM, SSD, Debian, démarrage auto, refroidissement — **Prévue** (matériel non instrumenté ; `docs/installation/BOX_DEBIAN_SETUP.md` = Q3 à livrer). Aucune preuve hardware à ce jour.

## 7. Box physique — audio et électronique

Micro, haut-parleur, volume, mode muet, ESP32-S3, LEDs, bouton, capteurs, pièces LG WK7 — **Non commencée**.

## 8. Commandes de l'interface

| Commande | Statut |
|---|---|
| `--help`, `--config`, `--provider remote/local` | **Implémentées, Testées** |
| `/help`, `/quit`, `/q`, `/clear` | **Implémentées, Testées** |
| `/provider`, `/status` | **Validées** (sha `cf7a97e`/`78ac05c`) |
| `/remember`, `/memory`, `/forget` | **Validées** (preuve §2) |
| **Compléments livrés hors du v1.3** | |
| `/memory-search`, `/export` | **Implémentées, Testées** (`3357de3`) |
| `/log` | **Testée** (`f66e89c`) |
| `/tools`, `/tool` | **Implémentées, Testées** (Phase 5) |
| `/mission`, `/missions`, `/mission-status/-answer/-cancel/-resume` | **Implémentées, Testées** (Phase 6) |
| Options routeur `/fast`, `/deep` (si `MILES_ROUTER=1`) | **Testées** (`3836b41`, 15 tests) |

## 9. Développement et tests

- Tests automatisés exécutés avec résultat conservé — **Validée** (807 OK/2 plateformes, 27/10).
- Commit exact testé noté — **Validée** (chaque ligne de ce catalogue porte un SHA).
- 137 tests réussis : résultat historique consigné et daté — **historique conservé** (19/10 ; chiffre courant 807).
- Connexion au fournisseur IA validée après localhost:8000 — **Validée** (Phase 5 + Debian).
- Mémoire après redémarrage validée — **Validée**.
- Filtrage des secrets validé — **Validée**.
- Tests d'intégration de bout en bout réussis — **Testée** (`tests/web_test_support.py`).
- Tests de non-régression après chaque livraison — **Validée** (pratique : chaque ligne = suite avant commit).
- Preuves de test conservées (commande, sortie, date, commit) — **Validée** (rapports + registre).

## 10. Vision à long terme (statut honnête)

| Objectif | Statut |
|---|---|
| Comprendre un objectif exprimé naturellement | Non commencée (pas de NLU dédié) |
| Planifier et réaliser des tâches complexes | Partielle (orchestrateur) |
| Conserver et réutiliser les informations utiles | Partielle (mémoire §2) |
| Reprendre le travail après une interruption | Testée (missions + systèmes de reprise des agents) |
| Utiliser des outils et vérifier leurs résultats | Testée |
| Diagnostiquer certaines pannes | Partielle (`availability_probe`, `/log`) |
| Fonctionner à la voix avec la box physique | Non commencée |
| Respecter les permissions et limites fixées | Validée |
| Reconnaître ses incertitudes | Validée (pratique documentaire : « NON VÉRIFIÉ ») |
| Expliquer ce qui a été réalisé et ce qui reste à faire | Validée (registres + rapports) |

## 11. Statuts (définitions — inchangées)

Implémentée · Testée · Validée · Partielle · Prévue · À vérifier · Non commencée.
Pour chaque validation : date, commit testé, étapes de reproduction, résultat
attendu, résultat observé, défauts éventuels.

## 12. Répartition des responsabilités (inchangée)

- **Agent A (Stan)** : développer/implémenter, corriger les défauts, livrer des commits identifiés.
- **Agent B** : reproduire les défauts indépendamment, exécuter et conserver les preuves,
  vérifier les corrections et rechercher les régressions, tester en environnement isolé.
- **Règle d'équipe** : pas de modification simultanée des mêmes fichiers sans accord.

---

### Annexe — Zones chaudes en attente d'audit B (27/10)

| Zone | SHA | Statut audit |
|---|---|---|
| `POST /configure` (connexion IA web) | `ba1ead5` | **NON AUDÉE** (mission B prête) |
| OAuth `--link` (serveur de rappel local) | `b3cb5a2` | **NON AUDÉ** |
| `GET /log`, CLI `/export` | `f66e89c`, `3357de3` | **NON AUDÉS** |
| MI-019 (fail-closed `context_id` + stem) | `167dd1d` | En attente de revue B |
| Correction D1 | `6b736d7` | TASK-DEV-019 EN ATTENTE (M-006/M-007) |
