# docs/coordination/TASKS.md — Tableau de suivi des tâches MILES

Convention :
- ID : `TASK-###`
- Statuts : `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`
- Agents : `Agent A`, `Agent B`
- Une tâche est terminée uniquement quand son statut est `DONE`, le résultat attendu produit, et les contrôles exécutés.

## Tâches en cours / initiales (Mission 001)

| ID | Titre | Description | Statut | Assigné à | Fichiers concernés | Résultat attendu | Bloqué par | Créé le | Mis à jour le |
|----|-------|-------------|--------|-----------|--------------------|------------------|------------|---------|---------------|
| TASK-001 | Mise en place de la structure de coordination | Créer AGENTS.md et les documents de docs/coordination/ | DONE | Agent A | AGENTS.md, docs/coordination/*.md | Documents de coordination cohérents, règles définies, workflow Git documenté | — | 2026-10-19 | 2026-10-19 |
| TASK-002 | Revue indépendante de l'organisation | Vérifier que les consignes sont claires, complètes et applicables par Agent B | TODO | Agent B | docs/coordination/*.md, AGENTS.md | Liste des oublis, ambiguïtés et suggestions d'amélioration | — | 2026-10-19 | — |
| TASK-003 | Vérification des consignes et tests documentés | Exécuter les contrôles réalisables sur les documents de coordination et consigner les résultats | TODO | Agent B | docs/coordination/*.md | Rapport de vérification (contrôles exécutés et résultats) | — | 2026-10-19 | — |
| TASK-004 | Détection des oublis et des ambiguïtés | Identifier ce qui manque ou ce qui est mal défini dans l'organisation | TODO | Agent B | docs/coordination/*.md, AGENTS.md | Liste d'éléments à corriger ou préciser | — | 2026-10-19 | — |

| TASK-DEV-001 | Premier prototype fonctionnel MILES | Créer un prototype exécutable : interface terminal, fournisseurs IA hybride, contexte conversationnel, actions locales, voix optionnelle | DONE | Agent A | app/**, config/**, tests/**, miles.py, requirements.txt, .gitignore | Programme lançable en terminal, conversation avec IA, contexte de session, actions locales autorisées, voix optionnelle documentée | — | 2026-10-19 | 2026-10-19 |
| TASK-DEV-002 | Revue indépendante des tests et vérification | Exécuter les tests sur Debian 13, vérifier le bon fonctionnement du mode texte, détecter les oublis et ambiguïtés | TODO | Agent B | tests/*.py (lecture et modification autorisée), miles.py (lecture seule), app/ (lecture seule) | Tous les tests passent sur Debian 13, rapport de vérification | Dépend de TASK-DEV-001 publié sur GitHub | — | — |

## Registre des fichiers et propriétaires (Mission DEV-001)

| Chemin exact | Objectif | Propriétaire | Statut | Dépendances | Contrat / Interface | Tâche associée |
|--------------|----------|--------------|--------|-------------|---------------------|----------------|
| miles.py | Point d'entrée du programme | Agent A | Disponible | app/config/settings.py, app/interface/cli.py | CLI : argparse, fonction main() | TASK-DEV-001 |
| .gitignore | Règles d'ignore Git | Agent A | Disponible | — | — | TASK-DEV-001 |
| requirements.txt | Dépendances Python (optionnelles) | Agent A | Disponible | — | — | TASK-DEV-001 |
| app/config/settings.py | Chargement config JSON + variables d'env | Agent A | Disponible | — | Classe Settings, méthodes get()/provider | TASK-DEV-001 |
| app/ai_providers/base.py | Interface abstraite des fournisseurs IA | Agent A | Disponible | — | ABC AIProvider : chat(), is_available(), name | TASK-DEV-001 |
| app/ai_providers/remote.py | Fournisseur IA distant (HTTP) | Agent A | Disponible | app/ai_providers/base.py | Implémente AIProvider | TASK-DEV-001 |
| app/ai_providers/local.py | Fournisseur IA local | Agent A | Disponible | app/ai_providers/base.py | Implémente AIProvider | TASK-DEV-001 |
| app/core/conversation.py | Historique ordonné des messages | Agent A | Disponible | — | Classe Conversation : add_user_message(), get_context() | TASK-DEV-001 |
| app/memory/history.py | Enveloppe session de conversation | Agent A | Disponible | app/core/conversation.py | Classe History | TASK-DEV-001 |
| app/interface/cli.py | Boucle terminal et affichage | Agent A | Disponible | app/core/conversation.py, app/security/validator.py | Classe CLI : run(), propose_action() | TASK-DEV-001 |
| app/security/validator.py | Registre et validation des actions locales | Agent A | Disponible | — | Classe ActionValidator : execute(), is_allowed() | TASK-DEV-001 |
| app/connectors/computer/actions.py | Actions locales sûres (datetime, workdir, list_files) | Agent A | Disponible | — | Classe ComputerActions | TASK-DEV-001 |
| app/voice/base.py | Interface vocale optionnelle (stubs) | Agent A | Disponible | — | Classe VoiceInterface : speak(), listen() | TASK-DEV-001 |
| config/config.json.example | Exemple de configuration (sans secrets) | Agent A | Disponible | — | JSON valide | TASK-DEV-001 |
| .env.example | Exemple de variables d'environnement (sans secrets) | Agent A | Disponible | — | — | TASK-DEV-001 |
| tests/test_conversation.py | Tests de l'historique et du contexte | Agent B | Disponible | unittest, app/core/conversation.py | — | TASK-DEV-002 |
| tests/test_actions.py | Tests du validateur d'actions | Agent B | Disponible | unittest, app/security/validator.py | — | TASK-DEV-002 |
| tests/test_providers.py | Tests des fournisseurs (simulés) | Agent B | Disponible | unittest, app/ai_providers/base.py | — | TASK-DEV-002 |
| docs/reports/DEV-001.md | Rapport de mission pour Agent B | Agent A | Disponible | — | Markdown | TASK-DEV-001 |

## Règles d'attribution

- Une tâche `TODO` peut être prise par l'agent désigné ou, à défaut, par l'agent disponible après coordination explicite.
- Une tâche `IN_PROGRESS` appartient à l'agent indiqué dans `assigned-to` ; l'autre agent ne doit pas y travailler sans accord.
- Une tâche `BLOCKED` doit faire l'objet d'une explication dans `STATUS.md` avant toute réassignation.
