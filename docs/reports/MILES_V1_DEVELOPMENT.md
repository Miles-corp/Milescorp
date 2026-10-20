# docs/reports/MILES_V1_DEVELOPMENT.md — Rapport de développement MILES V1 (Agent A)

## 1. Contexte et point de départ

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp` (branche `main`) |
| Commit de départ (base de la branche V1) | `e0886a7` (branche `origin/fix/agent-b-s002-s004-s005-s006` d'Agent B) |
| Branche de développement | `feature/miles-v1-conversation-persistence` |
| `origin/main` au moment du développement | `b5e1007` |
| Python utilisé | 3.12.10 (Windows) |

**Point de départ important** : Agent B avait déjà implémenté les correctifs de sécurité S-002, S-004, S-005, S-006 dans `origin/fix/agent-b-s002-s004-s005-s006`. La branche V1 en part, ce qui intègre automatiquement L-007 à L-010, S-001 à S-003 et la configuration mémoire.

## 2. Objectif fonctionnel atteint

Le scénario V1 complet est opérationnel et vérifié de bout en bout avec un fournisseur simulé local (coût nul) :

| Étape | État | Preuve |
|-------|-------|--------|
| 1. Lancement depuis le terminal | ✅ | `python miles.py` → écran d'accueil, code de sortie 0 |
| 2. Chargement et validation de la configuration | ✅ | `Settings` + `.env` + JSON, erreurs explicites |
| 3. Sélection du fournisseur et du modèle | ✅ | `MILES_PROVIDER`, `MILES_REMOTE_BASE_URL`, `MILES_REMOTE_MODEL` |
| 4. Saisie d'un message | ✅ | invite `> ` |
| 5. Envoi au fournisseur | ✅ | requête HTTP reçue par le serveur simulé |
| 6. Affichage de la réponse réelle | ✅ | réponse affichée dans le terminal |
| 7. Conservation du contexte de conversation | ✅ | contexte transmis entre 2 sessions : `['user', 'assistant', 'user']` |
| 8. Enregistrement de la conversation | ✅ | base `data/conversations.db` créée (32 Ko) |
| 9. Fermeture propre puis redémarrage | ✅ | code de sortie 0, EOF et Ctrl+C gérés avec message |
| 10. Restauration de la conversation | ✅ | « Conversation restaurée : 6 message(s). » |

## 3. Architecture retenue

```
app/
  memory/transcript.py     # NOUVEAU : persistance SQLite des transcriptions
  core/conversation.py     # étendu : liaison optionnelle à un transcripteur
  interface/cli.py         # étendu : /conversations, /new, message de restauration
  interface/web.py         # refactoré : rédaction partagée (app/utilities/redaction.py)
  config/settings.py       # étendu : options conversation_persist / conversation_db_path
  utilities/redaction.py    # NOUVEAU : source unique de détection des secrets
miles.py                   # options --conversation, --new-conversation,
                           #   --list-conversations, --no-persist
```

**Choix techniques et raisons :**

| Choix | Raison |
|-------|--------|
| SQLite (stdlib `sqlite3`) pour les transcriptions | Aucun dépôt à installer, transactions ACID, schéma versionné, cohérent avec la mémoire persistante existante |
| Module `app/memory/transcript.py` distinct de `persistent.py` | La « mémoire de souvenirs » (explicitement demandés par l'utilisateur) et l'« historique de conversation » sont deux notions différentes ; la mission V1 demande explicitement de ne pas les confondre avec une mémoire RAG |
| Clé `UNIQUE (conversation_id, sequence)` + `MAX(sequence)+1` sous `BEGIN IMMEDIATE` | Ordre garanti, aucun doublon possible, écriture concurrente sûre |
| `app/utilities/redaction.py` comme source unique | `web.py` et `transcript.py` appliquent les mêmes motifs ; une seule source à corriger |
| Lecture du `.env` dans un dictionnaire local (plus de mutation de `os.environ`) | Supprime un effet de bord global : la suite de tests devient hermétique et une valeur lue deux fois ne peut plus diverger |
| Précedence processus > `.env` > JSON > défauts | Le comportement existant est conservé à l'identique, mais devient explicite et documenté |
| API `Conversation` inchangée sans transcripteur | Rétrocompatibilité totale : les 228 tests existants n'ont pas été modifiés dans leur logique |

## 4. Fichiers créés ou modifiés

### Créés (3)
| Fichier | Rôle |
|---------|------|
| `app/memory/transcript.py` | Persistance SQLite des conversations (271 lignes) |
| `app/utilities/redaction.py` | Source unique de détection/redaction des secrets (58 lignes) |
| `tests/test_conversation_persistence.py` | 48 tests V1 (catégories A à E) |

### Modifiés (10)
| Fichier | Modification |
|---------|--------------|
| `app/core/conversation.py` | `attach_transcript()`, `restore()`, `new_conversation()`, `is_persistent`, persistance automatique des messages |
| `app/config/settings.py` | Options `conversation_persist` / `conversation_db_path` ; `.env` lu sans muter `os.environ` ; booléens normalisés |
| `miles.py` | Branchement du transcripteur, 4 nouvelles options CLI, restauration automatique |
| `app/interface/cli.py` | Commandes `/conversations` et `/new`, message de restauration, EOF/Ctrl+C explicites |
| `app/interface/web.py` | Utilisation de la rédaction partagée (suppression des motifs dupliqués) |
| `app/memory/__init__.py` | Exports `ConversationTranscript`, `TranscriptError` |
| `tests/__init__.py` | Herméticité de la suite (redirection de `MILES_ENV_FILE`) |
| `tests/test_settings_memory_config.py` | Isolation de `MILES_ENV_FILE` (les tests ne dépendent plus du `.env` local) |
| `tests/test_web_security.py` | Tolérance au reset TCP sur refus de requête (voir §7) |
| `docs/installation/INSTALL.md` | Section « 3bis » (persistance V1) + nouvelles commandes |
| `docs/installation/QUICKSTART.md` | Section 6.8 bis (persistance de conversation V1) |

## 5. Tests exécutés — résultats réels

### Suite complète
```
$ python -m unittest discover -s tests
Ran 276 tests in 35.065s
OK (skipped=4)
```

| Mesure | Avant V1 (base `e0886a7`) | Après V1 |
|--------|---------------------------|----------|
| Tests découverts | 228 | **276** |
| Réussis | 228 | **276** |
| Échecs / erreurs | 0 | **0** |
| Ignorés | 4 | 4 |

Les 4 tests ignorés sont les tests de voix nécessitant `pyttsx3` et `speech_recognition` (non installés).

### Stabilité (fiabilité de la suite)
| Mesure | Avant | Après |
|---------|-------|-------|
| `tests.test_web_security` sur 15 exécutions | 3 échecs (20 %) | **0 échec** |
| Suite complète sur 5 exécutions | — | **0 échec** |

### Test de bout en bout (fournisseur simulé local, coût nul)
Voir §2 : les 10 étapes du scénario V1 sont validées, y compris la persistance inter-sessions.

## 6. Traitement des constats de la revue

| Constat | Évaluation | Traitement |
|---------|-----------|------------|
| S-002 (web sans authentification) | Corrigé par Agent B | Intégré via la base de la branche V1 |
| S-004 (Content-Length non borné) | Corrigé par Agent B | Intégré ; invariant « le corps n'est jamais lu au-delà de la limite » **préservé** |
| S-005 (traversée par symlink) | Corrigé par Agent B (`app/security/paths.py`) | Intégré et **utilisé** pour la base de conversations : le chemin est confiné aux racines autorisées |
| S-006 (`Queue` non fermée) | Corrigé par Agent B | Intégré |
| Instabilité de `test_web_security` | **Défaut confirmé par Agent A** (3/15 échecs) | Corrigé (§7) |
| Non-herméneutéité de la suite | **Défaut confirmé par Agent A** (le `.env` local faisait échouer 4 tests d'Agent B) | Corrigé (§7) |
| Effet de bord global de `_load_env_file` | **Défaut confirmé par Agent A** | Corrigé : lecture dans un dictionnaire local |

## 7. Défauts trouvés et corrigés par Agent A

### D-A1 — Instabilité de la suite de tests (20 % d'échecs)

**Constat** : `tests/test_web_security.py` échouait 3 fois sur 15. Cause : le serveur refuse une requête trop volumineuse **sans lire son corps** (invariant de sécurité correct d'Agent B), puis ferme la connexion ; le client, encore en train d'écrire, observe une réinitialisation TCP au lieu du 413.

**Correction** : le helper `_raw_post` capte désormais `http.client.HTTPException` et `OSError` et renvoie un statut 0 ; une assertion `_assert_refused` accepte le statut attendu **ou** une réinitialisation de connexion. L'assertion de sécurité stricte (`test_lecture_bornee_a_la_limite` : le handler ne lit jamais plus de `MAX_BODY_BYTES`) est **inchangée**.

> Une première tentative de correction côté serveur (drain borné du corps) a été **abandonnée** : elle violait l'invariant de sécurité d'Agent B. Elle a été intégralement ré reverted.

### D-A2 — La suite de tests dépendait du `.env` local du développeur

**Constat** : 4 tests d'Agent B échouaient dans le répertoire de développement (`.env` local présent) alors qu'ils passaient dans un worktree propre. `mock.patch.dict(os.environ, ...)` n'isole pas `MILES_ENV_FILE`.

**Correction** : `tests/__init__.py` redirige `MILES_ENV_FILE` vers un chemin inexistant pour toute la session (sauf si le développeur le définit explicitement) ; les helpers de `test_settings_memory_config.py` isolent également `MILES_ENV_FILE`.

### D-A3 — Effet de bord global de `_load_env_file`

**Constat** : `Settings._load_env_file()` injectait les variables du `.env` dans `os.environ`, ce qui polluait le processus entier et pouvait faire diverger deux instances de `Settings`.

**Correction** : le `.env` est lu dans un dictionnaire local ; l'environnement du processus n'est plus modifié. La précédence (processus > `.env` > JSON > défauts) est conservée à l'identique et désormais documentée.

## 8. Test d'inférence réel — procédure préparée, NON EXÉCUTÉE

| Élément | Valeur |
|---------|--------|
| Fournisseur | `RemoteProvider` (existant, inchangé) |
| Endpoint | `MILES_REMOTE_BASE_URL` — pour Groq : `https://api.groq.com/openai` |
| Modèle | `MILES_REMOTE_MODEL` — pour Groq, un modèle réel de la console Groq (ex. `llama-3.1-8b-instant`) |
| Clé API | `MILES_REMOTE_API_KEY` — lue depuis `.env` (jamais affichée, jamais journalisée) |
| Timeout | `MILES_REMOTE_TIMEOUT` (défaut 30 s) |
| Requête | `POST /v1/chat/completions`, corps `{"model": ..., "messages": [...], "temperature": 0.7, "stream": false}` |
| Résultat attendu | HTTP 200, `choices[0].message.content` non vide, réponse affichée dans le terminal, message persisté |

**Commande de test (non exécutée) :**
```bash
python miles.py
# puis : Bonjour, qui es-tu ?
```

**Coût / quota** : à vérifier par l'utilisateur sur sa console Groq (https://console.groq.com) — le tarif dépend du modèle retenu et du quota du compte. **Aucun appel n'a été effectué.**

**Précautions** :
- la clé reste dans `.env` (ignoré par Git) et n'apparaît dans aucun journal ni rapport ;
- `sanitize_text()` expurge toute clé d'un message avant écriture dans l'historique ;
- aucun réessai automatique n'est implémenté : un appel = un appel facturé.

## 9. Fournisseur local hors ligne — proposition technique (sans installation)

Contrainte matérielle : **RTX 3050, 4 Go de VRAM** (CUDA 13.4, pilote 617.42).

| Élément | Proposition |
|---------|-------------|
| Moteur | **llama.cpp** — exécutable standalone, serveur HTTP compatible OpenAI-like (donc réutilisable tel quel par `LocalProvider`), CPU et/ou GPU, multi-plateforme Windows/Linux |
| Alternative | `llama-cpp-python` (binding Python) si l'on veut éviter un processus séparé ; même moteur |
| Modèle | **Llama-3.2-1B-Instruct** en quantification 4 bits (Q4_K_M) — ~0,7 à 1 Go |
| Alternative | Phi-3-mini-4k-instruct 4 bits — ~2,0 à 2,2 Go |
| VRAM requise | ~1 Go (Llama-3.2-1B 4 bits) à ~2,5 Go (Phi-3-mini 4 bits) : **tient dans les 4 Go** |
| Performance attendue | ~30-60 tokens/s sur RTX 3050 pour un modèle 1B 4 bits ; latency faible, qualité conversationnelle correcte |
| Hors ligne | Oui, après téléchargement unique du modèle ; aucune requête réseau ensuite |
| Dépendances | Aucune si binaire pré-compilé (Windows/Linux) ; `cmake` + toolchain CUDA uniquement pour compiler |

**Recommandation** : `llama.cpp` en serveur HTTP + `Llama-3.2-1B-Instruct` Q4_K_M. L'endpoint produit est déjà compatible avec l'implémentation `LocalProvider` existante : **aucune modification de `app/ai_providers/local.py` n'est nécessaire**.

**Aucun téléchargement ni installation n'a été effectué.** L'accord explicite de l'utilisateur est requis (taille ~0,7 Go pour le modèle, ~10 Mo pour le binaire).

## 10. Limites et risques résiduels

| Limite | Gravité | Statut |
|--------|---------|--------|
| Validation Debian 13 non effectuée | Moyenne | Responsabilité Agent B (VM disponible) |
| Test d'inférence réel non effectué | Moyenne | En attente d'accord (coût API) |
| Fournisseur local non implémenté | Moyenne | TASK-DEV-007 |
| Mode hors ligne non testé | Moyenne | Dépend de l'installation du moteur local |
| S-002 : pas d'authentification web | Moyenne | Corrigé par Agent B (serveur strictement local) |
| Le 413 peut être perdu si le client écrit encore son corps | Faible | Comportement assumé (invariant de sécurité préservé) ; documenté |
| En-tête `Server: BaseHTTP/0.6 Python/3.12.10` | Faible | Pré-existant, non corrigé |
| Mémoire persistante de souvenirs ≠ historique de conversation | — | Séparés par conception (mémoire RAG hors périmètre) |

## 11. Commandes de reproduction

```bash
# Suite complète
python -m unittest discover -s tests -v

# Scénario V1 complet (fournisseur simulé, coût nul)
# voir docs/reports/MILES_V1_DEVELOPMENT.md §2

# Lancement
python miles.py
python miles.py --list-conversations
python miles.py --new-conversation
python miles.py --no-persist
```

## 12. Références de commits et branches

| Référence | Contenu |
|-----------|---------|
| `e0886a7` | Base : correctifs S-002, S-004, S-005, S-006 (Agent B) |
| `feature/miles-v1-conversation-persistence` | Branche de développement V1 (Agent A) |
| `b5e1007` | `origin/main` au moment du développement (inchangé) |
| `origin/fix/agent-b-s002-s004-s005-s006` | Branche d'Agent B, base de la V1 |

## 13. Demande de vérification à Agent B

Agent B est invité à vérifier indépendamment :
1. la suite complète (276 tests) sur **Debian 13** ;
2. le scénario V1 de bout en bout (persistance, redémarrage, restauration) ;
3. les deux corrections apportées aux tests d'Agent B (herméneuticité, tolérance au reset TCP) — vérifier qu'aucune assertion de sécurité n'a été affaiblie ;
4. l'absence de secret dans l'historique de conversation et dans les journaux ;
5. la conformité de `app/memory/transcript.py` (schéma, ordonnancement, absence de doublons) ;
6. la régression de `app/config/settings.py` (précédence processus > `.env` > JSON > défauts).

---

*Aucun appel API réel, aucun téléchargement de modèle, aucune dépense. Aucun commit ni push n'a été effectué dans le cadre de la rédaction de ce rapport.*
