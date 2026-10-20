# docs/reports/PHASE_4_R3_R6_AGENT_A.md — Documentation R3 et erreurs fournisseur R6 (Agent A)

Traitement des messages **M-006** (R3 — documentation `INSTALL.md`) et **M-007** (R6 — erreurs du fournisseur), reçus d'Agent B via la branche `origin/audit/agent-b-v1-review`.

## 1. Synchronisation préalable

| Contrôle | Résultat |
|----------|----------|
| Dépôt | `Miles-corp/Milescorp` (le dépôt attendu) |
| Branche active | `feature/miles-v1-conversation-persistence` |
| `git fetch origin` | Nouvelle branche distante détectée : `origin/audit/agent-b-v1-review` (`fa5384f..e98c320`) |
| Synchronisation branche de travail | `7dacdfe` = `origin/feature/miles-v1-conversation-persistence` — **aucune divergence** |
| Modifications locales | Uniquement l'artefact parasite `tatus --short --branch` (préservé, non committé) |
| `origin/main` | `b5e1007` — **inchangé** |

## 2. Mission R3 — documentation de `INSTALL.md`

### 2.1 Vérification préalable de chaque affirmation d'Agent B

Le message M-006 fournit un texte de référence. **Chaque affirmation a été revérifiée contre le code réel** avant d'être reprise.

| Affirmation d'Agent B | Vérification | Verdict |
|---|---|---|
| « 18 variables `MILES_*` explicitement mappées » | `env_mapping` contient **17** entrées ; le code lit en outre `MILES_ENV_FILE` et `MILES_CONFIG` (chemins de fichiers) → **19 variables MILES_* lues au total** | ⚠️ **Divergence corrigée** : la documentation indique 17 + 2 = 19, avec le détail |
| Priorité : processus > `.env` > JSON > défauts | `settings.py` : `dotenv_values` lu séparément, `os.environ.get(env_name)` prioritaire, JSON appliqué avant la boucle env | ✅ Conforme |
| `.env` : `MILES_ENV_FILE`, défaut `.env` | `settings.py` : `Path(os.environ.get("MILES_ENV_FILE", ".env"))` | ✅ Conforme |
| JSON : `--config`, sinon `MILES_CONFIG`, sinon `config/config.json` | `miles.py` passe `--config` ; `settings.py` : `config_path or os.environ.get("MILES_CONFIG", "config/config.json")` | ✅ Conforme |
| Variables non mappées ignorées, non injectées | Vérifié par exécution : `HTTP_PROXY` du `.env` **absent** de `os.environ` | ✅ Conforme |
| Proxy : à définir dans l'environnement du processus | `urllib.request.getproxies()` lit bien l'environnement : `{'http': 'http://proxy.exemple:3128'}` | ✅ Conforme |
| Priorité de configuration inchangée | **Non modifiée** | ✅ |

### 2.2 Section ajoutée

`docs/installation/INSTALL.md` — nouvelle section **« 3ter. Sources de configuration et variables reconnues »** :

1. Les quatre sources de configuration et leur **ordre de priorité réel** ;
2. Le tableau des variables reconnues, avec le nombre par catégorie (7 fournisseur, 2 secrets, 1 contexte, 1 voix, 4 mémoire, 2 conversation, 2 chemins) ;
3. Le traitement des variables **non reconnues** (ignorées, non injectées) ;
4. La procédure de **proxy HTTP/HTTPS** (Linux et Windows), avec la raison technique (`urllib` lit l'environnement du processus) ;
5. Les **limites** de la prise en charge des variables d'environnement (19 variables, secrets jamais journalisés, valeurs booléennes strictes).

### 2.3 Tests anti-dérive documentaire

`tests/test_docs_configuration.py` (11 tests) — garantissent que la documentation reste alignée sur le code :

- nombre réel de variables reconnues (19) et de variables de mapping (17) ;
- **toute** variable `MILES_*` mentionnée dans `INSTALL.md` est reconnue par le code ;
- **toute** variable reconnue par le code est documentée ;
- les sources de configuration et l'ordre de priorité sont mentionnés ;
- priorité réelle vérifiée par exécution : processus > `.env` > JSON > défauts ;
- une variable non mappée est ignorée et non injectée ;
- le proxy défini dans l'environnement du processus est bien pris en compte par `urllib`.

Ces tests ont d'abord **échoué** (5 variables non documentées, section absente) : ils ont donc détecté la lacune avant correction.

## 3. Mission R6 — erreurs du fournisseur

### 3.1 Diagnostic

`app/interface/cli.py` affichait `f"\nErreur du fournisseur IA : {exc}"`. Or le message d'une `AIProviderError` contient, dans `app/ai_providers/remote.py`, le **corps de la réponse HTTP du fournisseur tronqué à 200 caractères**. Ce corps peut contenir une clé d'API, un jeton, un identifiant de compte ou une URL interne : il était donc exposé au terminal.

L'interface web était déjà protégée (`public_provider_error()`), mais le terminal ne l'était pas : les deux interfaces divergeaient.

### 3.2 Correction

- **Nouveau** `app/ai_providers/public_errors.py` : source unique de la classification publique.
  - `public_provider_error(exc)` → message public, sans détail technique, selon 7 situations (authentification, quota, ressource introuvable, délai, réponse invalide, fournisseur indisponible, échec de communication). Le code HTTP n'est **pas** révélé.
  - `technical_detail(exc)` → diagnostic technique **expurgé** de tout secret (`type(exc).__name__` + message passé par `sanitize_text`), destiné aux journaux locaux uniquement.
- `app/interface/cli.py` : le terminal affiche désormais le **message public** et journalise le **détail technique** dans le logger `miles.cli` (avec `NullHandler` : rien n'est écrit par défaut). L'erreur interne générique remplace également l'exception brute.
- `app/interface/web.py` : sa copie locale de `public_provider_error` est remplacée par un ré-export du module partagé → **les deux interfaces exposent exactement le même message**.

### 3.3 Comportements préservés

| Élément | État |
|---------|-------|
| Code de sortie du programme | inchangé (0) |
| Conservation de la session après erreur | inchangé (le message utilisateur reste dans l'historique) |
| Contrat de `AIProviderError` | inchangé (aucun attribut ajouté) |
| Autres commandes du CLI | inchangées |
| Réponse de l'interface web | message public identique (aucune fuite) |

### 3.4 Tests ciblés

`tests/test_provider_errors.py` (15 tests) :

- classification : 401/403 → authentification, 429 → quota, 404 → introuvable, délai, réponse invalide, fournisseur indisponible, cas générique ;
- le code HTTP n'apparaît **pas** dans le message public ;
- aucun secret dans le message public ;
- le détail technique conserve le diagnostic (type + code) mais expurge les secrets ;
- le terminal n'affiche ni secret ni code HTTP ;
- la session est conservée après erreur fournisseur ;
- l'erreur interne ne divulgue pas de détail ;
- le journal contient le diagnostic expurgé et **pas** de secret ;
- le web et le CLI exposent le même message.

## 4. Fichiers modifiés

| Fichier | Action |
|---------|--------|
| `app/ai_providers/public_errors.py` | **Créé** — classification publique + diagnostic technique expurgé |
| `app/interface/cli.py` | Modifié — message public à l'écran, détail technique journalisé, logger `miles.cli` |
| `app/interface/web.py` | Modifié — ré-export de la classification partagée (suppression de la copie locale) |
| `docs/installation/INSTALL.md` | Modifié — section « 3ter » (R3) |
| `docs/coordination/TASKS.md` | Modifié — TASK-DEV-011 ajoutée |
| `docs/coordination/STATUS.md` | Modifié — TASK-DEV-011 ajoutée |
| `tests/test_docs_configuration.py` | **Créé** — 11 tests anti-dérive documentaire + priorité + proxy |
| `tests/test_provider_errors.py` | **Créé** — 15 tests R6 |
| `docs/reports/PHASE_4_R3_R6_AGENT_A.md` | **Créé** — ce rapport |

## 5. Tests exécutés — résultats réels

```
$ python -m unittest discover -s tests
Ran 328 tests in 38.611s
OK (skipped=4)
```

| Mesure | Avant | Après |
|--------|-------|-------|
| Tests découverts | 302 | **328** |
| Réussis | 302 | **328** |
| Échecs / erreurs | 0 | **0** |
| Ignorés (voix, 4) | 4 | 4 |
| Instabilité (3 exécutions de la suite complète) | — | **0 échec** |

Les 4 tests ignorés sont les tests de voix nécessitant `pyttsx3` et `speech_recognition` (non installés).

## 6. Limites de validation

| Limite | Gravité | Statut |
|--------|---------|--------|
| Validation Debian 13 non effectuée par Agent A | Moyenne | Agent B l'a déjà réalisée pour la révision précédente (302 tests, 0 ignoré) ; **à rejouer** pour ce lot |
| Les 4 tests ignorés (voix) ne sont pas exécutés | Faible | Dépendances vocales non installées, sans rapport avec R3/R6 |
| Test d'inférence réel Groq | Moyenne | En attente d'accord (coût API) |
| Fournisseur local hors ligne | Moyenne | TASK-DEV-007 |

## 7. Points restant à vérifier par Agent B

1. Rejouer la suite complète (**328 tests**) sur Debian 13, dont les 4 ignorés.
2. Vérifier que la section « 3ter » de `INSTALL.md` reste alignée sur le code après toute
   modification de `app/config/settings.py` (les tests `test_docs_configuration.py`
   échoueront automatiquement en cas de dérive).
3. Vérifier R6 : le terminal ne doit plus afficher de code HTTP ni de corps de
   réponse du fournisseur ; le diagnostic doit rester dans les journaux locaux.
4. Vérifier que l'interface web et le terminal exposent le **même** message public.
5. Confirmer que la priorité de configuration (processus > `.env` > JSON > défauts)
   est inchangée par la documentation.
6. Confirmer que la procédure proxy documentée fonctionne sur Debian 13
   (`export HTTP_PROXY=...`).

---

*Aucun appel API réel, aucun téléchargement de modèle, aucune installation.
`main` n'est pas modifié. La branche `audit/agent-b-v1-review` d'Agent B n'a pas
été touchée.*
