# docs/reports/PHASE_6_3L_P1_ANSWER_AUTHORIZATION_AUDIT_AGENT_B.md — Audit indépendant P1 `/answer` et D2

**Agent** : Agent B (revue et vérification)
**Date** : 2026-10-22
**Branche auditée** : `fix/miles-answer-authorization-only` @ `8b9ab15` et `fix/miles-windows-paths` @ `d3240d2`
**Branche de publication** : `audit/agent-b-phase6-1-web-security-review`
**Plateformes** : Windows 3.14.7, Debian 13 (Python 3.13.5)

---

## 1. Mission 1 — Autorisation `/answer` (commit `8b9ab15`)

### SHA testé
`8b9ab156093dfc49fd3ba7872f0cc5eff18975f4`

### Vérifications

| Critère | Résultat |
|---|---|
| `/answer` n'approuve jamais sans jeton valide | ✅ HTTP 403 `authorization_requires_token` pour `o`, `oui`, `yes`, `ok`, `autorise` |
| `/authorize` exige jeton valide, non expiré, à usage unique | ✅ `check_authorization` + `hmac.compare_digest` + `expires_at` |
| Contrôles de session et de propriétaire appliqués | ✅ `requester_user_id`, `requester_session_id`, `mission.owner_user_id` |
| Une clarification ne peut pas contourner l'autorisation | ✅ `answer()` lève `MissionAuthorizationError` si `pending.kind == "authorization"` |
| Tests détectent la régression (mutation) | ✅ retrait du garde-fou → 9 erreurs sur 8 tests |

### Preuves

- `/answer 'o'` → HTTP 403 `authorization_requires_token` (5 variantes)
- `/authorize` avec vrai jeton → HTTP 200 `approved:true` + exécution réelle
- `/authorize` avec jeton expiré → HTTP 403 `expired_approval_token`
- Mutation (retrait garde-fou) → 9 erreurs sur 8 tests

### Tests

| Plateforme | Suite | Résultat |
|---|---|---|
| Windows | `tests.test_answer_authorization_invariant` (8 tests) | ✅ OK |
| Windows | `tests.test_answer_d1ter_fixes` (19 tests) | ✅ OK |
| Windows | Suite complète (655 tests) | ✅ OK (4 ignorés) |
| Debian 13 | `tests.test_answer_authorization_invariant` (8 tests) | ✅ OK |
| Debian 13 | Suite complète (655 tests) | ❌ 4 échecs (D2, pas P1) |

### Verdict Mission 1 : ✅ **VALIDÉ**

---

## 2. Mission 2 — Chemins D2 (commit `d3240d2`)

### SHA testé
`d3240d2ecce9847cdcc13b49769f482d9c5a1956`

**Note** : le SHA `e623627` mentionné dans la mission n'existe pas dans le dépôt. Le commit D2 le plus récent est `d3240d2`.

### Vérifications

| Critère | Windows | Debian 13 |
|---|---|---|
| Chemins POSIX absolus avec espaces traités intégralement | N/A | ❌ tronqué (`/tmp/xxx/Dossier` au lieu de `/tmp/xxx/Dossier Avec Espace`) |
| Chemins entre guillemets fonctionnent | ✅ | ❌ POSIX cité → `None` |
| Chemins Windows externes refusés sous Linux | N/A | ❌ `C:/Windows/System32` accepté comme chemin relatif |
| Chemins autorisés utilisables sous Windows | ✅ 555 tests OK | — |
| Aucun accès hors périmètre | ✅ | ❌ `C:/Windows/System32` résolu dans la racine projet |

### 4 échecs Debian (reproduits indépendamment, 2 runs)

```
FAIL: test_chemin_hors_perimetre_refuse (test_mission_orchestrator)
FAIL: test_dossier_avec_espace_analyse (×2) (test_windows_paths)
FAIL: test_mission_avec_chemin_windows_externe_echoue (test_windows_paths)
```

### Causes racines (3 défauts)

1. **POSIX avec espace non prolongé** : `_word_continues_path` n'étend les espaces que pour les chemins Windows absolus.
2. **POSIX cité → None** : `_QUOTED_PATH` capture le chemin cité mais aucun test ne couvre le cas POSIX.
3. **Chemin Windows externe accepté sur Linux** : `C:/Windows/System32` est résolu comme chemin relatif (`/tmp/.../C:/Windows/System32`) → dans la racine projet → non refusé.

### Mutation (discriminance)

Retrait de la capture de la lettre de lecteur → 9/21 tests échouent ✅

### Preuves d'extraction (Debian)

```
'Analyse /tmp/xxx/Dossier Avec Espace en lecture seule' -> '/tmp/xxx/Dossier'  (tronqué)
'Analyse "/tmp/xxx/Dossier Avec Espace" en lecture seule' -> None  (devrait fonctionner)
'Analyse C:/Windows/System32' -> 'C:/Windows/System32'  (accepté, devrait être refusé)
```

### Verdict Mission 2 : ⚠️ **VALIDÉ SOUS RÉSERVES**

- Fonctionne correctement sur Windows (555 tests OK)
- 4 échecs sur Debian, dont 1 régression d'un test préexistant
- 3 défauts identifiés nécessitant correction avant fusion

### Correctif minimal recommandé

1. Étendre `_word_continues_path` aux chemins POSIX absolus
2. Traiter les chemins POSIX cités
3. Sur Linux, refuser explicitement les chemins `C:/...` (hors périmètre)

---

## 3. Résumé

| Mission | SHA | Verdict | Réserve |
|---|---|---|---|
| P1 `/answer` | `8b9ab15` | ✅ VALIDÉ | Aucune |
| D2 Chemins | `d3240d2` | ⚠️ VALIDÉ SOUS RÉSERVES | 4 échecs Linux, 3 défauts POSIX |

## 4. Commandes de reproduction

```bash
# Windows
python -m unittest discover -s tests   # 655 OK (8b9ab15), 555 OK (d3240d2)
python -m unittest tests.test_answer_authorization_invariant  # 8 OK
python -m unittest tests.test_windows_paths  # 21 OK

# Debian 13
python3 -m unittest discover -s tests  # 655 tests, 4 failures (8b9ab15)
python3 -m unittest discover -s tests  # 555 tests, 4 failures (d3240d2)
python3 -m unittest tests.test_answer_authorization_invariant  # 8 OK
```

## 5. Fichiers examinés

- `app/orchestration/planner.py` (extract_target_path, _word_continues_path, _QUOTED_PATH)
- `app/security/paths.py` (canonical_path, default_allowed_roots, is_within)
- `app/orchestration/runner.py` (answer, check_answer, authorize, check_authorization)
- `app/interface/web.py` (answer_mission, authorize_mission)
- `tests/test_windows_paths.py` (21 tests)
- `tests/test_answer_authorization_invariant.py` (8 tests)
- `tests/test_answer_d1ter_fixes.py` (19 tests)

## 6. Points encore incertains

- Le SHA `e623627` mentionné dans la mission n'existe pas — le commit D2 audité est `d3240d2`
- Les tests D2 n'ont jamais été exécutés sur Linux par Agent A
- L'instabilité du moteur d'outils (multiprocessing) sur Linux masque les erreurs réelles

## 7. Limites rencontrées

- VM Debian 13 nécessite redémarrage fréquent (crashs)
- Les permissions root sont nécessaires pour git dans /tmp
- Le clone frais est nécessaire à chaque session

---

**Agent B** — 2026-10-22 — Rapport d'audit indépendant
