# docs/reports/PHASE_4_REVIEW_AGENT_B.md — Rapport de révision indépendante Phase 4 (Agent B)

## 1. Contexte et portée

Suite à la revue indépendante initiale d'Agent B (défauts L-007 à L-010), Agent A a publié des corrections de sécurité sur la branche `review/phase4-security-fixes` du dépôt GitHub `https://github.com/Miles-corp/Milescorp.git`.

Cette mission est la **revue indépendante d'Agent B** du commit publié. Elle ne modifie pas les fichiers de production d'Agent A sur `main` ; elle travaille sur une branche de revue distincte `review/agent-b-phase4-review`.

## 2. Commit examiné

| Élément | Valeur |
|---------|--------|
| Dépôt distant | `https://github.com/Miles-corp/Milescorp.git` |
| Branche examinée | `review/phase4-security-fixes` (origin) |
| Commit examiné | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` |
| Message du commit | `fix: address Phase 4 security review findings` |
| Commit de base (parent) | `b5e1007` |
| Branche de revue locale | `review/agent-b-phase4-review` (créée à partir de `4b6f515`) |

Vérification : le hash récupéré par `git ls-remote origin review/phase4-security-fixes` correspond exactement au commit attendu `4b6f515`. Le parent `b5e1007` correspond au commit de base annoncé.

## 3. Fichiers examinés (lecture du code réel)

| Fichier | Rôle | Examiné |
|---------|------|---------|
| `app/tools/engine.py` | Moteur de décision et exécution d'outils | Oui |
| `app/tools/policy.py` | Politique de sécurité (shell, code, secrets) | Oui |
| `app/tools/registry.py` | Registre des outils autorisés | Oui |
| `app/tools/audit.py` | Journal d'audit des demandes | Oui |
| `app/tools/status_tool.py` | Outil lecture seule (`status_tool_handler`) | Oui |
| `tests/test_tool_engine.py` | Tests du moteur (146 tests inclus) | Oui |
| `tests/test_tool_policy.py` | Tests de la politique | Oui |
| `tests/test_tool_audit.py` | Tests du journal d'audit | Oui |
| `tests/test_status_tool.py` | Tests de l'outil status | Oui |
| `docs/reports/PHASE_4_REVIEW_AGENT_B.md` | Rapport d'Agent A (préexistant dans le commit) | Oui (lecture) |

## 4. Tests réellement exécutés

| Commande | Résultat |
|----------|----------|
| `python -m unittest discover -s tests -v` | ✅ **146 tests, 146 OK, 0 échec, 0 erreur** (19,8 s) |

| Environnement | Valeur |
|---------------|--------|
| Système | Windows (PC de l'agent B) |
| Version Python | 3.14.7 |
| Interpréteur | CPython |
| Dépendances | Stdlib uniquement (multiprocessing, unittest, etc.) |
| Notes | Les tests n'ont pas été exécutés sur Debian 13 depuis ce poste. Les résultats ci-dessous sont **uniquement** ceux de Windows. |

### Couverture des défauts L-007 à L-010 dans les tests exécutés

| Test | Défaut couvert | Résultat |
|------|---------------|----------|
| `test_depassement_delai` | L-007 | OK |
| `test_depassement_delai_arret_effectif` | L-007 | OK |
| `test_parametre_shell_refuse` | L-008 | OK |
| `test_parametre_command_refuse` | L-008 | OK |
| `test_parametre_code_refuse` | L-008 | OK |
| `test_parametre_secret_refuse` | L-008 | OK |
| `test_valeur_secrete_refusee` | L-008 | OK |
| `test_confirmation_expiree_refusee` | L-009 | OK |
| `test_confirmation_valide_dans_delai` | L-009 | OK |
| `test_confirmation_utilisee_uneseulefois` | L-009 | OK |
| `test_audit_sans_secret` | L-010 | OK |
| `test_exception_handler` | L-010 | OK |

## 5. Analyse des quatre défauts corrigés

### L-007 — Arrêt effectif après timeout (critique)

**Problème initial :** `threading.Thread` avec `thread.join(timeout=)` n'arrêtait pas réellement le handler en cas de dépassement.

**Correction dans `app/tools/engine.py` (commit `4b6f515`) :**
- Remplacement de `threading.Thread` par `multiprocessing.Process` avec fonction de module niveau `_run_handler_in_process` (sérialisable par `spawn` sur Windows).
- En cas de dépassement : `process.terminate()`, puis `process.join(timeout=5)`, puis `process.kill()` si le processus est toujours vivant.

**Vérification de la revue d'Agent B :**
Le code lit correctement :
1. `process.start()` lance le handler dans un processus séparé.
2. `process.join(timeout=tool.timeout_seconds)` attend avec délai.
3. `if process.is_alive()` : `process.terminate()` puis `process.join(timeout=5)` puis `process.kill()` si nécessaire.
4. Retour d'un `ToolResult` avec `success=False` et message de délai dépassé.

**Limite identifiée :** Sur Windows, `multiprocessing` utilise `spawn` (pas `fork`). Le handler doit être sérialisable (fonction de module niveau, pas de fermeture/capture de variables locales complexes). Un processus tué ne peut pas annuler une opération externe déjà réalisée (écriture fichier, appel réseau déjà émis). Ce risque est documenté mais ne peut pas être éliminé par ce mécanisme seul.

**Verdict L-007 :** Corrigé de manière appropriée pour le périmètre du projet (aucun shell arbitraire, aucun accès réseau dans les handlers de test).

### L-008 — Application de la politique de sécurité (critique)

**Problème initial :** Les méthodes `validate_no_shell_access`, `validate_no_code_execution`, `validate_no_secret_access` existaient dans `ToolPolicy` mais n'étaient pas appelées dans `request_tool`.

**Correction dans `app/tools/engine.py` (commit `4b6f515`) :**
- Appel des trois méthodes dans `request_tool`, après vérification de l'outil et avant toute exécution :
  - `self._policy.validate_no_shell_access(parameters)`
  - `self._policy.validate_no_code_execution(parameters)`
  - `self._policy.validate_no_secret_access(parameters)`
- En cas de `PermissionError`, refus immédiat avec message générique, pas d'exécution du handler.

**Correction dans `app/tools/policy.py` (commit `4b6f515`) :**
- Vérification récursive des clés et valeurs dans les structures imbriquées (`dict`, `list`, `tuple`, `set`) via `_iter_keys` et `_iter_values`.
- Détection des valeurs contenant des mots interdits (ex: `"mon mot de passe est secret123"` dans une valeur de paramètre).

**Vérification de la revue d'Agent B :**
Les tests `test_parametre_shell_refuse`, `test_parametre_command_refuse`, `test_parametre_code_refuse`, `test_parametre_secret_refuse`, `test_valeur_secrete_refusee` confirment que :
1. Les clés interdites dans les paramètres sont rejetées.
2. Les valeurs contenant des mots interdits sont rejetées.
3. Le refus empêche l'exécution du handler (pas d'effet de bord).
4. Les paramètres imbriqués sont inspectés récursivement.

**Verdict L-008 :** Corrigé de manière complète et testée.

### L-009 — Expiration des confirmations (critique)

**Problème initial :** Les jetons de confirmation n'avaient pas de durée de validité.

**Correction dans `app/tools/engine.py` (commit `4b6f515`) :**
- `_PendingConfirmation` contient un champ `expires_at: float`.
- L'horloge est injectable via le paramètre `clock` du constructeur (`clock: Callable[[], float] = time.time`), permettant les tests d'expiration.
- TTL par défaut : 300 secondes (5 minutes).
- Dans `_find_pending_confirmation` : si `self._clock() > pending.expires_at`, le jeton est supprimé et `None` est retourné.
- Utilisation unique : `self._pending_confirmations.pop(pending.token, None)` après confirmation valide.

**Vérification de la revue d'Agent B :**
Les tests confirment :
1. `test_confirmation_expiree_refusee` : TTL de 0,1 s, attente de 0,2 s, token expiré refusé et nouveau token généré.
2. `test_confirmation_valide_dans_delai` : TTL de 60 s, confirmation dans le délai acceptée.
3. `test_confirmation_utilisee_uneseulefois` : même token utilisé deux fois → deuxième utilisation refusée.
4. Liaison aux paramètres exacts : `test_confirmation_mauvais_parametres` (déjà présent avant, confirmé).
5. Liaison au nom de l'outil : `test_confirmation_mauvais_outil` (déjà présent avant, confirmé).

**Verdict L-009 :** Corrigé de manière complète et testée.

### L-010 — Protection des journaux d'audit (critique)

**Problème initial :** Les exceptions brutes des handlers pouvaient être journalisées, exposant potentiellement des secrets.

**Correction dans `app/tools/engine.py` (commit `4b6f515`) :**
- Dans `_execute_tool`, en cas d'erreur du handler : `error_message="Erreur d'exécution."` (message générique, pas l'exception brute).
- Le `ToolResult.error_message` contient le message générique.
- Dans `_record` : l'`error_message` passé à l'audit est le message générique, jamais l'exception brute.

**Vérification de la revue d'Agent B :**
Les tests confirment :
1. `test_exception_handler` : `assertNotIn("RuntimeError", result.error_message)` et `assertNotIn("erreur simulee", result.error_message)`.
2. `test_audit_sans_secret` : passage de `{"data": "sk-1234567890"}` et vérification qu'aucun motif de secret n'apparaît dans les entrées d'audit.

**Verdict L-010 :** Corrigé de manière appropriée.

## 6. Limites et risques résiduels

| Limite | Explication |
|--------|-------------|
| Arrêt effectif sous Windows (spawn) | `multiprocessing` sous Windows utilise `spawn` : le handler doit être sérialisable (fonction de module niveau). Les fermetures (closures) ne fonctionnent pas. Un processus tué ne peut pas annuler une opération externe déjà réalisée. |
| Jetons en mémoire vive | Les confirmations sont stockées en mémoire ; perdues en cas de redémarrage du processus. |
| Pas de fournisseur IA réel | Aucun appel API réel n'a été effectué (pas de clé API configurée). |
| Pas de test sur Debian 13 | Les tests ont été exécutés uniquement sur Windows Python 3.14.7. La validation Debian 13 reste à effectuer par l'agent sur sa VM. |
| ResourceWarning | Quelques `ResourceWarning` apparaissent dans les sorties (sqlite3, HTTP) mais ne bloquent pas l'exécution. |

## 7. Tests de régression ajoutés par Agent A (dans le commit examiné)

Les tests suivants ont été ajoutés pour couvrir les défauts L-007 à L-010 et sont présents dans le commit `4b6f515` :

| Fichier de test | Nouveaux tests | Cible |
|-----------------|---------------|-------|
| `tests/test_tool_engine.py` | `test_depassement_delai`, `test_depassement_delai_arret_effectif`, `test_parametre_shell_refuse`, `test_parametre_command_refuse`, `test_parametre_code_refuse`, `test_parametre_secret_refuse`, `test_valeur_secrete_refusee`, `test_confirmation_expiree_refusee`, `test_confirmation_valide_dans_delai`, `test_confirmation_utilisee_uneseulefois` | L-007, L-008, L-009, L-010 |
| `tests/test_tool_policy.py` | Tests existants pour `validate_no_*` (déjà présents avant) | L-008 |
| `tests/test_tool_audit.py` | `test_no_secret_in_audit` (déjà présent avant) | L-010 |
| `tests/test_status_tool.py` | Tests existants (déjà présents avant) | Lecture seule |

## 8. Verdict

**APPROUVÉ AVEC RÉSERVES**

### Justification

Les quatre défauts identifiés lors de la revue initiale (L-007 à L-010) ont été corrigés dans le commit `4b6f515` :
1. **L-007** : `multiprocessing.Process` avec `terminate()`/`kill()` remplace `threading.Thread`. Arrêt effectif après timeout.
2. **L-008** : Les trois validations de politique sont appelées dans `request_tool` avant toute exécution. Vérification récursive des structures imbriquées.
3. **L-009** : Jetons de confirmation avec TTL (défaut 300 s), horloge injectable, suppression après expiration ou utilisation unique.
4. **L-010** : Message d'erreur générique "Erreur d'exécution." au lieu de l'exception brute. Aucun secret dans l'audit.

Tous les **146 tests passent** sur Windows (Python 3.14.7), dont les tests de régression pour les quatre défauts.

### Réserves

- Les tests n'ont été exécutés que sur **Windows**, pas sur Debian 13. Le multiprocessing `spawn` sous Windows peut se comporter différemment de `fork` sous Linux.
- Un processus tué ne peut pas annuler une opération externe déjà effectuée (appel réseau, écriture disque). Ce risque structurel ne peut pas être éliminé par le seul moteur d'outils ; il relève de la conception des handlers eux-mêmes.
- Le verdict reflète les preuves recueillies sur ce poste Windows uniquement.

## 9. Recommandations

1. Agent B recommande la **validation sur Debian 13** avant toute fusion dans `main` (exécuter `python3 -m unittest discover -s tests -v` sur la VM).
2. Agent A devrait documenter que les handlers exécutés via le moteur doivent être des fonctions de module niveau sérialisables (contrainte `spawn` sous Windows).
3. Aucun push vers `main` ne doit être effectué sans autorisation explicite de l'utilisateur (règle DEC-004).

## 10. Fichiers modifiés par cette revue

| Fichier | Action |
|---------|--------|
| Aucun (lecture seule) | Aucun fichier n'a été modifié, créé ou supprimé lors de cette revue d'Agent B. Le code examiné est celui du commit `4b6f515` publié par Agent A. |

---
*Rapport rédigé par Agent B le 2026-10-19. Commit examiné : `4b6f515`. Environnement de test : Windows, Python 3.14.7.*
