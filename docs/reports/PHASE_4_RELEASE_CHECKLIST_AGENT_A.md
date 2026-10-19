# docs/reports/PHASE_4_RELEASE_CHECKLIST_AGENT_A.md — Checklist de livraison Phase 4 (Agent A)

## 1. Identité du livrable

| Élément | Valeur | Statut |
|---------|--------|--------|
| Commit des correctifs L-007 à L-010 | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` | ✅ Publié (`review/phase4-security-fixes`) |
| Branche des correctifs | `review/phase4-security-fixes` | ✅ Publi��e sur `origin` |
| Commit de base de la branche | `b5e1007` | ✅ |
| Branche du rapport de revue Agent B | `review/agent-b-phase4-review` | ✅ Publiée |
| Commit du rapport Agent B | `928410ca6374687823d5d5c3e874868ee54141bd` | ✅ |
| `origin/main` | `b5e1007` | ✅ Non modifié par la Phase 4 |
| Branche de travail Agent A (audit) | `work/agent-a-phase4-audit` | ⏳ Locale, non publiée |
| Version Python (Agent A) | 3.12.10 (Windows) | ✅ |
| Version Python (Agent B) | 3.14.7 (Windows) / Debian 13 | ⚠️ **En attente** du rapport Debian 13 |

## 2. Résultats des tests

| Plateforme | Commande | Résultat | Statut |
|------------|----------|----------|--------|
| Windows (Agent A, Python 3.12.10) | `python -m unittest discover -s tests` | 161 tests, 161 OK, 0 échec, 0 erreur | ✅ |
| Windows (Agent B, Python 3.14.7) | `python -m unittest discover -s tests -v` | 146 tests, 146 OK, 0 échec, 0 erreur (commit `4b6f515`) | ✅ |
| Debian 13 (Agent B) | `python3 -m unittest discover -s tests -v` | — | ⏳ **EN ATTENTE** |

> Le décompte Windows est passé de 146 à 161 après l'ajout de 15 tests complémentaires par Agent A (branche de travail locale, non publiée). La valeur de référence pour `4b6f515` reste **146**.

## 3. Vérification des correctifs L-007 à L-010

| Défaut | Correction attendue | Vérification Agent A | Statut |
|--------|---------------------|----------------------|--------|
| **L-007** | Arrêt effectif après timeout | `multiprocessing.Process` avec `terminate()` puis `kill()` ; plus de `threading.Thread` | ✅ Code vérifié + 2 tests |
| **L-008** | Application réelle de la politique | `validate_no_shell_access`, `validate_no_code_execution`, `validate_no_secret_access` appelées dans `request_tool` avant exécution ; validation récursive imbriquée | ✅ Code vérifié + 5 tests + 8 tests complémentaires |
| **L-009** | Expiration des confirmations | `expires_at` + horloge injectable ; TTL 300 s ; liaison outil + hash des paramètres ; usage unique | ✅ Code vérifié + 3 tests + 4 tests complémentaires à horloge déterministe |
| **L-010** | Protection des journaux d'audit | Messages génériques ; exceptions brutes jamais journalisées | ✅ Code vérifié + 3 tests complémentaires |

**Réserve L-007** : l'arrêt effectif concerne le processus fils. Les effets de bord déjà produits par le handler avant l'arrêt (fichier écrit, appel réseau émis) ne sont pas annulables. La garantie est « le processus n'est plus en cours », pas « aucune effet n'a eu lieu ».

**Réserve L-009** : les jetons vivent en mémoire dans le processus `ToolEngine`. Un redémarrage de MILES invalide toutes les confirmations en attente (comportement conservateur et souhaitable).

## 4. Limites de `multiprocessing` et effets externes

| Limite | Impact | Statut |
|--------|--------|--------|
| Mode `spawn` sous Windows | Les handlers doivent être des fonctions de niveau module (picklables). Une closure ou une lambda dans un `ToolDefinition` échoue au `Process.start()`. | ⚠️ Documenté dans `docs/reports/PHASE_4_REVIEW_AGENT_B.md` |
| Mode `fork` sous Linux | Comportement différent (les closures y fonctionnent). **Non validé sous Debian 13.** | ⏳ **EN ATTENTE** |
| Effets de bord pré-timeout | Un handler peut avoir déjà écrit un fichier ou émis une requête avant d'être arrêté. | ⚠️ Documenté |
| `multiprocessing.Queue` jamais fermée | 2 handles/descripteurs fuient par appel d'outil. | ⚠️ Défaut **S-006** (audit Agent A), non corrigé à ce jour |
| `process.kill()` | Disponible à partir de Python 3.7. Compatible Debian 13 et Python 3.10+. | ✅ |
| Sérialisation du handler | Le handler et ses arguments doivent être picklables. Un handler capturant un objet non picklable échoue. | ⚠️ Documenté |

## 5. Gestion des confirmations lors d'un redémarrage

| Situation | Comportement | Statut |
|-----------|--------------|--------|
| Redémarrage du processus MILES | Les jetons en mémoire sont perdus → toute confirmation en attente doit être refaite | ✅ Conservative et correct |
| Jeton expiré (dépassement du TTL de 300 s) | Refusé, invalidé, une nouvelle confirmation est demandée | ✅ Testé (horloge déterministe) |
| Jeton réutilisé | Refusé (usage unique) | ✅ Testé |
| Jeton associé à d'autres paramètres | Refusé (hash des paramètres) | ✅ Testé |
| Jeton falsifié (`user_confirmed=True` sans jeton) | Refusé, confirmation exigée | ✅ Testé |

## 6. Contrôle des secrets et fichiers sensibles

| Vérification | Méthode | Résultat |
|--------------|---------|----------|
| `.env` suivi par Git | `git ls-files` | ✅ Non suivi (`.gitignore` lignes 10 et 13) |
| Clé API dans les fichiers versionnés | Lecture du diff complet de `4b6f515` | ✅ Aucune |
| Base SQLite versionnée | `git ls-files` + `.gitignore` (`data/*.db`) | ✅ Non suivie |
| Environnement virtuel / caches | `.gitignore` (`.venv/`, `venv/`, `__pycache__/`) | ✅ Ignorés |
| Secrets dans l'audit d'outils | Test avec fausse clé dans une exception | ✅ Non divulgué |
| Secrets dans les logs HTTP | `log_message` désactivé + `error_message` générique | ✅ |
| Fichiers du commit `4b6f515` | `git show --stat` | ✅ 4 fichiers, aucun secret |

**Note** : le fichier `.env` local de l'utilisateur (contenant la clé Groq) n'est ni affiché, ni copié, ni committé par cette mission.

## 7. Reproductibilité des tests

| Élément | Valeur | Statut |
|---------|--------|--------|
| Commande | `python -m unittest discover -s tests` (Linux : `python3 -m unittest discover -s tests -v`) | ✅ |
| Dépendances | Aucune (bibliothèque standard uniquement) | ✅ |
| Environnement virtuel | `python3 -m venv .venv && source .venv/bin/activate` | ✅ Documenté dans `docs/installation/INSTALL.md` |
| Effets externes | Aucun (SQLite en mémoire ou répertoire temporaire) | ✅ |
| Durée observée | ~20 s | ✅ |
| Graine aléatoire | Aucune (tests déterministes) | ✅ |

## 8. Critères d'acceptation et conditions bloquantes

| # | Critère | Statut |
|---|---------|--------|
| 1 | Les 67 tests historiques restent verts | ✅ 161/161 |
| 2 | L-007 : arrêt effectif du processus au timeout | ✅ (avec réserve effets de bord) |
| 3 | L-008 : politique appliquée avant exécution | ✅ |
| 4 | L-009 : confirmations expirables et à usage unique | ✅ |
| 5 | L-010 : aucune exception brute dans les journaux | ✅ |
| 6 | Fournisseurs distants existants restent compatibles | ✅ (non modifiés) |
| 7 | Aucun secret publié | ✅ |
| 8 | **Résultats de validation Debian 13** | ⏳ **BLOQUANT** |
| 9 | **Rapport de revue Agent B examiné et intégré** | ⏳ **BLOQUANT** |
| 10 | **Correction des défauts S-001 à S-006 de l'audit complémentaire** | ⏳ **BLOQUANT (recommandé)** |

**Conditions bloquantes à lever avant fusion** :
1. Rapport de validation Debian 13 d'Agent B (exécution de `4b6f515` sur Debian 13, comportement `fork` de `multiprocessing`).
2. Revue du rapport Agent B `928410c` et décision explicite sur les constats qu'il contient.
3. Traitement des défauts S-001 à S-006 relevés par l'audit complémentaire Agent A (au minimum S-001, S-002, S-003, S-004, S-005).

## 9. Vérification de la documentation

| Document | État | Statut |
|----------|-------|--------|
| `docs/installation/INSTALL.md` | Guide d'installation (Agent B) | ⚠️ Ne mentionne pas les variables `MILES_MEMORY_*` ni le moteur d'outils — **à compléter** |
| `docs/installation/QUICKSTART.md` | Guide de démarrage rapide (Agent A) | ⚠️ Rédigé avant la Phase 4 — **à compléter** (outils, mémoire) |
| `docs/reports/PHASE_4_TOOL_ENGINE.md` | Rapport Phase 4 initial | ✅ |
| `docs/reports/PHASE_4_REVIEW_AGENT_B.md` | Rapport de revue | ✅ (version Agent B : `928410c`) |
| `docs/reports/PHASE_4_SUPPLEMENTARY_SECURITY_AUDIT_AGENT_A.md` | Audit complémentaire | ⏳ Créé, non publié |
| `docs/reports/PHASE_4_ADDITIONAL_TESTS_AGENT_A.md` | Tests complémentaires | ⏳ Créé, non publié |
| `docs/reports/PHASE_4_RELEASE_CHECKLIST_AGENT_A.md` | Ce document | ⏳ Créé, non publié |
| `docs/reports/PHASE_4_PULL_REQUEST_DRAFT_AGENT_A.md` | Brouillon de PR | ⏳ Créé, non publié |
| `docs/coordination/*` | Documents de coordination | ⚠️ Ne mentionnent pas encore la Phase 4 corrigée — **à mettre à jour** |

## 10. Procédure de revue avant fusion

1. **Lecture du rapport Agent B `928410c`** sur la branche `review/agent-b-phase4-review`.
2. **Lecture de l'audit complémentaire Agent A** (S-001 à S-012) et décision sur chaque constat.
3. **Vérification des tests** : exécuter `python3 -m unittest discover -s tests -v` sur Debian 13 sur le commit candidat de fusion.
4. **Vérification des secrets** : `git ls-files | grep -iE '\.env|\.db$'` doit être vide ; inspection du diff final.
5. **Revue de code** ciblée sur `app/tools/engine.py`, `app/tools/policy.py`, `app/interface/web.py`, `app/security/validator.py`.
6. **Décision explicite** sur la fusion vers `main`, avec mise à jour de `TASKS.md` et `STATUS.md`.
7. **Fusion** par Pull Request (jamais de push direct sur `main`, jamais de force push).

## 11. Résumé

Le correctif `4b6f515` est **solide sur Windows** (161 tests verts) et les quatre défauts L-007 à L-010 sont effectivement corrigés et couverts par des tests.

Il **n'est pas validé globalement** : la validation Debian 13 et la revue du rapport Agent B restent à effectuer, et l'audit complémentaire Agent A a mis en évidence six défauts démontrés supplémentaires (S-001 à S-006) qui n'appartiennent pas au périmètre des correctifs L-007 à L-010 et n'ont volontairement pas été modifiés.
