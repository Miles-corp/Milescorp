# docs/reports/PHASE_2_DISTANT_PROVIDER_WEB.md — Rapport Phase 2 : Fournisseur distant connecté + Interface web (Agent A)

## 1. Commit de départ et commit final

| Élément | Valeur |
|---------|--------|
| Commit de départ | `0ad3a41` (TEST-001/TEST-002 rapports, correction L-006, QUICKSTART) |
| Commit final | En attente de publication (modifications locales non committées) |
| Branche | `main` (synchronisé avec `origin/main`) |

## 2. Fichiers créés ou modifiés

### Créés
| Chemin | Rôle |
|--------|------|
| `app/interface/web.py` | Interface web `http.server` (stdlib), serveur sur `127.0.0.1`, routes `/`, `/status`, `/message`, `/memory`, `/remember`, `/forget` |
| `tests/test_web.py` | 16 tests simulés : index, status, message (avec/sans fournisseur, message vide, échec fournisseur, réponse malformée), mémoire (liste, remember, forget, désactivée, id invalide), route inconnue |
| `tests/test_env_loading.py` | 5 tests : chargement .env, priorité processus, fichier absent, guillemets, pas de secret dans les logs |
| `tests/test_provider_selection.py` | 10 tests : sélection remote/local, pas de basculement silencieux, échec fournisseur, fournisseur invalide rejeté |

### Modifiés
| Chemin | Modification |
|--------|--------------|
| `miles.py` | Instancie `RemoteProvider` ou `LocalProvider` selon `settings.provider`, passe l'instance au `CLI` |
| `app/config/settings.py` | Ajoute `_load_env_file()` (chargement .env stdlib, priorité aux variables du processus), ajoute options `memory_*` (déjà présentes), propriétés `memory_enabled`, `memory_db_path`, etc. |
| `app/interface/cli.py` | Ajoute commande `memory` et `memory` paramètre au constructeur `CLI` |
| `app/interface/__init__.py` | Exporte `CLI`, `MilesHandler`, `MilesWebServer`, `WebApp` |
| `app/memory/persistent.py` | Thread-safety : `check_same_thread=False`, `threading.RLock()`, dégradation gracieuse sur base corrompue (correction L-006) |
| `config/config.json.example` | Ajoute options `memory_*` |
| `.env.example` | Ajoute variables `MILES_MEMORY_*` |
| `docs/coordination/TASKS.md` | TASK-DEV-005 et TASK-DEV-006 passés en DONE, ajout TASK-DEV-007, registre fichiers mis à jour |
| `docs/coordination/STATUS.md` | État mis à jour, Phase 2 terminée, TASK-DEV-007 ajouté |
| `docs/coordination/DECISIONS.md` | Ajout DEC-007 (interface web http.server) |
| `docs/reports/MILESTONE-005.md` | Rapport MILESTONE-005 (créé précédemment) |
| `docs/reports/MILESTONE-006.md` | Rapport MILESTONE-006 (créé précédemment) |

### Non modifiés (intentionnellement)
- `app/ai_providers/remote.py` : conservé tel quel (règle : ne pas réécrire les fournisseurs existants)
- `app/ai_providers/local.py` : conservé tel quel
- `tests/test_conversation.py`, `test_actions.py`, `test_providers.py`, `test_cli_reliability.py`, `test_settings.py`, `test_voice.py` : attribués à Agent B, non modifiés
- `docs/installation/INSTALL.md` : créé par Agent B, non modifié

## 3. Architecture retenue et raisons

### Fournisseur distant (branchement immédiat)
- `miles.py` instancie `RemoteProvider` quand `settings.provider == "remote"` (valeur par défaut), ou `LocalProvider` quand `"local"`.
- Les paramètres viennent de `Settings` : `remote_base_url`, `remote_model`, `remote_api_key`, `remote_timeout`.
- Aucun basculement silencieux : le fournisseur est sélectionné explicitement.
- Le fournisseur est passé au `CLI`, qui l'utilise dans `_process_input`.

### Chargement du fichier `.env`
- `Settings._load_env_file()` lit `.env` (ou `MILES_ENV_FILE`) avec la bibliothèque standard uniquement.
- Les variables déjà présentes dans `os.environ` sont prioritaires et ne sont pas écrasées.
- Un fichier `.env` absent n'empêche pas le démarrage.
- Les guillemets environnants sont retirés.
- Aucun secret n'est journalisé.

### Interface web (`app/interface/web.py`)
- `WebApp` : logique applicative, indépendante du serveur web. Dépend uniquement des composants métier (fournisseur, conversation, mémoire, settings).
- `MilesHandler` : gestionnaire HTTP (`BaseHTTPRequestHandler`), routes :
  - `GET /` : page d'accueil HTML avec formulaire de conversation
  - `GET /status` : état du fournisseur et de la mémoire
  - `POST /message` : envoyer un message, recevoir la réponse
  - `GET /memory` : lister les souvenirs
  - `POST /remember` : enregistrer un souvenir
  - `POST /forget` : supprimer un souvenir
- `MilesWebServer` : lance `ThreadingHTTPServer` sur `127.0.0.1:8080` par défaut.
- Aucun accès shell arbitraire depuis le navigateur.
- Séparation claire : serveur web / logique applicative / fournisseurs IA.

### Mémoire persistante (correction L-006)
- `PersistentMemory._initialize` ne lève plus d'exception sur base corrompue : met `is_available = False` (dégradation gracieuse).
- Thread-safe : `check_same_thread=False` + `threading.RLock()` pour l'accès multi-thread depuis le serveur web.

## 4. Décisions d'architecture (DEC-005, DEC-006, DEC-007)

Consignées dans `docs/coordination/DECISIONS.md`.

## 5. Tests automatisés (simulateurs uniquement)

| Fichier | Nombre de tests | Couverture |
|---------|----------------|------------|
| `tests/test_web.py` | 16 | Index, status, message (OK/absence fournisseur/vide/échec/malformé), mémoire (liste/remember/forget/désactivé/id invalide), 404 |
| `tests/test_env_loading.py` | 5 | Chargement .env, priorité processus, fichier absent, guillemets, pas de secret |
| `tests/test_provider_selection.py` | 10 | Sélection remote/local, pas de basculement, échec fournisseur, fournisseur invalide |
| **Total nouveaux** | **31** | — |
| **Total existants** | **64** | Conversation, actions, CLI fiabilité, fournisseurs, settings, voix, mémoire persistante, MILESTONE-005 |
| **Total global** | **95** | **95 OK, 0 échec, 0 erreur** |

Tous les tests utilisent des simulateurs (mocks). Aucun appel réseau, aucune clé API, aucun coût.

## 6. Interface web : état

- Serveur `http.server` sur `127.0.0.1:8080` par défaut.
- Page d'accueil avec formulaire de conversation.
- Routes JSON pour statut, message, mémoire.
- Non lancé pour test réel (nécessiterait un fournisseur configuré).
- Pas d'exposition réseau externe (127.0.0.1 uniquement).

## 7. Fournisseur local hors ligne (TASK-DEV-007 — TODO)

Non implémenté dans cette phase. Proposition technique à documenter (voir rapport séparé à venir).

Pour une RTX 3050 (4 Go VRAM) :
- Moteur candidat : llama.cpp (serveur HTTP standalone) ou llama-cpp-python (wrapper Python).
- Modèle candidat : Llama-3.2-1B-Instruct (4-bit, ~0,7-1 Go VRAM) ou Phi-3-mini-4k-instruct (4-bit, ~2-2,2 Go VRAM).
- Fonctionnement hors ligne après téléchargement du modèle.
- **Aucun téléchargement ni installation n'a été effectué** (accord utilisateur requis).

## 8. Sécurité

- Aucune clé API codée en dur.
- Les clés API sont lues depuis `os.environ` (via `.env` ou variables d'environnement du processus).
- Les clés API ne sont jamais journalisées (`as_dict()` existe mais n'est pas appelée dans les logs).
- Le serveur web écoute uniquement sur `127.0.0.1`.
- Aucun accès shell arbitraire depuis l'interface web.
- Les erreurs fournisseur sont retournées sans exposition de secrets internes.

## 9. Commandes réellement exécutées

| Commande | Résultat |
|----------|----------|
| `python -m unittest discover -s tests -v` | 95 tests, 95 OK, 0 échec, 0 erreur (Windows, Python 3.12.10) |
| `python miles.py --help` | Non exécuté (nécessiterait un fournisseur configuré pour test complet) |

## 10. Tests non exécutés et raisons

| Test | Raison |
|------|--------|
| Test réel d'inférence via fournisseur distant | Nécessite accord utilisateur (coût API possible) et clé API |
| Test réel d'interface web avec fournisseur connecté | Nécessite un fournisseur configuré |
| Test du fournisseur local hors ligne | Nécessite accord pour télécharger/installer un moteur et un modèle |
| Validation sur Debian 13 | Environnement non disponible sur ce poste Windows |

## 11. Prochaines tâches recommandées

1. **Proposition technique fournisseur local** (TASK-DEV-007) : documenter moteur + modèle pour RTX 3050 4 Go.
2. **Test réel d'inférence** : après accord utilisateur pour coût API, tester `miles.py` avec un fournisseur distant configuré.
3. **Test réel d'interface web** : lancer le serveur web et vérifier les routes avec un fournisseur configuré.
4. **Validation sur Debian 13** : Agent B exécute les 95 tests sur Debian 13.

---

*Aucun commit ni push n'a été effectué pour ces modifications. L'autorisation de l'utilisateur est requise pour publier.*
