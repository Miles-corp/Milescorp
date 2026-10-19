# docs/reports/MILESTONE-006.md — Rapport MILESTONE-006 : Mémoire persistante locale (Agent A)

## 1. Objectif

Ajouter à MILES une mémoire persistante locale simple, contrôlable par l'utilisateur et indépendante du fournisseur IA. Elle doit permettre de conserver des informations utiles entre plusieurs lancements sans confondre l'historique complet d'une conversation avec les souvenirs que l'utilisateur souhaite garder.

## 2. Prérequis vérifiés

| Prérequis | Statut | Preuve |
|-----------|--------|--------|
| TASK-DEV-004 (fiabilisation) terminé | DONE | Commit `e156a24`, 38 tests OK |
| TASK-DEV-003 (consolidation) terminé | DONE avec réserves | Commit `89c845c`, tests sur Windows (pas Debian 13) |
| TASK-DEV-005 (MILESTONE-005) terminé | DONE | Commit `5c63332`, architecture hybride distant/local |
| Gestion de conversation stable | Vérifiée (statique) | `app/core/conversation.py`, `app/interface/cli.py` corrigé (L-005) |
| Pas de Python 3 sur ce PC Windows | Limite | Tests non exécutables localement |

## 3. Architecture retenue

### Principe

SQLite (stdlib Python `sqlite3`) pour une base de fichier unique sur la machine de l'utilisateur. Aucune dépendance externe. Aucune synchronisation vers un fournisseur distant. Stockage exclusivement à la demande de l'utilisateur.

### Fichiers créés / modifiés

| Fichier | Action | Rôle |
|---------|--------|------|
| `app/memory/persistent.py` | Créé | Classe `PersistentMemory` : CRUD souvenirs, préférences, contexte IA, détection secrets |
| `app/memory/__init__.py` | Modifié | Exports `PersistentMemory`, `PersistentMemoryError` |
| `app/config/settings.py` | Modifié | Nouvelles options `memory_*`, validation |
| `app/interface/cli.py` | Modifié | Commandes `/remember`, `/memory`, `/forget`, affichage statut mémoire |
| `miles.py` | Modifié | Instanciation `PersistentMemory` et passage au `CLI` |
| `tests/test_memory_persistent.py` | Créé | 18 tests (init, ajout, lecture, persistance, suppression, effacement, base invalide, secrets, préférences, contexte) |
| `config/config.json.example` | Modifié | Options `memory_*` |
| `.env.example` | Modifié | Variables `MILES_MEMORY_*` |
| `docs/reports/MILESTONE-006.md` | Créé | Ce rapport |
| `docs/coordination/TASKS.md` | Modifié | TASK-DEV-006 + registre fichiers |
| `docs/coordination/STATUS.md` | Modifié | Objectif MILESTONE-006 |
| `docs/coordination/DECISIONS.md` | Modifié | DEC-006 |

### Fichiers non modifiés (intentionnellement)

- `app/core/conversation.py` — historique de session (éphémère), inchangé
- `app/ai_providers/remote.py` et `local.py` — fournisseurs IA, inchangés (mémoire indépendante)
- `tests/test_*.py` existants — attribués à Agent B, inchangés

## 4. Décision d'architecture : DEC-006

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-006 demande une mémoire persistante locale contrôlable par l'utilisateur, indépendante du fournisseur IA.
- **Décision** : SQLite (stdlib Python) en fichier unique `data/memory.db`. Trois notions séparées : historique de session (éphémère), préférences (key-value), souvenirs explicits (uniquement à la demande utilisateur). Détection des motifs secrets (clé API, mot de passe, token) au moment de l'enregistrement. Budget de contexte configurable. Dégradation gracieuse si base absente/corrompue/indisponible. Base exclue de Git (`.gitignore` couvre `data/*.db`).
- **Statut** : ACCEPTEE

## 5. Schéma de base de données

| Table | Colonnes | Rôle |
|-------|----------|------|
| `schema_version` | `version INTEGER` | Version du schéma (migration) |
| `memories` | `id, content, category, importance, created_at, updated_at` | Souvenirs explicits utilisateur |
| `preferences` | `key, value, updated_at` | Préférences utilisateur |

Version actuelle du schéma : `1`.

## 6. Comportements

| Situation | Comportement |
|-----------|--------------|
| Mémoire désactivée (`MILES_MEMORY_ENABLED=false`) | Toutes les opérations sont des no-op, messages d'information |
| Base absente | Créée automatiquement au premier écrit |
| Base corrompue | Dégradation gracieuse : `is_available = False`, message d'erreur, programme continue sans mémoire |
| Contenu vide | Rejeté (`PersistentMemoryError`) |
| Contenu > `memory_max_content_length` | Rejeté |
| Motif secret détecté (sk-, api_key, password, secret, token…) | Enregistrement refusé |
| Suppression souvenir ciblé | `/forget <id>`, retour booléen |
| Effacement complet | `/memory` puis suppression individuelle, ou `clear_all_memories()` |
| Souvenirs dans le contexte IA | `get_context_memories()` respecte `max_memories_in_context` et `max_content_length` |

## 7. Interface utilisateur (CLI)

| Commande | Action |
|----------|--------|
| `/remember <texte>` | Enregistre un souvenir explicite |
| `/memory` | Liste tous les souvenirs avec id, catégorie, importance |
| `/forget <id>` | Supprime le souvenir d'identifiant donné |
| `/status` | Affiche l'état de la mémoire persistante (activée/désactivée/indisponible) |

L'interface ne enregistre **jamais** automatiquement une conversation comme souvenir.

## 8. Tests automatisés

Fichier : `tests/test_memory_persistent.py`

| Test | Couverture |
|------|------------|
| Initialisation crée la base | ✅ |
| Tables créées | ✅ |
| Mémoire désactivée indisponible | ✅ |
| Ajout + liste souvenir | ✅ |
| Contenu vide rejeté | ✅ |
| Secret refusé (clé API, mot de passe) | ✅ |
| Lecture par id | ✅ |
| Suppression ciblée | ✅ |
| Effacement complet | ✅ |
| Liste par catégorie | ✅ |
| Limite de contenu | ✅ |
| Préférence set/get/delete | ✅ |
| Préférence secret refusé | ✅ |
| Contexte IA respecte la limite | ✅ |
| Contexte vide si désactivé | ✅ |
| Base corrompue → dégradation gracieuse | ✅ |
| Ajout quand indisponible → erreur | ✅ |

Total : 18 tests.

**Contrainte** : `python3` n'est pas installé sur ce PC Windows. Les tests n'ont pas été exécutés localement. Ils doivent l'être sur Debian 13.

## 9. Sécurité et confidentialité

| Règle | Mise en œuvre |
|-------|---------------|
| Stockage sur machine utilisateur | Fichier `data/memory.db` local |
| Exclusion de Git | `.gitignore` couvre `data/*.db` |
| Aucun secret dans les journaux | Détection des motifs secrets au moment de l'enregistrement |
| Aucun mot de passe/clé API stocké | Rejet systématique |
| Emplacement documenté | `MILES_MEMORY_DB_PATH`, défaut `data/memory.db` |
| Suppression possible | `/forget <id>` ou `clear_all_memories()` |
| Tests d'effacement | `test_clear_all_memories`, `test_delete_memory` |

## 10. Critères d'acceptation

| Critère | Statut |
|---------|--------|
| Mémoire persiste entre lancements | ✅ SQLite fichier |
| Utilisateur consulte et efface | ✅ `/memory`, `/forget` |
| Souvenirs distincts de l'historique | ✅ Tables séparées, `Conversation` inchangé |
| Fournisseurs distant/local utilisent la même interface | ✅ `PersistentMemory` indépendant du fournisseur |
| Tests automatisés passent | ⚠️ À exécuter (pas de Python 3) |
| Données privées hors de Git | ✅ `.gitignore` `data/*.db` |
| Installation et désactivation documentées | ✅ `.env.example`, `config.json.example`, INSTALL.md |

## 11. Limites et réserves

- Tests non exécutés (pas de Python 3 sur ce PC Windows).
- Aucun essai de persistance réelle entre deux lancements n'a pu être effectué.
- Validation sur Debian 13 non effectuée (environnement non disponible).
- Aucune clé API ou secret n'est stocké ; les motifs suspects sont refusés.

## 12. Prochaine étape

Exécuter `python3 -m unittest discover -s tests -v` sur un poste avec Python 3 (Debian 13 recommandé) pour confirmer que les 38 tests existants + les 18 nouveaux tests de mémoire passent.
