# docs/reports/PHASE_6_3L_P1_ANSWER_AUTHORIZATION_AGENT_A.md — Mission P1 : `/answer` n'approuve plus

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base de travail** : `25baa60e2691f54900111a11194cf7e186419050` (`fix/miles-answer-d1ter` : D1 + D2 + D1-bis + D3 + A-α/B-α)
- **Branche de correction** : `fix/miles-answer-authorization-only`
- **Rapport d'audit concerné** : `docs/reports/AUDIT_MILES_PHASE5_6_61_AGENT_B.md` (Agent B, `origin/audit/agent-b-phase6-1-web-security-review` = `fd25a26`)
- **`main`** : `b9b7e7d` — **inchangée** · **Intégration** : `69bf670` — **inchangée**

> **Aucune fusion.** Les audits D1, D2, D1-bis, D3, A-α/B-α et D-B05 sont **en cours**.

---

## 1. Préalables Git

| Branche | SHA réel vérifié |
|---------|------------------|
| `origin/fix/miles-answer-d1ter` (base) | `25baa60e2691f54900111a11194cf7e186419050` ✔ |
| `origin/fix/miles-results-persistence` | `54bd13859602ab007d955115f6273dc2ca9fdb6a` ✔ |
| `origin/fix/miles-policy-path-typing` (D3) | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` ✔ |
| `origin/fix/miles-d1bis-authorization-response` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` ✔ |
| `origin/fix/miles-windows-paths` (D2) | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` ✔ |
| `origin/fix/miles-d1-web-authorization` (D1) | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` ✔ |
| `origin/main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` ✔ |
| `origin/integration/miles-phases-5-6-6-1` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` ✔ |

Worktree dédié : `C:\Users\StanC\AppData\Local\Temp\miles-answeronly`, branche
`fix/miles-answer-authorization-only`. Le checkout principal reste sur
`fix/miles-d1-web-authorization`, artefact non suivi `tatus --short--branch`
**préservé**, bases du développeur intactes.

---

## 2. Constat de l'audit Agent B (P1)

> « `/answer` approuve par réponse textuelle : `runner.answer()` transforme
> une réponse `o`/`oui`/`y`/`yes`/`ok`/`autorise` en approbation d'autorisation
> sans jeton d'approbation. **Cette voie contourne le contrôle P1-6-06.** »

**Vérification sur le code réel** : confirmé. `MissionRunner.answer`
appelait `self.authorize(..., approval_token=mission.pending.approval_token)`
lorsque la demande en attente était une autorisation — le jeton étant
**injecté en interne**, le client n'avait jamais à le présenter. La route
web `/answer` répondait donc `{"answered": true}` et la mission aboutissait,
sans contrôle de session, de propriétaire, d'expiration ni d'usage unique
côté client. C'est un **contournement du contrôle P1-6-06** (qui exige
que le demandeur présente le jeton d'approbation de la demande en attente),
et non une simple incohérence de réponse (contrairement à D1-bis).

---

## 3. Correctif

### 3.1 `app/orchestration/runner.py`

`MissionRunner.answer` **ne transforme plus** une réponse textuelle en
approbation d'autorisation. Si la demande en attente est une autorisation,
il lève `MissionAuthorizationError` (`REASON_AUTHORIZATION_REQUIRES_TOKEN`) :

```python
if mission.pending.kind == "authorization":
    raise MissionAuthorizationError(
        "Une autorisation en attente doit être accordée par la route "
        "d'autorisation, avec son jeton d'approbation.",
        REASON_AUTHORIZATION_REQUIRES_TOKEN,
    )
```

`MissionRunner.check_answer` est mise à jour pour lever le même refus (et
ne plus appeler `check_authorization` : la réponse textuelle ne porte pas
de jeton).

La mission n'est **ni approuvée ni arrêtée** : elle reste en attente, et
l'utilisateur doit passer par `/authorize` avec le jeton d'approbation
(usage unique, expiration, session, propriétaire).

### 3.2 `app/interface/cli.py`

Le handler `/mission-answer` intercepte désormais l'exception et affiche le
message ; il n'approuve plus une autorisation par réponse textuelle.

### 3.3 `app/interface/web.py`

La route `/answer` continue de valider de façon synchrone (A-α, D1-bis) et
renvoie `403` + `reason: authorization_requires_token` pour une demande
d'autorisation. Aucun changement de contrat pour les **clarifications**.

---

## 4. Tests

### 4.1 Tests mis à jour

`tests/test_answer_d1ter_fixes.py` — les tests qui affirmaient que
l'approbation sans jeton était attendue sont **inversés** pour exprimer le
comportement attendu après correction (réponse refusée, mission inchangée,
aucun grant).

### 4.2 Test d'invariant ajouté

`tests/test_answer_authorization_invariant.py` — **8 tests** :

| # | Test | Ce qu'il vérifie |
|---|------|------------------|
| 1 | `test_aucune_reponse_textuelle_n_approuve` | **aucun** mot d'approbation (`o`, `oui`, `y`, `yes`, `ok`, `autorise`…) par `/answer` n'approuve l'action |
| 2 | `test_l_api_interne_de_l_orchestrateur_n_approuve_pas` | l'API interne (`MissionRunner.answer`) n'approuve pas non plus |
| 3 | `test_une_autorisation_sans_jeton_valide_est_refusee` | `/authorize` sans jeton valide n'approuve pas |
| 4 | `test_le_jeton_dune_autre_mission_est_refuse` | jeton d'une autre mission refusé (usage unique) |
| 5 | `test_le_jeton_dune_autre_session_est_refuse` | jeton d'une autre session refusé |
| 6 | `test_le_jeton_dautre_utilisateur_est_refuse` | un autre utilisateur ne peut pas approuver |
| 7 | `test_une_autorisation_valide_approuve_et_execute` | avec un jeton valide, l'action est approuvée puis exécutée (grant unique, lié à la session et à la mission) |
| 8 | `test_le_jeton_ne_sert_qu_une_seule_fois` | le jeton est à usage unique |

Ces tests **échouent** si le correctif est retiré (9 échecs) et **passent**
avec lui.

### 4.3 Résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_answer_authorization_invariant` | **8 tests, 0 échec** (3,9 s) |
| `python -m unittest tests.test_answer_authorization_invariant` *(revert du runner)* | **9 échecs** |
| `python -m unittest tests.test_answer_d1ter_fixes` | 19 tests, 0 échec |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_web_authorization` (D1) | 6 tests, 0 échec |
| `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| `python -m unittest tests.test_web_security` | 33 tests, 0 échec |
| `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| `python -m unittest discover -s tests` | **655 tests, 0 échec, 4 ignorés** (101,0 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (21,9 s) |

Les tests ignorés sont des **limites de plateforme Windows** (liens
symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13.

---

## 5. Preuve sur le vrai serveur (HTTP)

```
=== MISSION 1 : /answer n approuve plus ===
  etat en attente   : awaiting_authorization
  /answer 'o'        -> HTTP 403 authorization_requires_token
  /answer 'oui'      -> HTTP 403 authorization_requires_token
  /answer 'yes'      -> HTTP 403 authorization_requires_token
  /answer 'ok'       -> HTTP 403 authorization_requires_token
  /answer 'autorise' -> HTTP 403 authorization_requires_token
  etat apres /answer: awaiting_authorization | grants: 1 echange(s)
  /authorize (jeton valide) -> HTTP 200 {'approved': True, 'started': True}
  etat final : completed | motif : completed
```

L'approbation n'est possible que par `/authorize` avec le jeton d'approbation
(usage unique, expiration, session, propriétaire).

---

## 6. Diff complet

### `app/orchestration/runner.py` (+51 / −17)

- `REASON_AUTHORIZATION_REQUIRES_TOKEN` (nouveau code de refus) ;
- `check_answer` ne valide plus `check_authorization` : elle lève le refus
  explicite si la demande en attente est une autorisation ;
- `answer` lève le même refus **avant** tout traitement.

### `app/interface/cli.py` (+16 / −1)

- import de `MissionAuthorizationError` ;
- le handler `/mission-answer` intercepte l'exception et n'approuve plus.

### `tests/test_answer_d1ter_fixes.py`

- les tests qui affirmaient que l'approbation sans jeton était attendue
  sont **inversés** pour exprimer le comportement attendu après correction.

### `tests/test_answer_authorization_invariant.py` (nouveau)

- 8 tests d'invariant (aucune route alternative, aucune variante de jeton).

---

## 7. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | L'asymétrie entre les deux routes est résolue pour l'**approbation**, mais `/answer` reste la voie de convenance pour les **clarifications** : le contrat de l'API web ne change pas | choix assumé (l'audit demandait la suppression du contournement, pas un changement de contrat) |
| 2 | Une mission en attente d'autorisation reçoit désormais un refus explicite (`authorization_requires_token`) à la place d'une approbation : tout client automatisé qui appuyait sur `/answer` doit être mis à jour | **changement de comportement observable** : documenté dans le rapport et signalé à Agent B |
| 3 | Les tests d'observation (`test_investigation_d1ter_answer_path.py`) ont été mis à jour pour refléter le nouveau comportement | ils ne contournent pas la protection : ils vérifient désormais que l'approbation **n'a pas** lieu |
| 4 | Aucune validation Debian 13 | environnement indisponible |

---

## 8. Interactions avec les audits Agent B

| Branche en audit | Interaction |
|------------------|-------------|
| **D1** (`3a59dae`) | la correction P1 s'appuie sur le fait que `/authorize` exige le jeton : elle **ne modifie pas** D1 ; D1 doit être fusionné avant (ou avec) ce correctif |
| **D1-bis** (`1ef4878`) | `app/interface/web.py` : le hunk touché est `answer_mission` (validation synchrone) ; D1-bis a modifié `authorize_mission` et `_handle_mission_authorize` → **hunks distincts**, pas de conflit de code |
| **D3** (`0be08cd`) | aucun fichier commun (`app/tools/*`) → pas de conflit |
| **A-α/B-α** (`25baa60`, base de la présente branche) | `app/orchestration/runner.py` : le hunk touché est `check_answer`/`answer`, distinct de `check_authorization`/`authorize` → **hunks distincts** ; le fichier est modifié par les deux branches, mais les sections sont disjointes |
| **D-B05** (`79692fe`) | `app/orchestration/runner.py` : le hunk touché est `list_missions` → **hunk distinct** |
| **D-B05-restants** (`54bd138`) | `app/orchestration/runner.py` : hunks `resume`/`_execute_loop` → **hunks distincts** |

**Ordre de fusion suggéré** : D1 → D2 → D1-bis → D3 → A-α/B-α → P1
(ce correctif) → D-B05 → D-B05-restants → frontières `read_only`.

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-answer-authorization-only` (poussée sur `origin`) |
| SHA de base | `25baa60` (`fix/miles-answer-d1ter`) |
| Fichiers modifiés | `app/orchestration/runner.py`, `app/interface/cli.py`, `tests/test_answer_d1ter_fixes.py` |
| Fichiers ajoutés | `tests/test_answer_authorization_invariant.py`, ce rapport |
| `main` / intégration | `b9b7e7d` / `69bf670` — **inchangées** |
| D1 / D2 / D1-bis / D3 / A-α·B-α | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` / `25baa60` — **inchangées** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |

---

## 10. Prochaine action

1. **Audit indépendant d'Agent B** de la branche
   `fix/miles-answer-authorization-only`, portant sur :
   - l'absence totale de contournement de P1-6-06 ;
   - la cohérence de la route `/answer` (clarifications uniquement) ;
   - les 8 tests d'invariant ;
   - l'exécution sous Debian 13.
2. **Ne pas fusionner** sans cet audit.
3. Si Agent B demande un changement de contrat (exiger le jeton sur
   `/answer`), c'est un choix d'API à trancher séparément.
