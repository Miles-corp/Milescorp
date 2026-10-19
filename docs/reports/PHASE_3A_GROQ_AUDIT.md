# docs/reports/PHASE_3A_GROQ_AUDIT.md — Rapport Phase 3A : Audit fournisseur Groq sans appel réseau (Agent A)

## 1. État du dépôt au début de l'audit

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp.git` |
| Branche | `main` |
| Commit HEAD | `c70f9d1 docs: add Phase 2 final report` |
| Origin/main | `c70f9d1` (synchronisé) |
| Working tree | Propre (avant modifications) |
| Python | 3.12.10 sur Windows |

## 2. Vérifications effectuées

### 2.1 État Git
- `git status` : working tree propre avant audit
- `git branch --show-current` : `main`
- `git log --oneline` : `c70f9d1` est le dernier commit
- `git fetch origin` : `origin/main` à `c70f9d1`, synchronisé
- Aucun travail non committé, aucun écrasement

### 2.2 Fichier `.env` et secrets
- `.gitignore` contient `.env` (lignes 10 et 13) et `data/*.db` (ligne 34) → exclus du dépôt
- `git status` ne montre aucun `.env` suivi
- `git diff` ne contient que `app/config/settings.py` et `app/ai_providers/remote.py`
- Aucun secret, clé API, mot de passe ou token dans les fichiers modifiés
- Le `.env.local` de l'utilisateur (contenant la clé Groq) n'est **pas** suivi par Git et ne sera **jamais** committé

### 2.3 Chargement du fichier `.env` et priorité des variables
**Fichier** : `app/config/settings.py`, méthode `_load_env_file()` (lignes 113-147)
- Utilise uniquement la bibliothèque standard Python (aucun `python-dotenv`)
- Lit `MILES_ENV_FILE` ou `.env` par défaut
- Un fichier `.env` absent n'empêche pas le démarrage
- **Priorité** : les variables déjà présentes dans `os.environ` sont prioritaires et ne sont **pas** écrasées (ligne 143 : `if key not in os.environ`)
- Les guillemets environnants sont retirés
- Les erreurs de lecture sont ignorées silencieusement (dégradation gracieuse)

### 2.4 Configuration du fournisseur distant et construction de l'URL

**Fichier** : `app/ai_providers/remote.py`

| Paramètre | Source | Valeur par défaut |
|-----------|--------|-------------------|
| `base_url` | `MILES_REMOTE_BASE_URL` | `http://localhost:8000` |
| `model` | `MILES_REMOTE_MODEL` | `miles-default` |
| `api_key` | `MILES_REMOTE_API_KEY` | `None` |
| `timeout` | `MILES_REMOTE_TIMEOUT` | `30` |

**Construction de l'URL** (ligne 64) :
```python
req = urllib.request.Request(
    f"{self._base_url}/v1/chat/completions",
    ...
)
```

**Défaut identifié et corrigé** : si l'utilisateur configure `MILES_REMOTE_BASE_URL=https://api.groq.com/openai/v1` (URL standard Groq), l'URL finale devenait `https://api.groq.com/openai/v1/v1/chat/completions` (doublon de `/v1/` → erreur 404).

**Correction appliquée** : `base_url` est normalisé pour retirer un `/v1` terminal avant d'ajouter `/v1/chat/completions`. Ainsi :
- `https://api.groq.com/openai/v1` → `https://api.groq.com/openai/v1/chat/completions` ✓
- `https://api.groq.com/openai` → `https://api.groq.com/openai/v1/chat/completions` ✓
- `http://localhost:8000` → `http://localhost:8000/v1/chat/completions` ✓

### 2.5 Transmmission de la clé API

**Fichier** : `app/ai_providers/remote.py`, lignes 59-60
```python
if self._api_key:
    headers["Authorization"] = f"Bearer {self._api_key}"
```
- La clé est transmise **uniquement** dans l'en-tête `Authorization` de la requête HTTP
- Elle n'est **jamais** affichée dans les logs, exceptions, ou rapports
- Les exceptions montrent seulement le code HTTP et le corps de réponse tronqué à 200 caractères
- `Settings.as_dict()` inclut la clé mais n'est **jamais** appelée dans les logs

### 2.6 Modèle configuré et disponibilité sur Groq

**Valeur par défaut** : `miles-default` (dans `settings.py`, ligne 30) — **ce n'est pas un modèle Groq valide**.

**Modèles Groq disponibles** (à vérifier par l'utilisateur sur sa console Groq) :
- `llama-3.1-8b-instant` — rapide, économique
- `llama-3.3-70b-versatile` — plus capable, plus cher
- `mixtral-8x7b-32768` — alternative open-weight

**Recommandation** : l'utilisateur doit configurer `MILES_REMOTE_MODEL` avec un modèle Groq réel (ex. `llama-3.1-8b-instant`). La valeur par défaut `miles-default` provoquera une erreur 404/400 chez Groq.

### 2.7 Conditions tarifaires et quota Groq

**Non vérifiées directement** (pas d'accès au compte Groq de l'utilisateur). Sources à consulter par l'utilisateur :
- https://console.groq.com (tableau de bord, clés API, quotas)
- https://groq.com/pricing (tarification par modèle)

**Points d'attention** :
- Groq facture par token (entrée + sortie)
- Certains modèles ont des quotas gratuits limités
- Il revient à l'utilisateur de vérifier son solde et ses limites avant tout appel

### 2.8 Délai d'attente, erreurs HTTP et absence de réessais automatiques

**Délai d'attente** : `remote_timeout` (défaut 30 secondes, configurable via `MILES_REMOTE_TIMEOUT`)

**Gestion des erreurs** (`app/ai_providers/remote.py`, méthode `chat`) :
- `HTTPError` (4xx/5xx) → `AIProviderError` avec code et corps tronqué à 200 caractères
- `URLError` (connexion impossible) → `AIProviderError` avec message d'impossibilité de joindre
- `JSONDecodeError` (réponse invalide) → `AIProviderError`
- `Exception` générique → `AIProviderError`

**Absence de réessais automatiques** : ✓ Confirmé. Le code effectue une seule tentative par appel `chat()`. Aucun mécanisme de retry n'est présent. Cela évite de multiplier les appels facturés en cas d'erreur temporaire.

### 2.9 Tests automatisés exécutés

```
python -m unittest discover -s tests -v
```
→ **95 tests, 95 OK, 0 échec, 0 erreur** (Windows, Python 3.12.10)

Tests concernés par cette mission :
- `tests/test_provider_selection.py` : 10 tests (sélection remote/local, pas de basculement silencieux, échec fournisseur, fournisseur invalide)
- `tests/test_env_loading.py` : 5 tests (chargement .env, priorité processus, fichier absent, guillemets, pas de secret)
- `tests/test_web.py` : 16 tests (routes web, message avec/sans fournisseur, mémoire)
- Tous les tests existants préservés

## 3. Fichiers examinés et modifiés

| Fichier | Action | Raison |
|---------|--------|--------|
| `app/config/settings.py` | Modifié | Ajout de `memory_max_memories_in_context` et `memory_max_content_length` à la conversion en entier (défaut : valeur `'5'` depuis `.env` non convertie) |
| `app/ai_providers/remote.py` | Modifié | Normalisation de `base_url` pour éviter le doublon `/v1/` avec Groq |
| `tests/test_env_loading.py` | Non modifié | Déjà existant, passe |
| `tests/test_provider_selection.py` | Non modifié | Déjà existant, passe |
| `tests/test_web.py` | Non modifié | Déjà existant, passe |

## 4. Modèle Groq recommandé

| Modèle | Cas d'usage | Coût relatif | Recommandation |
|--------|------------|--------------|----------------|
| `llama-3.1-8b-instant` | Général, rapide, économique | Bas | ✅ Recommandé pour les tests initiaux |
| `llama-3.3-70b-versatile` | Tâches complexes | Élevé | À réserver aux cas avancés |
| `mixtral-8x7b-32768` | Alternative open-weight | Moyen | Optionnel |

**Aucun modèle n'a été téléchargé ni appelé.** L'utilisateur doit configurer `MILES_REMOTE_MODEL` avec le modèle de son choix.

## 5. Risques et points bloquants

| Risque | Gravité | Mitigation |
|--------|---------|------------|
| Modèle par défaut `miles-default` invalide chez Groq | Élevée | L'utilisateur doit configurer `MILES_REMOTE_MODEL` avec un modèle réel |
| Coût API non maîtrisé | Élevée | L'utilisateur doit vérifier ses quotas Groq avant tout appel |
| Doublon `/v1/` dans l'URL | Corrigée | Normalisation appliquée dans `remote.py` |
| Clé API exposée | Non | Transmise uniquement dans `Authorization`, jamais journalisée |

## 6. Procédure préparée pour le test d'inférence réel (NON EXÉCUTÉE)

1. L'utilisateur configure dans son `.env` (local, non committé) :
   ```
   MILES_PROVIDER=remote
   MILES_REMOTE_BASE_URL=https://api.groq.com/openai/v1
   MILES_REMOTE_MODEL=llama-3.1-8b-instant
   MILES_REMOTE_API_KEY=<sa_clé_groq>
   MILES_REMOTE_TIMEOUT=30
   ```
2. L'utilisateur lance `python miles.py` (ou `py miles.py` sur Windows)
3. L'utilisateur envoie un message via le terminal ou l'interface web (`http://127.0.0.1:8080`)
4. MILES appelle Groq et affiche la réponse

## 7. Demande d'autorisation

**Aucun appel API réel n'a été effectué.** Avant que je puisse lancer un test d'inférence réel via Groq, j'ai besoin de votre autorisation explicite sur :

1. **Le modèle à utiliser** : quel modèle Groq souhaitez-vous tester ? (ex. `llama-3.1-8b-instant`)
2. **Le coût potentiel** : êtes-vous conscient que les appels Groq sont facturés par token et avez-vous vérifié vos quotas sur https://console.groq.com ?
3. **L'URL du fournisseur** : confirmez-vous utiliser `https://api.groq.com/openai/v1` (ou une autre URL Groq) ?

**Attendez mon autorisation explicite avant tout appel API réel.** Aucun appel réseau susceptible d'être facturé n'a été effectué à ce jour.

---

*Aucun commit ni push n'a été effectué pour ces corrections. Les modifications locales (remote.py, settings.py) attendent votre décision.*
