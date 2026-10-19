# docs/reports/MILESTONE-005.md — Rapport MILESTONE-005 : Assistant personnel hybride (Agent A)

## 1. Objectif

Faire évoluer le prototype MILES validé afin que l'utilisateur puisse choisir **explicitement** entre :
- un fournisseur IA distant (déjà présent : `RemoteProvider`),
- un fournisseur IA local fonctionnant sur le PC équipé d'un GPU NVIDIA (déjà présent : `LocalProvider`, se connectant à un serveur local type Ollama/llama.cpp).

Aucun nouveau fournisseur hypothétique n'est créé. Le `LocalProvider` existant est réutilisé tel quel.

## 2. Audit technique préalable

### Fournisseurs existants (conservés tels quels)

| Fournisseur | Fichier | Rôle | Protocole |
|-------------|---------|------|-----------|
| Distant | `app/ai_providers/remote.py` | API HTTP distante (OpenAI-like) | `urllib` (stdlib) |
| Local | `app/ai_providers/local.py` | Serveur de modèle local (Ollama, llama.cpp) | `urllib` (stdlib) |

### Contrat de base (`app/ai_providers/base.py`)

- `chat(messages) -> str`
- `is_available() -> bool`
- `name` (property)
- Erreurs : `AIProviderError`

### Configuration (`app/config/settings.py`)

Déjà supporté : `provider` = `"remote"` ou `"local"`, avec `remote_*` et `local_*` (base_url, model, timeout, api_key). Aucune clé en dur.

### Historique (`app/core/conversation.py`)

- `history_limit` = nombre de messages (pas d'échanges)
- Conversation préservée en cas d'erreur fournisseur (cli.py)

### Dépendances

- Python 3 + stdlib uniquement (`urllib`, `json`, `unittest`)
- Aucune dépendance externe obligatoire
- Dépendances vocales (`pyttsx3`, `speech_recognition`) optionnelles

### GPU détecté (nvidia-smi, lecture seule, non destructif)

| Élément | Valeur |
|---------|--------|
| GPU | NVIDIA GeForce RTX 3050 |
| VRAM totale | 4096 MiB (4 Go) |
| VRAM utilisée | 1298 MiB |
| Pilote | 617.42 |
| CUDA | 13.4 |
| OS | Windows (WDDM) |

Le GPU est géré par le serveur local (Ollama/llama.cpp), pas par MILES directement. MILES se connecte au serveur local via HTTP.

## 3. Architecture retenue

### Principe

Conserver `RemoteProvider` et `LocalProvider` inchangés. Ajouter :
1. Un utilitaire de diagnostic GPU (`app/utilities/gpu_info.py`) pour documenter le matériel disponible.
2. Des tests automatisés (mocks uniquement) pour la sélection explicite, l'absence de basculement silencieux, la gestion d'erreur, la préservation de l'historique.
3. Une documentation d'installation locale (Ollama/llama.cpp avec GPU) dans `docs/installation/INSTALL.md` (déjà créé par Agent B).
4. Une décision d'architecture consignée (`DEC-005`).

### Fichiers créés / modifiés

| Fichier | Action | Rôle |
|---------|--------|------|
| `app/utilities/__init__.py | Créé | Package utilitaires |
| `app/utilities/gpu_info.py | Créé | Détection GPU NVIDIA via nvidia-smi (lecture seule) |
| `tests/test_milestone_005.py | Créé | Tests sélection remote/local, pas de basculement silencieux, erreur fournisseur, préservation historique |
| `app/interface/cli.py | Modifié | Correction L-005 : `conversation or Conversation(...)` → `if conversation is None` |
| `docs/coordination/TASKS.md | Modifié | Ajout TASK-DEV-005, registre des fichiers |
| `docs/coordination/STATUS.md | Modifié | Objectif MILESTONE-005 |
| `docs/coordination/DECISIONS.md | Modifié | DEC-005 architecture hybride |
| `docs/coordination/MESSAGES.md | Modifié | M-002 réponse à M-001 (L-005 corrigé) |
| `docs/reports/MILESTONE-005.md | Créé | Ce rapport |

### Fichiers non modifiés (intentionnellement)

- `app/ai_providers/remote.py` — conservé tel quel (règle : ne pas réécrire les fournisseurs distants)
- `app/ai_providers/local.py` — conservé tel quel (déjà compatible avec l'architecture)
- `app/config/settings.py` — conservé tel quel (déjà supporte remote/local)
- `tests/test_*.py` existants — attribués à Agent B, non modifiés

## 4. Décisions d'architecture

### DEC-005 — Architecture hybride distant/local avec sélection explicite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande un fournisseur local sur PC avec GPU NVIDIA (RTX 3050, 4 Go VRAM).
- **Décision** : Réutiliser `LocalProvider` existant (serveur local HTTP type Ollama/llama.cpp). Aucune réécriture des fournisseurs. Sélection explicite via `MILES_PROVIDER` ou `--provider`. Pas de basculement silencieux. Diagnostic GPU via `nvidia-smi` (lecture seule, optionnel).
- **Statut** : ACCEPTEE

## 5. Dépendances supplémentaires

- Aucune dépendance externe obligatoire.
- `app/utilities/gpu_info.py` utilise uniquement `subprocess` (stdlib) pour appeler `nvidia-smi` si présent.
- Pour utiliser le mode local avec GPU, l'utilisateur doit installer séparément un serveur local (Ollama, llama.cpp) et un modèle compatible avec 4 Go VRAM. MILES ne télécharge aucun modèle.

## 6. Tests automatisés

Fichier : `tests/test_milestone_005.py`

| Test | Couverture | Statut (prévu) |
|------|------------|----------------|
| Sélection fournisseur distant | `RemoteProvider` créé, nom commence par "remote" | À exécuter |
| Sélection fournisseur local | `LocalProvider` créé, nom commence par "local" | À exécuter |
| Pas de basculement silencieux | Instances distinctes, nom correct | À exécuter |
| Fournisseur distant indisponible | `is_available()` retourne bool | À exécuter |
| Fournisseur local erreur connexion | `AIProviderError` levé | À exécuter |
| Préservation historique après erreur | Message utilisateur conservé | À exécuter |
| Fournisseur invalide rejeté | `SettingsError` pour `MILES_PROVIDER=inconnu` | À exécuter |
| CLI indique fournisseur actif | `cli.provider.name` correct | À exécuter |

**Contrainte** : `python3` n'est pas installé sur ce PC Windows. Les tests n'ont pas été exécutés. Ils doivent l'être sur Debian 13 ou un poste avec Python 3.

## 7. Essais locaux réels

Aucun essai d'inférence réel n'a été effectué :
- Aucun serveur local (Ollama/llama.cpp) n'est installé sur ce poste.
- Aucun modèle n'est téléchargé.
- Aucun fournisseur IA distant n'est configuré.
- Le GPU n'est pas utilisé par MILES directement (géré par le serveur local).

## 8. Critères d'acceptation

| Critère | Statut |
|---------|--------|
| Fournisseurs distants existants compatibles | ✅ Conservés inchangés |
| Mode local documenté et testable | ✅ `LocalProvider` existant + INSTALL.md + tests |
| Utilisateur choisit le mode explicitement | ✅ `MILES_PROVIDER` / `--provider`, pas de basculement silencieux |
| Erreurs explicites, pas de perte de contexte | ✅ `AIProviderError`, historique préservé |
| Tests passent | ⚠️ À exécuter (pas de Python 3 sur ce poste) |
| Installation minimale sans voix | ✅ Dépendances stdlib uniquement, voix optionnelle |
| Pas de secrets ni caches de modèles committés | ✅ Vérifié (`.gitignore`, `.env.example`) |
| Guide d'installation locale | ✅ `docs/installation/INSTALL.md` (Agent B) |

## 9. Limites et réserves

- Tests non exécutés (pas de Python 3 sur ce PC Windows).
- Aucun fournisseur IA réel appelé (pas d'endpoint, pas de clé API).
- Validation sur Debian 13 non effectuée (environnement non disponible).
- GPU non utilisé par MILES directement (géré par le serveur local externe).

## 10. Prochaine étape

Exécuter `python3 -m unittest discover -s tests -v` sur un poste avec Python 3 (Debian 13 recommandé) et confirmer que les 38 tests existants + les nouveaux tests MILESTONE-005 passent.
