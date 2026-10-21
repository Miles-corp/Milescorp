# docs/coordination/DECISIONS.md — Registre des décisions MILES

Convention : chaque décision reçoit un ID `DEC-###` (ou `D-###`), une date, un auteur, un contexte, la décision et un statut (`PROPOSEE`, `ACCEPTEE`, `REJETEE`, `OBSOLETE`). Journal append-only : les décisions ne sont jamais modifiées rétroactivement.

## DEC-001 — Système de coordination asynchrone par fichiers Markdown

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Deux instances OpenCode sur deux PC distincts, aucun serveur permanent, aucun service payant, pas de communication directe entre agents.
- **Décision** : La coordination s'appuie exclusivement sur des fichiers Markdown dans `docs/coordination/` (`AGENTS.md`, `WORKFLOW.md`, `TASKS.md`, `DECISIONS.md`, `STATUS.md`, `HANDOFF.md`, `REPORT_TEMPLATE.md`), synchronisés via Git et GitHub. La communication est asynchrone.
- **Statut** : ACCEPTEE

## DEC-002 — Identifiants des agents et format des tâches

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Il faut distinguer clairement les deux agents et tracer chaque tâche.
- **Décision** : Les agents sont `Agent A` (PC principal, git `DripMind`) et `Agent B` (second PC). Les tâches utilisent l'identifiant `TASK-###` avec les statuts `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`.
- **Statut** : ACCEPTEE

## DEC-003 — Pas de développement fonctionnel dans la Mission 001

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : La mission 001 concerne uniquement l'organisation, la documentation et les règles de collaboration.
- **Décision** : Aucune fonctionnalité de l'assistant MILES n'est développée durant cette mission.
- **Statut** : ACCEPTEE

## DEC-004 — Aucun push automatique vers GitHub

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : L'utilisateur a demandé de ne rien publier sans son autorisation.
- **Décision** : Les documents sont créés localement. Aucun commit ni push n'est effectué sans accord explicite pour publier.
- **Statut** : ACCEPTEE

## DEC-005 — Architecture hybride distant/local avec sélection explicite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande un fournisseur local sur PC avec GPU NVIDIA (RTX 3050, 4 Go VRAM détectés via nvidia-smi).
- **Décision** : Réutiliser `LocalProvider` existant (serveur local HTTP type Ollama/llama.cpp). Aucune réécriture des fournisseurs distants. Sélection explicite via `MILES_PROVIDER` ou `--provider`. Pas de basculement silencieux. Diagnostic GPU via `nvidia-smi` (lecture seule, optionnel). MILES ne télécharge aucun modèle.
- **Statut** : ACCEPTEE

## DEC-006 — Mémoire persistante locale SQLite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-006 demande une mémoire persistante locale, contrôlable par l'utilisateur, indépendante du fournisseur IA.
- **Décision** : SQLite (stdlib Python) en fichier unique `data/memory.db`. Trois notions séparées : historique de session (éphémère), préférences (key-value), souvenirs explicites (uniquement à la demande utilisateur via `/remember`). Détection des motifs secrets au moment de l'enregistrement. Budget de contexte configurable. Dégradation gracieuse si base absente/corrompue/indisponible. Base exclue de Git via `.gitignore` (`data/*.db`).
- **Statut** : ACCEPTEE

## DEC-007 — Interface web http.server sur 127.0.0.1, zéro dépendance

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande une interface web pour converser avec MILES.
- **Décision** : Utiliser `http.server` de la bibliothèque standard Python (zéro dépendance supplémentaire). Serveur sur `127.0.0.1` uniquement par défaut. Routes : `/` (page d'accueil + formulaire), `/message` (POST), `/status` (GET), `/memory` (GET), `/remember` (POST), `/forget` (POST). Séparation claire entre serveur web, logique applicative (WebApp) et fournisseurs IA. Évolution vers Flask possible ultérieurement.
- **Statut** : ACCEPTEE

## DEC-008 — Couche métier unique `ToolService` partagée par le CLI et l'interface web

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : le moteur d'outils de la Phase 4 existait mais n'était branché nulle part. Le CLI disposait d'un chemin d'action parallèle (`propose_action()` / `ActionValidator`) jamais appelé, et le web n'exposait aucune route d'outils. Brancher les deux interfaces demandait de ne pas dupliquer la logique métier (validation, permissions, confirmation, délai, audit).
- **Décision** : introduire `app/tools/service.py` (`ToolService`) comme **unique** point d'entrée vers le moteur d'outils. Le CLI (`/tools`, `/tool`) et l'interface web (`GET /tools`, `POST /tool`) reçoivent la **même instance**, construite une seule fois dans `miles.py`. Le registre par défaut (`app/tools/builtin.py`) n'enregistre que des outils réellement implémentés ; les handlers sont des fonctions de niveau module picklables (le moteur exécute dans un sous-processus). L'ancien `propose_action()` est conservé pour compatibilité mais n'est plus le chemin d'exécution. Les actions MEDIUM/HIGH exigent une confirmation humaine explicite (CLI : saisie clavier ; web : boîte de confirmation), via le mécanisme de jeton existant du moteur (lié à l'outil et aux paramètres exacts, usage unique, TTL 300 s).
- **Conséquences** : comportement identique par construction entre les deux interfaces (vérifié par test d'identité du service), aucune nouvelle dépendance, aucun appel API payant. Limite assumée : le jeton n'est pas lié à une identité utilisateur ; à traiter avant toute exposition des outils au modèle.
- **Statut** : ACCEPTEE
