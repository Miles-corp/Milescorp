# docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md — Corrections S-001, S-003 et configuration mémoire (Agent B)

## 1. Branche et commit de base

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp.git` |
| Branche de correction | `fix/agent-b-s001-s003-memory-config` |
| Commit de base | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` (`fix: address Phase 4 security review findings`) |
| Commit de base (parent) | `b5e1007` |
| `main` | Non modifiée (`b5e1007` inchangé) |
| Branches des autres agents | Non touchées : `review/phase4-security-fixes` (`4b6f515`), `review/agent-b-phase4-review` (`928410c`), `work/agent-a-phase4-audit` (`632f27b`) |

**Base retenue.** `origin/main` est à `b5e1007`, qui ne contient **pas** les correctifs L-007 à L-010 (ils sont dans `4b6f515`, branche `review/phase4-security-fixes`). La seule version publiée contenant L-007 à L-010 est donc `4b6f515` : c'est la base de la réimplémentation, et elle vérifie l'exigence « L-007 à L-010 restent présents et inchangés ».

**Point de départ réel.** Les commits `ccb512d` et `8e82d45` annoncés lors de la mission précédente, ainsi que la branche `fix/agent-b-s001-s003`, n'ont jamais été publiés : ils étaient uniquement locaux. La présente mission repart donc du code réellement présent (`4b6f515`) et réimplémente les trois corrections dans une branche dédiée.

## 2. Fichiers modifiés

| Fichier | Action | Correction |
|---------|--------|------------|
| `miles.py` | Modifié (+1 / -1) | S-001 |
| `app/interface/web.py` | Modifié (+104 / -6) | S-003 |
| `app/config/settings.py` | Modifié (+47 / -0) | Configuration mémoire |
| `tests/test_miles_entrypoint.py` | Créé (nouveau, 4 tests) | S-001 |
| `tests/test_web_security.py` | Créé (nouveau, 14 tests) | S-003 |
| `tests/test_settings_memory_config.py` | Créé (nouveau, 14 tests) | Configuration |
| `docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md` | Créé (nouveau) | Rapport |

Aucun autre fichier du dépôt n'a été touché. Aucun fichier de `app/tools/` ni de `tests/test_tool*` n'a été modifié.

## 3. Corrections réalisées

### 3.1 S-001 — `PersistentMemoryError` non importé dans `miles.py`

**Défaut confirmé dans la base.** `miles.py:11` n'importait que `PersistentMemory`, alors que
`miles.py:72` référence `PersistentMemoryError` dans la clause
`except PersistentMemoryError as exc:`. La classe est définie dans
`app/memory/persistent.py` (ligne 23) et exportée par `app/memory/__init__.py`.

**Effet.** Si l'initialisation de la mémoire persistante levait
`PersistentMemoryError`, l'évaluation de la clause `except` levait
`NameError: name 'PersistentMemoryError' is not defined` au lieu de rattraper
l'erreur, arrêtant le programme.

**Correctif.** Import de l'exception depuis le module qui la définit, selon la
convention existante de `app/interface/cli.py` (ligne 14) :

```diff
-from app.memory.persistent import PersistentMemory
+from app.memory.persistent import PersistentMemory, PersistentMemoryError
```

Le traitement de l'erreur mémoire est **préservé** : la référence n'a pas été
supprimée, elle devient enfin résolvable. Le chemin reste inoffensif en pratique
aujourd'hui, car `_initialize()` (`app/memory/persistent.py:61-76`) applique une
dégradation gracieuse (correction L-006) ; le `except` demeure la défense prévue
si une autre opération lève cette exception.

### 3.2 S-003 — Divulgation d'informations sensibles dans les réponses HTTP

**Défaut confirmé dans la base.** Quatre réponses de `app/interface/web.py`
exposaient le contenu brut d'une exception au client HTTP :

| Emplacement | Code d'origine |
|-------------|----------------|
| `send_message`, `except AIProviderError` | `f"Erreur du fournisseur IA : {exc}"` (ligne 82) |
| `send_message`, `except Exception` | `f"Erreur inattendue : {exc}"` (ligne 88) |
| `add_memory`, `except Exception` | `str(exc)` (ligne 125) |
| `delete_memory`, `except Exception` | `str(exc)` (ligne 137) |

**Correctif — trois dispositifs.**

1. **Messages publics génériques par type d'erreur.** Le client ne reçoit plus
   jamais le message d'une exception :
   - erreur fournisseur → `public_provider_error()` : « réponse invalide du
     fournisseur » / « fournisseur indisponible » / « échec de la communication
     avec le fournisseur » ;
   - exception inattendue → « Erreur interne du service. » ;
   - `PersistentMemoryError` → message conservé, car il est produit par MILES
     lui-même sous forme de texte fixe, sans aucune valeur sensible.

2. **Journal interne assaini.** Les détails techniques sont conservés dans le
   journal `miles.web` (module `logging` de la bibliothèque standard), après
   passage par `sanitize_text()`, qui remplace par `[REDACTED]` :
   - les clés de forme `sk-…` (fournisseur distant) ;
   - les en-têtes `Bearer …` et `Basic …` ;
   - les paires `api_key=…`, `apikey=…`, `token=…`, `secret=…`,
     `password=…`, `passwd=…`, `pwd=…`, `credential=…`, `private_key=…`,
     `access_key=…` ;
   - les mentions isolées du type `password: monmotdepasse`.

3. **Absence de trace brute.** Pour les exceptions inattendues, seuls le nom de
   la classe et le message assaini sont journalisés. La trace d'appels complète
   n'est **pas** journalisée : elle contiendrait le message d'origine de
   l'exception, donc potentiellement un secret de format inconnu que
   `sanitize_text()` ne saurait pas détecter.

**Comportements préservés.** Codes HTTP (400), drapeau `context_preserved`,
champ `provider`, journalisation HTTP désactivée (`MilesHandler.log_message`),
et ensemble des réponses légitimes. Aucun secret réel n'est utilisé.

### 3.3 Configuration — `MILES_MEMORY_ENABLED`

**Défaut confirmé dans la base.** `settings.py:112` ne convertissait en booléen
que `MILES_VOICE_ENABLED` ; `MILES_MEMORY_ENABLED` restait une chaîne. La
propriété `settings.py:205` appliquait ensuite
`bool(self._values.get("memory_enabled", False))`, et **`bool("false")` vaut
`True`** : la mémoire persistante restait active malgré une désactivation
explicite.

**Correctif.**

1. **Aide de conversion** `_coerce_bool(value, source)` : un booléen est
   renvoyé tel quel ; une chaîne est comparée à une liste blanche
   (`1/true/yes/on` → `True`, `0/false/no/off` → `False`, insensible à la
   casse) ; toute autre valeur lève une `SettingsError` explicite, conformément
   à la convention du projet pour les configurations invalides.
2. **Variable d'environnement** : `MILES_MEMORY_ENABLED` est convertie via
   `_coerce_bool` dans la boucle de lecture de l'environnement.
3. **Fichier de configuration JSON** : la valeur fournie par le fichier est
   normalisée dans `_validate()`, donc une chaîne `"false"` y est également
   correctement interprétée.
4. **Valeur absente** : la valeur par défaut `False` de `DEFAULTS` est
   conservée, et la propriété `memory_enabled` reste un booléen.

**Périmètre volontairement restreint.** `MILES_VOICE_ENABLED` conserve son
comportement historique (toute valeur non reconnue vaut `False`, sans erreur).
Modifier ce paramètre hors mandat aurait changé le comportement d'une
configuration existante pour les utilisateurs ; l'alignement est recommandé
dans une mission dédiée (section 7).

## 4. Tests ajoutés

### `tests/test_miles_entrypoint.py` — S-001 (4 tests)

| Test | Comportement observable vérifié |
|------|---------------------------------|
| `test_name_error_absent_quand_memoire_echoue` | Un échec d'initialisation mémoire est rattrapé : `miles.main([])` retourne 0 et émet « mémoire persistante non disponible ». Sans l'import, ce test échoue avec `NameError`. |
| `test_name_error_absent_avec_base_inaccessible` | Idem pour un second motif d'échec. |
| `test_memoire_active_transmise_au_cli` | Comportement nominal inchangé : une instance `PersistentMemory` disponible est transmise à la CLI. |
| `test_memoire_desactivee_ne_demande_pas_de_base` | Mémoire désactivée : aucune base créée, `memory=None` transmis au CLI. |

### `tests/test_web_security.py` — S-003 (14 tests)

Secrets factices utilisés (aucun vrai secret) :
`sk-FAUSSE-CLE-XYZ` (fausse clé fournisseur),
`FAUX-JETON-BEARER-0123456789` (faux jeton Bearer),
`motdepasse-faux-0123456789` (faux mot de passe).

| Test | Comportement observable vérifié |
|------|---------------------------------|
| `test_erreur_fournisseur_avec_cle_fausse` | `POST /message` : HTTP 400, corps sans aucun des trois faux secrets ni `sk-`. |
| `test_erreur_fournisseur_avec_jeton_bearer_faux` | Idem avec un jeton Bearer factice. |
| `test_erreur_fournisseur_avec_mot_de_passe_faux` | Idem avec un mot de passe factice. |
| `test_exception_inattendue_ne_divulgue_pas_son_contenu` | Exception non prévue : HTTP 400, ni les secrets ni le texte « panne interne » dans la réponse. |
| `test_erreur_fournisseur_preserve_le_contexte` | HTTP 400 et `context_preserved` conservés. |
| `test_remember_ne_divulgue_pas_les_secrets` | `POST /remember` : HTTP 400, corps sans secret. |
| `test_forget_ne_divulgue_pas_les_secrets` | `POST /forget` : HTTP 400, corps sans secret. |
| `test_log_interne_ne_contient_pas_les_secrets` | Le journal `miles.web` conserve le détail technique, contient `[REDACTED]`, et aucun des trois faux secrets. |
| `test_log_interne_sans_trace_brute` | Aucune trace d'appels brute ni `RuntimeError:` dans le journal ; le nom de classe est conservé. |
| `test_cle_fournisseur_redigee` | `sanitize_text()` rédige une clé `sk-…`. |
| `test_jeton_bearer_redige` | `sanitize_text()` rédige un jeton `Bearer …`. |
| `test_mot_de_passe_redige` | `sanitize_text()` rédige un mot de passe. |
| `test_paire_cle_valeur_redigee` | `sanitize_text()` rédige une paire `api_key=…`. |
| `test_texte_non_sensible_conserve` | Un texte sans secret est conservé tel quel. |

### `tests/test_settings_memory_config.py` — Configuration (14 tests)

| Test | Comportement observable vérifié |
|------|---------------------------------|
| `test_valeur_par_defaut_desactive` | Valeur absente → `memory_enabled` faux. |
| `test_valeur_true_active` | `"true"` → actif. |
| `test_valeur_false_desactive` | `"false"` → **inactif** (le défaut corrigé). |
| `test_valeur_false_stockee_comme_booleen` | La valeur stockée est un booléen, pas une chaîne. |
| `test_valeur_majuscule_ignore` | `"TRUE"` / `"FALSE"` interprétés correctement. |
| `test_valeurs_booleennes_usuelles` | `1/true/yes/on` et `0/false/no/off`. |
| `test_valeur_invalide_leve_une_erreur_explicite` | `"peut-etre"` → `SettingsError`. |
| `test_fichier_avec_booleen_vrai` / `..._faux` | Valeurs JSON booléennes. |
| `test_fichier_avec_chaine_false` / `..._true` | Chaînes JSON correctement interprétées. |
| `test_fichier_avec_valeur_invalide_leve_une_erreur` | Valeur JSON invalide → `SettingsError`. |
| `test_desactivation_bloque_la_creation_de_la_base` | Désactivation effective : aucune base créée, `memory=None`. |
| `test_activation_cree_la_base` | Activation effective : base créée, mémoire disponible. |

## 5. Résultats des tests

### Commandes exécutées et résultats réels

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_miles_entrypoint tests.test_web_security tests.test_settings_memory_config -v` | ✅ **32 tests, 32 OK, 0 échec, 0 erreur** (4,64 s) |
| `python -m unittest discover -s tests` | ✅ **178 tests, 178 OK, 0 échec, 0 erreur** (23,56 s) |

| Mesure | Base `4b6f515` | Après corrections |
|---------|----------------|------------------|
| Tests ciblés S-001 / S-003 / configuration | 0 | 32 |
| Suite complète | 146 tests, 146 OK | **178 tests, 178 OK** |
| Échecs / erreurs | 0 | 0 |

Aucun test existant n'a été supprimé ni modifié.

### Environnement d'exécution

| Élément | Valeur |
|---------|--------|
| Système | **Windows** |
| Version Python | **3.14.7** (CPython) |
| Dépendances | Stdlib uniquement |
| Exécution Debian 13 | **Non effectuée dans cette mission.** Les résultats ci-dessus sont uniquement ceux de Windows. La validation Debian 13 reste à faire. |

## 6. Vérifications d'intégrité de L-007 à L-010

| Contrôle | Méthode | Résultat |
|----------|---------|----------|
| Aucun fichier de `app/tools/` modifié | `git diff --name-only 4b6f515` | ✅ Aucun |
| Aucun fichier `tests/test_tool*` modifié | idem | ✅ Aucun |
| L-007 — arrêt effectif du processus | `engine.py:370` `multiprocessing.Process`, `:380` `process.terminate()`, `:383` `process.kill()` | ✅ Intacts |
| L-008 — application de la politique | `engine.py:164` `validate_no_shell_access`, `:165` `validate_no_code_execution`, `:166` `validate_no_secret_access` | ✅ Intacts |
| L-009 — expiration des confirmations | `engine.py:72` `expires_at: float`, `:113` `confirmation_ttl_seconds: float = 300.0` | ✅ Intacts |
| L-010 — absence de secrets dans l'audit | `engine.py:414` `error_message="Erreur d'exécution."` | ✅ Intact |
| Tests de régression L-007 à L-010 | Suite complète | ✅ Tous passent |

Aucun conflit technique avec L-007 à L-010 n'a été découvert : les trois
corrections portent sur `miles.py`, `app/interface/web.py` et
`app/config/settings.py`, fichiers disjoints de `app/tools/`.

## 7. Risques résiduels

| Risque | Description |
|--------|-------------|
| Formats de secrets inconnus | `sanitize_text()` couvre `sk-…`, `Bearer`/`Basic` et les paires `clé=valeur`. Un secret d'un format non reconnu (clé hexadécimale brute) ne serait pas redacté **dans le journal interne**. La réponse HTTP, elle, n'expose jamais de contenu d'exception : le risque résiduel est limité au journal interne. |
| Classification des erreurs fournisseur | `public_provider_error()` classifie l'erreur en inspectant le message d'exception (usage interne, jamais transmis). Un fournisseur employant une autre formulation serait classé dans la catégorie par défaut, ce qui reste sûr. |
| `PersistentMemoryError` exposée au client | Les messages de `PersistentMemoryError` sont renvoyés tels quels car ce sont des textes fixes produits par MILES. Si une version future y intégrait une valeur issue des données de l'utilisateur, ce point devrait être revu. |
| Journalisation applicative non configurée | Le logger `miles.web` est créé avec un `NullHandler` : l'application doit configurer la journalisation pour que les détails soient persistés (dossier `logs/` actuellement inutilisé). Hors périmètre de cette mission. |
| `MILES_VOICE_ENABLED` non aligné | Conservé volontairement hors périmètre (section 3.3). Le même défaut de conversion y subsiste (`bool("false")` valant `True`), à traiter dans une mission dédiée. |
| Limite de `multiprocessing` sous Windows | Inchangé : les handlers doivent être des fonctions de module niveau sérialisables (`spawn`). Non traité par cette mission. |

## 8. Commits locaux

| Commit | Contenu | Auteur de la création |
|--------|---------|------------------------|
| `064f907d910b03647fb677f89ceffeef02275c1e` | `miles.py`, `app/interface/web.py`, `app/config/settings.py` (les 3 corrections) | **Action externe à l'agent** (voir section 9) |
| `8b0e9dc` | `tests/test_miles_entrypoint.py` | Action externe à l'agent |
| `bdee0f6eea4b1ae2df36551b6e2c9c80b584703e` | `tests/test_web_security.py` | Action externe à l'agent |
| `97bbd904db4b988ba4367afb6e7316d0a69178ab` | `tests/test_settings_memory_config.py` | Agent B |
| *(à venir)* | `docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md` | Agent B |

## 9. Événement signalé — commits et push externes

Pendant cette session, **trois commits et un push ont été créés en dehors de
l'agent B** (auteur git `iopjklad-pixel <iopjklad@gmail.com>`, c'est-à-dire la
configuration locale du poste). Le reflog montre :

```
bdee0f6 HEAD@{0}: commit: Create test_web_security.py
8b0e9dc HEAD@{1}: commit: Create test_miles_entrypoint.py
064f907 HEAD@{2}: commit: corrigé
```

La branche `fix/agent-b-s001-s003-memory-config` a également été poussée sur
`origin` (référence distante `bdee0f6eea4b1ae2df36551b6e2c9c80b584703e`),
alors que la mission interdit explicitement toute publication sans
autorisation distincte.

**Contrôle d'intégrité effectué.** Le contenu des trois commits externes a été
comparé à l'état de travail de l'agent B : `git diff bdee0f6 -- miles.py
app/config/settings.py app/interface/web.py tests/test_miles_entrypoint.py
tests/test_web_security.py` ne retourne **0 ligne de différence**. Les commits
externes contiennent donc exactement le travail réalisé et validé par les
tests, sans ajout ni modification. Aucun travail existant d'un autre agent n'a
été écrasé : `main` reste à `b5e1007` et les autres branches distantes sont
inchangées.

**Conséquence pour la suite.** Le commit `97bbd90` (test de configuration) et le
présent rapport sont **locaux uniquement** : l'agent B ne poussera rien sans
autorisation distincte. La branche distante est donc actuellement en retard
d'un commit par rapport à l'état local.

## 10. Commandes de reproduction

```bash
# Tests ciblés des trois corrections
python -m unittest tests.test_miles_entrypoint tests.test_web_security tests.test_settings_memory_config -v

# Suite complète
python -m unittest discover -s tests

# Intégrité de L-007 à L-010
git diff --name-only 4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a -- app/tools tests/test_tool_engine.py
```

## 11. Points restant à traiter

1. **Revue indépendante** de la branche `fix/agent-b-s001-s003-memory-config` par Agent A.
2. **Validation Debian 13** de la suite complète (178 tests).
3. **Alignement de `MILES_VOICE_ENABLED`** sur la même conversion stricte (mission dédiée).
4. **Configuration de la journalisation applicative** pour le logger `miles.web` (dossier `logs/` inutilisé).
5. **Publication** : le push du commit `97bbd90` et du présent rapport est soumis à autorisation distincte. La fusion dans `main` reste une décision séparée (règle DEC-004).

---
*Rapport rédigé par Agent B le 2026-10-19. Base : `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a`. Environnement de test : Windows, Python 3.14.7.*
