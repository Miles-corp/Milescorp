# docs/reports/PHASE_4_REVIEW_FIXES_AGENT_A.md — Revue indépendante des corrections S-001 / S-003 et de la configuration mémoire (Agent A)

## Verdict

> ## ⚠️ APPROUVÉ AVEC RÉSERVES
>
> Les trois défauts sont **réellement corrigés**, avec des tests de régression **efficaces** (validés par test de mutation). La branche est propre, sans secret publié, et n'affecte ni `main` ni les correctifs L-007 à L-010.
>
> **Réserves** : (1) incident de publication à regulariser, (2) validation Debian 13 non effectuée, (3) deux risques résiduels mineurs dans `web.py`, (4) les constats S-002, S-004, S-005, S-006 restent ouverts et hors périmètre.

---

## 1. Section A — Vérification Git et incident de publication

### 1.1 Identité de la branche et des commits

| Élément | Annoncé | Vérifié | Statut |
|---------|---------|---------|--------|
| Branche | `fix/agent-b-s001-s003-memory-config` | `origin/fix/agent-b-s001-s003-memory-config` | ✅ |
| Base | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` | parent de `064f907` | ✅ |
| `064f907` — corrections de production | ✔ | `app/config/settings.py`, `app/interface/web.py`, `miles.py` | ✅ |
| `8b0e9dc` — tests point d'entrée | ✔ | `tests/test_miles_entrypoint.py` (112 l.) | ✅ |
| `bdee0f6` — tests sécurité web | ✔ | `tests/test_web_security.py` (270 l.) | ✅ |
| `97bbd90` — tests configuration mémoire | ✔ | `tests/test_settings_memory_config.py` (158 l.) | ✅ |
| `f53cffc` — rapport local | ✔ | `docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md` (301 l.) | ✅ |

### 1.2 Chaînage des parents (chaque commit)

```
064f907  parent: 4b6f515   (correctifs L-007 à L-010)
8b0e9dc  parent: 064f907
bdee0f6  parent: 8b0e9dc
97bbd90  parent: bdee0f6
f53cffc  parent: 97bbd90
```

**Chaînage linéaire et sansInterpolation** ✅. `git merge-base --is-ancestor 4b6f515 origin/fix/...` → **vrai** : la branche est bien issue de la base annoncée.

### 1.3 Diff réel par rapport à `4b6f515`

```
M  app/config/settings.py                                |  47 ++++
M  app/interface/web.py                                  | 104 ++++++-
M  miles.py                                              |   2 +-
A  docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md | 301 ++++
A  tests/test_miles_entrypoint.py                        | 112 +++
A  tests/test_settings_memory_config.py                  | 158 +++
A  tests/test_web_security.py                            | 270 +++
7 files changed, 988 insertions(+), 6 deletions(-)
```

**Aucun fichier hors périmètre.** Ni `app/tools/*` (correctifs L-007 à L-010), ni `tests/test_tool*`, ni `app/memory/persistent.py`, ni `app/security/validator.py` n'ont été touchés.

### 1.4 Vérification que L-007 à L-010 sont intacts

| Contrôle | Résultat |
|----------|----------|
| `git diff 4b6f515 origin/fix/... -- app/tools/` | **vide** ✅ |
| `git diff 4b6f515 origin/fix/... -- tests/test_tool_engine.py` | **vide** ✅ |
| `multiprocessing.Process` + `terminate()` + `kill()` | ✅ présent |
| 3 validations de politique avant exécution | ✅ présentes |
| `expires_at` + horloge injectable | ✅ présent |
| Messages d'audit génériques | ✅ présents |

### 1.5 État du dépôt et des autres branches

| Élément | État | Intact ? |
|---------|------|----------|
| Branche active | `work/agent-a-phase4-audit` | — |
| HEAD local | `632f27b` | ✅ |
| `origin/main` | `b5e1007` | ✅ **inchangée** |
| `origin/review/phase4-security-fixes` | `4b6f515` | ✅ |
| `origin/review/agent-b-phase4-review` | `928410c` | ✅ |
| `origin/work/agent-a-phase4-audit` | `632f27b` | ✅ |

### 1.6 Incident de publication — constat factuel

| Élément | Constat |
|---------|---------|
| Auteur des 5 commits | `iopjklad-pixel <iopjklad@gmail.com>` (identité Git d'Agent B) |
| Fenêtre de publication | 20:01:12 → 20:03:40, 19/10/2026 (≈ 2 min 28 s) |
| Branche locale `fix/agent-b-s001-s003-memory-config` | **inexistante** (0 référence locale) |
| Référence distante | `.git/refs/remotes/origin/fix/agent-b-s001-s003-memory-config` → `f53cffc` |
| `origin/main` | **non touchée** |
| Autres branches d'agents | **non touchées** |
| Contenu publié | conforme au périmètre annoncé, **aucun secret** |

**Analyse de l'écart de procédure.** L'écart constaté est le suivant : cinq commits ont été publiés sur `origin` sans autorisation distincte, et la branche locale correspondante a été supprimée (ou le push a été effectué depuis un autre clone), ne laissant qu'une référence distante. Le contenu publié est **de bonne qualité et conforme**, et l'historique de `main` n'est pas affecté : l'incident est donc **procédural et sans impact sur le code**, mais doit être régularisé par le propriétaire du projet (décision de conservation, de renommage ou de suppression de la branche distante — **hors périmètre de cette revue, aucune action de suppression n'a été effectuée**).

**Point de cohérence** : le rapport d'Agent B reconnaît explicitement que les commits `ccb512d` / `8e82d45` et la branche `fix/agent-b-s001-s003` annoncés lors de la mission précédente « n'ont jamais été publiés : ils étaient uniquement locaux », ce qui **confirme** le constat de la revue précédente (aucun artefact trouvé dans le dépôt) et explique la réimplémentation depuis `4b6f515`. Cette explication est cohérente avec l'état Git observé.

### 1.7 Recherche de secrets dans les fichiers publiés

| Fichier | Résultat |
|---------|----------|
| `app/config/settings.py` | Aucun secret réel |
| `app/interface/web.py` | Aucun secret réel |
| `miles.py` | Aucun secret réel |
| `tests/test_miles_entrypoint.py` | Aucun secret réel (valeurs fictives uniquement) |
| `tests/test_settings_memory_config.py` | Aucun secret réel |
| `tests/test_web_security.py` | Aucun secret réel (`sk-FAUSSE-CLE-XYZ`, `FAUX-JETON-BEARER-0123456789`, `motdepasse-faux-0123456789` → valeurs de test explicitement fictives) |

---

## 2. Section B — Vérification S-001

### 2.1 Import corrigé

```diff
-from app.memory.persistent import PersistentMemory
+from app.memory.persistent import PersistentMemory, PersistentMemoryError
```

L'import provient bien du **module de définition** (`app/memory/persistent.py`, où la classe est définie ligne 23), et non d'un ré-export. La convention existante de `app/interface/cli.py` (ligne 14) est respectée. ✅

### 2.2 Traitement d'erreur mémoire fonctionnel

La référence à `PersistentMemoryError` n'a pas été supprimée : la clause `except` de `miles.py` est devenue résolvable et le traitement reste en place. `miles.py` continue d'attraper l'erreur et d'afficher un avertissement sur `stderr` sans interrompre le programme. ✅

### 2.3 Le test de régression détecte-t-il le défaut initial ? — **OUI, prouvé par mutation**

| Expérience | Résultat |
|------------|----------|
| Code corrigé (branche) | 4 tests, `OK` |
| **Mutation** : retrait de `PersistentMemoryError` de l'import (défaut d'origine) | **2 tests en ERROR** avec `NameError: name 'PersistentMemoryError' is not defined. Did you mean: 'PersistentMemory'?` |

Le test `test_name_error_absent_quand_memoire_echoue` et `test_name_error_absent_avec_base_inaccessible` **détectent bien** le défaut initial. ✅

---

## 3. Section C — Audit S-003

### 3.1 Réponses HTTP de tous les gestionnaires d'erreurs modifiés

| Bloc `except` | Emplacement | Réponse publique | Journal interne |
|---------------|-------------|------------------|-----------------|
| `except AIProviderError` | `web.py` (send_message) | `public_provider_error(exc)` → message ** générique** parmi 3 | `logger.error(... sanitize_text(exc))` |
| `except Exception` | `web.py` (send_message) | `"Erreur interne du service."` | `logger.error("... (%s) : %s", type(exc).__name__, sanitize_text(exc))` |
| `except PersistentMemoryError` | `web.py` (add_memory) | `str(exc)` — texte **fixe produit par MILES** | `logger.error(... sanitize_text(exc))` |
| `except Exception` | `web.py` (add_memory) | `"Erreur interne du service."` | `logger.error("... (%s) : %s", type(exc).__name__, sanitize_text(exc))` |
| `except PersistentMemoryError` | `web.py` (delete_memory) | `str(exc)` — texte **fixe produit par MILES** | `logger.error(... sanitize_text(exc))` |
| `except Exception` | `web.py` (delete_memory) | `"Erreur interne du service."` | `logger.error("... (%s) : %s", type(exc).__name__, sanitize_text(exc))` |

**Vérification exhaustive** : `str(exc)` / `{exc}` absents de **tous** les handlers de `web.py` :
```
_handle_status        -> False
_handle_list_memories -> False
_handle_message       -> False
_handle_remember      -> False
_handle_forget        -> False
do_GET / do_POST      -> False
```
✅

### 3.2 `sanitize_text()` et motifs de détection

Fonction présente et exportée. 4 motifs :

| # | Motif | Couverture |
|---|-------|-----------|
| 1 | `sk-[A-Za-z0-9_\-]{4,}` | Clés de fournisseur IA |
| 2 | `(?i)\b(?:bearer\|basic)\s+[A-Za-z0-9._\-]{4,}` | Jetons d'authentification |
| 3 | `(?i)\b(?:api[_-]?key\|apikey\|token\|secret\|password\|...)\b\s*[:=]\s*...` | Paires clé=valeur |
| 4 | `(?i)\b(?:password\|passwd\|pwd\|secret\|token\|api[_-]?key)\b\s*[:=]\s*...` | Valeurs isolées |

Replacement par le marqueur `[REDACTED]`. ✅

### 3.3 Messages publics et codes HTTP

| Cas | Code HTTP | Corps de la réponse |
|-----|-----------|---------------------|
| Erreur fournisseur | 400 | `{"error": "Erreur du fournisseur IA : échec de la communication avec le fournisseur.", "provider": "remote", "context_preserved": true}` |
| Erreur inattendue | 400 | `{"error": "Erreur interne du service.", ...}` |
| Message vide | 400 | `{"error": "Message vide ou invalide."}` |
| ID invalide | 400 | `{"error": "Identifiant invalide."}` |
| Route inconnue | 404 | `{"error": "Not found", "path": "..."}` |

**Le `provider` est conservé** dans la réponse (information non sensible, utile au client). La conversation est préservée (`context_preserved: true`). ✅

### 3.4 Risques de fuite — analyse des vecteurs

| Vecteur | Analyse | Statut |
|---------|---------|--------|
| **Exception imbriquée** | `except Exception` capture l'exception finale ; `str(exc)` n'est plus jamais renvoyé au client. Le message original de la cause racine (qui peut porter un secret) n'est plus exposé. Le journal conserve `type(exc).__name__` + message assaini. | ✅ **Corrigé** |
| **En-têtes HTTP** | Aucune réponse ne reflète d'exception. Seuls `Content-Type` et `Content-Length` sont posés par l'application. **Réserve mineure** : `Server: BaseHTTP/0.6 Python/3.12.10` divulgue la version de Python — comportement **pré-existant** de `BaseHTTPRequestHandler`, non introduit par cette branche. | ⚠️ Mineur, pré-existant |
| **Journaux** | `logger.error` **sans `exc_info`** → aucune trace d'appels n'est produite (donc aucun message d'exception imbriqué). Un `NullHandler` est installé par défaut → **rien n'est écrit** tant que l'application ne configure pas la journalisation. Capture réelle : `Échec de l'appel au fournisseur IA : 401: [REDACTED] [REDACTED] [REDACTED]` — aucun secret, aucun `Traceback`. | ✅ **Corrigé** |
| **Chemins d'erreur alternatifs** | `add_memory` / `delete_memory` renvoient `str(exc)` **uniquement** pour `PersistentMemoryError`. Vérification : tous les `raise PersistentMemoryError` de `app/memory/persistent.py` produisent des **textes fixes** sans valeur utilisateur (mémoire indisponible, contenu vide, dépassement de longueur, motif secret détecté). | ✅ **Sûr** |
| **Journalisation de `BaseHTTPRequestHandler`** | `log_message` reste désactivé (inchangé) → les requêtes HTTP ne sont pas journalisées. | ✅ inchangé |
| **Réflexion sur le contenu du message** | `send_message` renvoie `"content": content` en cas de succès pour `/remember` → c'est le contenu **émis par l'utilisateur lui-même**, pas une fuite. | ✅ sans objet |

### 3.5 Reproduction du risque S-003 — corrigé

| Scénario | Avant (4b6f515) | Après (branche) |
|----------|-----------------|----------------|
| `POST /message` avec fournisseur levant `sk-FAUSSE-CLE-XYZ` | `{"error": "Erreur du fournisseur IA : ... sk-FAUSSE-CLE-XYZ"}` → **fuite** | `{"error": "Erreur du fournisseur IA : échec de la communication avec le fournisseur."}` → **pas de fuite** |
| Faux secret dans le journal interne | — | `[REDACTED]` → **pas de fuite** |
| Trace brute dans le journal | — | absente → ✅ |

### 3.6 Les tests couvrent-ils les risques annoncés ?

| Risque annoncé | Test présent | Couverture |
|----------------|--------------|------------|
| Fausse clé fournisseur | `test_erreur_fournisseur_avec_cle_fausse` + `test_cle_fournisseur_redigee` | ✅ |
| Jeton Bearer | `test_erreur_fournisseur_avec_jeton_bearer_faux` + `test_jeton_bearer_redige` | ✅ |
| Mot de passe | `test_erreur_fournisseur_avec_mot_de_passe_faux` + `test_mot_de_passe_redige` | ✅ |
| Exception inattendue | `test_exception_inattendue_ne_divulgue_pas_son_contenu` | ✅ |
| Préservation du contexte | `test_erreur_fournisseur_preserve_le_contexte` | ✅ |
| `/remember` et `/forget` | `test_remember_ne_divulgue_pas_les_secrets`, `test_forget_ne_divulgue_pas_les_secrets` | ✅ |
| Journal interne | `test_log_interne_ne_contient_pas_les_secrets`, `test_log_interne_sans_trace_brute` | ✅ |
| Paire clé=valeur | `test_paire_cle_valeur_redigee` | ✅ |
| Non-régression | `test_texte_non_sensible_conserve` | ✅ |

**Efficacité prouvée par mutation** : en remplaçant `app/interface/web.py` par la version `4b6f515` (avant correction), **13 des 14 tests échouent** (8 failures + 5 errors). ✅

---

## 4. Section D — Configuration mémoire

### 4.1 Conversion des valeurs autorisées

| Valeur | Résultat attendu | Résultat observé | Statut |
|--------|------------------|-------------------|--------|
| `true` | True | True | ✅ |
| `1` | True | True | ✅ |
| `yes` | True | True | ✅ |
| `on` | True | True | ✅ |
| `false` | False | **False** | ✅ |
| `0` | False | **False** | ✅ |
| `no` | False | **False** | ✅ |
| `off` | False | **False** | ✅ |
| `TRUE` (majuscules) | True | True | ✅ |
| `False` | False | False | ✅ |
| `OFF` | False | False | ✅ |

**Insensibilité à la casse** confirmée. Le bug d'origine (`bool("false")` → True) est **corrigé**.

### 4.2 Valeurs absentes et invalides

| Cas | Comportement observé | Statut |
|-----|----------------------|--------|
| Variable absente | `memory_enabled = False` (défaut `DEFAULTS`), type `bool` | ✅ |
| Valeur invalide (`peut-etre`) | `SettingsError` explicite : `MILES_MEMORY_ENABLED doit être un booléen (true/false), valeur reçue : 'peut-etre'` | ✅ |

### 4.3 Origine des valeurs

| Source | Cas | Résultat | Statut |
|--------|-----|----------|--------|
| `.env` | `MILES_MEMORY_ENABLED=false` | `False` | ✅ |
| `.env` | `MILES_MEMORY_ENABLED=true` | `True` | ✅ |
| Variable de processus | `.env=true` + processus=`false` | **`False`** (processus prioritaire) | ✅ |
| JSON | `true` (booléen) | `True` (type `bool`) | ✅ |
| JSON | `false` (booléen) | `False` (type `bool`) | ✅ |
| JSON | `"true"` (chaîne) | `True` (type `bool`) | ✅ |
| JSON | `"false"` (chaîne) | **`False`** (type `bool`) | ✅ |
| JSON | `"peut-etre"` | `SettingsError` explicite | ✅ |

**Les deux sources sont couvertes** : la normalisation est appliquée dans la boucle de lecture des variables d'environnement **et** dans `_validate()` (qui couvre le fichier JSON). Ce double point de contrôle est **redondant mais_volontaire et sûr** (défense en profondeur).

### 4.4 La désactivation bloque-t-elle l'activation de la mémoire persistante ?

| Vérification | Résultat |
|--------------|----------|
| `miles.py` : instanciation conditionnée | `if settings.memory_enabled:` → **confirmé** |
| Base `data/memory.db` créée quand `memory_enabled = False` | **Non** — aucune base créée |
| Test automatisé correspondant | `test_desactivation_bloque_la_creation_de_la_base` ✅ |
| Test automatisé activation | `test_activation_cree_la_base` ✅ |

✅ **La désactivation empêche effectivement l'activation de la mémoire persistante.**

### 4.5 Efficacité des tests de configuration (mutation)

| Expérience | Résultat |
|------------|----------|
| Code corrigé | 14 tests, `OK` |
| **Mutation** : retrait de la conversion `memory_enabled` dans la boucle env | 14 tests, `OK` → la normalisation de `_validate()` suffisait |
| **Mutation** : retrait de la normalisation de `_validate()` **et** de la conversion env | **11 tests en FAILURE** |

La couverture est donc **efficace** : la double normalisation est bien ce qui rend la suite rouge dès qu'on retire les deux mécanismes. ✅

### 4.6 `MILES_VOICE_ENABLED` — hors périmètre

Le traitement de `voice_enabled` est **inchangé** (`elif key == "voice_enabled": value = value.lower() in ("1","true","yes","on")`). Aucun commit de la branche ne le modifie. ✅ Conforme à la consigne.

---

## 5. Section E — Tests et intégrité

### 5.1 Tests ciblés

| Fichier | Tests annoncés | Tests comptés | Statut |
|---------|-----------------|---------------|--------|
| `tests/test_miles_entrypoint.py` | 4 | 4 | ✅ |
| `tests/test_web_security.py` | 14 | 14 | ✅ |
| `tests/test_settings_memory_config.py` | 14 | 14 | ✅ |
| **Total ciblés** | **32** | **32** | ✅ |

### 5.2 Suite complète

```
$ python -m unittest discover -s tests
Ran 178 tests in 26.075s
OK
```

| Mesure | Valeur |
|--------|--------|
| Tests découverts | 178 |
| Réussis | 178 |
| Échecs | 0 |
| Erreurs | 0 |
| Ignorés | 0 |
| Décomposition | 146 (base `4b6f515`) + 32 (ciblés Agent B) |
| Environnement | **Windows**, Python 3.12.10 |

> ⚠️ **Ce résultat est une validation Windows.** Il ne constitue **pas** une validation Debian 13, qui relève de l'agent B et n'a pas été effectuée par Agent A.

### 5.3 L-007 à L-010 présents et inchangés

✅ Confirmé — voir section 1.4. Aucun fichier de `app/tools/` ni `tests/test_tool_engine.py` modifié par la branche.

### 5.4 Intégrité du dépôt pendant la revue

| Contrôle | Résultat |
|----------|----------|
| `main` | `b5e1007` inchangée ✅ |
| Branches des autres agents | intactes ✅ |
| Fichiers de production modifiés par Agent A | **aucun** ✅ |
| Tests modifiés par Agent A | **aucun** ✅ |
| Commit / push / PR / fusion | **aucun** ✅ |
| Secrets réels / fournisseur payant / téléchargement | **aucun** ✅ |

---

## 6. Risques résiduels

| # | Risque | Gravité | Statut |
|---|--------|---------|--------|
| R-01 | `Server: BaseHTTP/0.6 Python/3.12.10` divulgue la version de Python. Pré-existant, non introduit par la branche. | **Faible** | À traiter (option : surcharge de `version_string()`) |
| R-02 | Un secret de format non couvert (JWT `eyJ...` sans préfixe `sk-`, sans `Bearer`, sans `clé=valeur`) n'est pas redacté **dans les journaux**. Sans effet sur les réponses publiques (messages génériques) ni sur le comportement par défaut (journal `NullHandler`). | **Faible** | Recommandation : ajouter un motif générique de type JWT/base64 long |
| R-03 | `except PersistentMemoryError` renvoie `str(exc)` au client. Sûr à ce jour (tous les messages de `persistent.py` sont fixes), mais **fragile** si un futur `raise` inclut une valeur utilisateur. | **Faible** | Recommandation : message générique, comme pour les autres branches |
| R-04 | `public_provider_error(exc)` classifie l'erreur d'après `str(exc).lower()` : la classification peutDARLOir « invalide » ou « indisponible » selon le fournisseur, ce qui est un indice de diagnostic mais non un secret. | **Très faible** | Acceptable |
| R-05 | S-002 (aucune authentification web), S-004 (`Content-Length` non borné), S-005 (symlink), S-006 (`Queue` non fermée) : **toujours ouverts**, hors périmètre de la branche. | Moyenne à faible | Suivis séparément ; S-002 bloquant avant exposition réseau |
| R-06 | Validation Debian 13 non effectuée par Agent A. | — | Responsabilité Agent B |
| R-07 | Incident de publication : 5 commits publiés sur `origin` sans autorisation distincte, branche locale supprimée. Aucun impact sur le code, `main` intact. | **Procédurale** | À régulariser par le propriétaire |

---

## 7. Conclusion

### 7.1 Sur les trois corrections

| Correction | Verdict |
|------------|---------|
| **S-001** (`PersistentMemoryError` non importé) | ✅ **Corrigé** — import depuis le module de définition, traitement d'erreur préservé, test de régression prouvé efficace par mutation |
| **S-003** (divulgation d'exceptions dans les réponses HTTP) | ✅ **Corrigé** — `sanitize_text()` + `public_provider_error()` + 6 blocs `except` traités, aucune fuite reproduite, journal sans trace brute, 13/14 tests détectent le défaut d'origine |
| **Configuration mémoire** (`MILES_MEMORY_ENABLED=false` inopérant) | ✅ **Corrigé** — 11 valeurs booléennes conformes, absente → False, invalide → erreur explicite, `.env` et JSON couverts, désactivation bloquant la création de la base |

### 7.2 Sur la fusion

La branche **peut être envisagée pour fusion** vers `main` **après** :
1. régularisation de l'incident de publication (décision du propriétaire sur la branche distante) ;
2. examen de la validation Debian 13 d'Agent B (non substitute, mais attendu par le workflow) ;
3. mise à jour de `docs/coordination/TASKS.md` et `STATUS.md` pour acter la clôture.

**S-002 reste bloquant avant toute exposition réseau** du boîtier.

### 7.3 Ce que cette revue ne déclare pas

- Elle **ne déclare pas** la Phase 4 validée globalement : la validation Debian 13 manque.
- Elle **ne corrige pas** S-002, S-004, S-005, S-006, qui restent ouverts.
- Elle **ne modifie aucun fichier** de production ni de test.

---

## 8. Fichiers modifiés par cette revue

| Fichier | Action |
|---------|--------|
| `docs/reports/PHASE_4_REVIEW_FIXES_AGENT_A.md` | Mis à jour (ce document, version finale) |

**Éléments de travail hors dépôt** : un *worktree* de lecture en `C:\Users\StanC\AppData\Local\Temp\opencode\miles-review-s001-s003` (checkout détaché de `f53cffc`) et trois copies de mutation jetables dans le même répertoire temporaire. Aucune n'affecte le dépôt ni les branches.

**Confirmations** : aucun commit, push, PR, fusion ou suppression de branche. `main` (`b5e1007`), les correctifs L-007 à L-010 (`4b6f515`) et le travail des autres agents sont intacts. Aucun secret réel utilisé, aucun fournisseur payant contacté, aucun téléchargement, aucune dépense.
