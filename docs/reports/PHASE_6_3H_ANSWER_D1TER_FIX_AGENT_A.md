# docs/reports/PHASE_6_3H_ANSWER_D1TER_FIX_AGENT_A.md — Correctifs A-α et B-α

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base de travail** : `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` (`fix/miles-policy-path-typing`, qui porte D1 + D2 + D1-bis + D3)
- **Branche de correction** : `fix/miles-answer-d1ter`
- **Rapport d'investigation** : `docs/reports/PHASE_6_3G_INVESTIGATION_D1TER_ANSWER_AGENT_A.md`
- **`main`** : `b9b7e7d` — **inchangée**
- **Intégration** : `69bf670` — **inchangée**
- **D1 / D2 / D1-bis / D3** : `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` — **inchangées**

> **Aucune fusion.** Le correctif attend l'audit indépendant d'Agent B ; les
> audits D1, D2, D1-bis et D3 sont **en cours** et ne sont pas considérés
> comme approuvés.

---

## 1. Préalables Git

| Référence | SHA annoncé | SHA réel vérifié | Conforme |
|-----------|--------------|------------------|----------|
| D1 `fix/miles-d1-web-authorization` | `3a59dae` | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` | ✔ |
| D2 `fix/miles-windows-paths` | `d3240d2` | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` | ✔ |
| D1-bis `fix/miles-d1bis-authorization-response` | `1ef4878` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | ✔ |
| D3 `fix/miles-policy-path-typing` | `0be08cd` | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` | ✔ |
| `main` | `b9b7e7d` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | ✔ |
| Intégration | `69bf670` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` | ✔ |

**Worktree d'investigation/correction** :
`C:\Users\StanC\AppData\Local\Temp\miles-answer` (branche
`fix/miles-answer-d1ter`, base `0be08cd`). Aucune branche existante n'a été
modifiée ; le checkout principal reste sur `fix/miles-d1-web-authorization`,
son artefact non suivi `tatus --short--branch` est préservé, et les bases de
données du développeur n'ont pas été écrites.

---

## 2. A-α — Réponse honnête de `POST /mission/<id>/answer`

### 2.1 Le défaut (reproduit avant correction)

`WebApp.answer_mission` validait la mission et la présence d'une demande en
attente, puis déléguait l'action à un **fil d'exécution** :

```python
started = self._start_mission_thread(
    mission_id,
    lambda mid: self.mission_runner.answer(...),
)
...
return {"mission_id": mission_id, "answered": True, "started": True}
```

Toute erreur levée **dans le fil** (`MissionAuthorizationError` : session
différente, budget d'interactions épuisé, demande expirée) était journalisée
et absorbée : la route répondait malgré tout `{"answered": true}`.

**Preuve (avant correctif, base `0be08cd`)** :

```
=== A4 : /answer depuis une AUTRE session (même utilisateur) ===
   reponse : {'mission_id': ..., 'answered': True, 'started': True}   <- mensonger
   etat de la mission : awaiting_authorization                        <- refus réel
   grants emis        : 0
```

### 2.2 Le correctif

**`app/orchestration/runner.py`** — nouvelle méthode
`MissionRunner.check_answer(...)` : elle factorise les contrôles de
`answer` **sans traiter la réponse**, sur le modèle de
`check_authorization` (correction D1-bis). Contrôles :

1. la mission existe et n'est **pas dans un état terminal** ;
2. le demandeur est le **propriétaire** de la mission ;
3. une **demande est en attente** ;
4. le **budget d'interactions** n'est pas épuisé ;
5. si la demande en attente est une **autorisation**, les mêmes contrôles
   que l'octroi d'un grant s'appliquent (expiration de la demande, session
   du demandeur) — via `check_authorization`, **sans duplication de règles**.

`answer()` appelle désormais `check_answer()` : la source de vérité est
unique, et l'interface web ne peut plus valider « à côté » de l'action.

**`app/interface/web.py`** — `answer_mission` appelle `check_answer` de façon
**synchrone** avant de lancer le fil ; en cas de refus, elle renvoie
`{"error": …, "reason": …}` (jamais de jeton, de session ni de secret dans
le corps). Le gestionnaire `_handle_mission_answer` renvoie **409** pour le
cas « mission occupée » (cohérence avec `/authorize`) et **403** pour les
autres refus.

**Le contrat de la route est inchangé** : le client transmet une réponse
texte, **aucun jeton n'est exigé** (l'option A-β n'est **pas** appliquée).

### 2.3 Codes HTTP et corps

| Cas | HTTP | Corps |
|-----|------|-------|
| Réponse traitée | **200** | `{"mission_id": …, "answered": true, "started": true}` |
| Autre session | **403** | `{"error": "Cette mission est liee a une autre session.", "reason": "session_mismatch"}` |
| Autre utilisateur | **403** | `{"error": "Mission inconnue : …", "reason": "mission_not_found"}` |
| Mission terminée | **403** | `{"error": "La mission est deja terminee.", "reason": "mission_finished"}` |
| Aucune demande en attente | **403** | `{"error": "Aucune demande en attente pour cette mission.", "reason": "no_pending_authorization"}` |
| Demande expirée | **403** | `{"error": "La demande d'autorisation est expiree.", "reason": "expired_approval_token"}` |
| Budget d'interactions épuisé | **403** | `{"error": "Budget d'interactions de la mission épuisé.", "reason": "interaction_budget_exceeded"}` |
| Mission occupée | **409** | `{"error": "La mission est encore en cours de traitement : …", "reason": "mission_busy"}` |
| Réponse vide | **403** | `{"error": "Réponse vide."}` |

---

## 3. B-α — Suppression de la fenêtre de course D1-ter

### 3.1 Le défaut (reproduit avant correction)

Le compte rendu d'une mission était construit **même pour une mission en
attente**, et la construction demandait l'**analyse qualitative** au
fournisseur IA : le fil de la mission restait occupé le temps de l'appel, et
une autorisation reçue pendant cette fenêtre était **silencieusement ignorée**
(`_start_mission_thread` ne relance pas une mission dont un fil est vivant).

**Preuve (avant correctif, fournisseur simulé, aucun appel réseau)** :

```
=== B3 : la mission en attente demande-t-elle une analyse ? ===
   etat      : awaiting_authorization
   faits     : ["Résultat de l'étape s1 : 2 caractère(s)."]
   appels au fournisseur : 2
      - Tu proposes un plan d'observation pour MILES. …
      - Tu analyses les faits observés par une mission MILES. …   <- l'analyse
```

### 3.2 Le correctif (une ligne, dans `_execute_loop`)

```python
analyste = self._analyze if mission.state.is_terminal else None
mission.report = self._report_builder.build(mission, analyste)
```

L'analyse n'est demandée que si la mission a atteint un **état terminal**.
Le fil de la mission se termine donc dès la demande d'autorisation : la
fenêtre disparaît.

**Effet de bord assumé** : le compte rendu **provisoire** d'une mission en
attente ne comporte plus de section « Analyse qualitative ». Le compte
rendu **définitif**, produit à la fin de la mission, la conserve (vérifié par
test). Le reste du rapport (faits, erreurs, étapes non terminées, budget,
motif d'arrêt) est inchangé.

Le **409 reste en place** comme protection : si une autre action occupe
encore la mission (cas distinct de la fenêtre D1-ter), la réponse reste
explicite et le client peut réessayer.

---

## 4. Tests

Fichier ajouté : `tests/test_answer_d1ter_fixes.py` — **18 tests** de
régression (non destructifs : outils simulés, répertoires temporaires,
fournisseur **simulé**, aucun appel réseau, aucun coût, aucune donnée réelle).

| # | Test | Ce qu'il fixe |
|---|------|----------------|
| 1 | `test_reponse_valide_acceptee_et_mission_avancee` | réponse positive **et** mission poursuivie |
| 2 | `test_autre_session_refusee_explicitement` | **403** + `session_mismatch`, 0 grant |
| 3 | `test_mission_terminee_refusee_explicitement` | **403** + `mission_finished` |
| 4 | `test_aucune_demande_en_attente_refusee_explicitement` | **403** + `no_pending_authorization` |
| 5 | `test_mission_inconnue_refusee_explicitement` | **403** + `mission_not_found` |
| 6 | `test_autre_utilisateur_refuse` | refus, mission invisible |
| 7 | `test_demande_expiree_refusee_explicitement` | **403** (erreur auparavant avalée dans le fil) |
| 8 | `test_budget_d_interactions_epuise_refuse_explicitement` | **403** (erreur auparavant avalée dans le fil) |
| 9 | `test_reponse_vide_refusee` | refus explicite |
| 10 | `test_le_contrat_de_answer_est_inchange` | **aucun jeton exigé** (A-β non appliqué) |
| 11 | `test_les_reponses_ne_divulguent_ni_jeton_ni_session` | aucun jeton / session / CSRF dans les corps |
| 12 | `test_les_codes_http_sont_explicites` | 200 / 403 / 409 au niveau HTTP |
| 13 | `test_pas_d_analyse_pendant_l_attente` | **B-α** : aucune analyse demandée pendant l'attente |
| 14 | `test_le_compte_rendu_final_conserve_l_analyse` | le compte rendu final garde l'analyse |
| 15 | `test_le_compte_rendu_provisoire_est_coherent` | le rapport provisoire reste cohérent |
| 16 | `test_une_autorisation_n_est_plus_ignoree` | l'autorisation reçue juste après est appliquée (pas de 409) |
| 17 | `test_le_409_reste_en_place_comme_filet` | le 409 subsiste si un conflit temporaire est possible |
| 18 | `test_le_reessai_ne_duplique_ni_travail_ni_budget` | réessai : ni étape, ni appel d'outil, ni échange dupliqué, aucun budget réinitialisé |

### 4.1 Les tests échouent-ils sans le correctif ?

Vérifié explicitement :

| Situation | Résultat |
|-----------|----------|
| Correctifs appliqués | `Ran 18 tests — OK` |
| **Revert de `app/interface/web.py`** (A-α retiré) | **`FAILED (failures=7)`** : les 7 tests de refus explicite (autre session, mission terminée, aucune demande, mission inconnue, demande expirée, budget épuisé, codes HTTP) |
| **Neutralisation de B-α** (analyse pour toute mission) | **`FAILED (failures=1)`** : `test_pas_d_analyse_pendant_l_attente` |

Le revert de `app/orchestration/runner.py` complet n'a pas été exploitable
tel quel : `check_answer` n'existant plus, l'appel de l'interface web
lèverait une `AttributeError` ; la neutralisation ciblée de B-α et le revert
de l'interface web suffisent à démontrer la couverture.

### 4.2 Commandes et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_answer_d1ter_fixes` | **18 tests, 0 échec** (5,4 s) |
| `python -m unittest tests.test_answer_d1ter_fixes` *(revert web.py)* | **7 échecs** |
| `python -m unittest tests.test_answer_d1ter_fixes` *(sans B-α)* | **1 échec** |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_web_authorization` (D1) | 6 tests, 0 échec |
| `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| `python -m unittest tests.test_web_security` | 33 tests, 0 échec |
| `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| `python -m unittest tests.test_windows_paths` (D3) | 21 tests, 0 échec |
| `python -m unittest tests.test_tool_policy` | 11 tests, 0 échec |
| `python -m unittest tests.test_path_security` | 21 tests, 0 échec, 3 ignorés |
| `python -m unittest tests.test_tool_engine` | 26 tests, 0 échec |
| `python -m unittest tests.test_tool_integration` | 40 tests, 0 échec |
| `python -m unittest tests.test_tool_resources` | 8 tests, 0 échec, 1 ignoré |
| `python -m unittest discover -s tests` | **633 tests, 0 échec, 4 ignorés** (90,2 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (22,3 s) |

Les tests ignorés sont des **limites de plateforme Windows** (liens
symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13.

---

## 5. Diff complet

### 5.1 `app/orchestration/runner.py` (+82 / −17)

- `REASON_INTERACTION_BUDGET_EXCEEDED` (nouveau code de refus).
- **nouvelle** méthode `check_answer(...)` (validation synchrone d'une
  réponse) ; `answer(...)` l'appelle (source de vérité unique).
- B-α : l'analyse qualitative n'est demandée que pour un état terminal.

### 5.2 `app/interface/web.py` (+35 / −4)

- import de la nouvelle constante de raison ;
- `answer_mission` : validation synchrone via `check_answer`, réponses
  explicites avec `reason`, message de contrat (aucun jeton exigé) ;
- `_handle_mission_answer` : 409 pour « mission occupée », 403 pour les
  autres refus.

### 5.3 `tests/test_answer_d1ter_fixes.py` (nouveau)

18 tests de régression (voir §4).

**Aucun autre fichier de production n'est modifié** : ni la politique de
sécurité, ni les permissions, ni le confinement des chemins
(`app/security/paths.py` intact), ni le planificateur, ni les outils.

---

## 6. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | **Fenêtre résiduelle** : si une autre action occupe encore la mission (cas distinct de D1-ter), l'autorisation est ignorée → **409**, client doit réessayer | le 409 est conservé comme filet ; le réessai ne duplique rien (test 18) |
| 2 | **Course résiduelle** : entre la validation synchrone et l'action dans le fil, l'état de la mission peut changer (fenêtre étroite) → l'action peut échouer dans le fil → la réponse reste positive | **inchangé** (même résidualité que sur `/authorize` après D1-bis) ; l'action refusée n'accorde rien |
| 3 | **Compte rendu provisoire sans analyse** : le rapport d'une mission en attente n'a plus de section « Analyse qualitative » | effet de bord **assumé et documenté** ; le rapport final la conserve (test 14) |
| 4 | **`/answer` approuve toujours sans jeton** (A-β non appliqué) | choix assumé : le jeton n'est pas un second facteur contre le propriétaire ; l'incohérence entre les deux routes subsiste → **documentée**, à arbitrer par Agent B |
| 5 | `check_answer` change le comportement de `runner.answer` pour une mission **inconnue** (avant : `None` ; maintenant : `MissionAuthorizationError`) | les appelants (CLI et web) pré-contrôlent déjà ces cas ; les tests existants le confirment (73/73, 35/35) |
| 6 | Aucune validation sous **Debian 13** | environnement indisponible |

---

## 7. Interactions avec les audits Agent B en cours

| Branche en audit | Interaction |
|------------------|-------------|
| **D1** (`3a59dae`) | le correctif D1 (grant vérifié avec `mission.session_id`) est **la condition** du refus cross-session : sans lui, l'approbation d'une autre session émettrait un grant inutilisable et consommerait un échange. **Le correctif D1 doit être fusionné avant (ou avec) celui-ci** — l'ordre D1 → D2 → D1-bis → D3 → A-α/B-α est conservé. |
| **D2** (`d3240d2`) | aucun fichier commun (`app/orchestration/planner.py` vs `runner.py`/`web.py`) → pas de conflit |
| **D1-bis** (`1ef4878`) | **conflit de contexte possible** : D1-bis a modifié `app/orchestration/runner.py` (ajout de `check_authorization`) **et** `app/interface/web.py` (validation synchrone de `/authorize`). Le présent correctif modifie les deux fichiers également, mais dans des **hunks distincts** : `runner.py` → `check_answer` + `answer` (l. ~296-400) et le rapport (l. ~888) ; `web.py` → `answer_mission` (l. ~379) et `_handle_mission_answer` (l. ~1375). Le hunk D1-bis sur `web.py` porte sur `authorize_mission` (l. ~291) et sur les imports (l. ~27) → **conflit possible sur le bloc d'imports** (les deux branches ajoutent des constantes `REASON_*`) : à résoudre manuellement, sans risque sémantique. |
| **D3** (`0be08cd`) | aucun fichier commun (`app/tools/*`) → pas de conflit. La base retenue est D3, donc cette branche **contient** D3. |

Le test d'audit d'Agent B qui **inspecte le code source** de
`WebApp.authorize_mission` (`test_autorisation_de_mission_exige_identite_et_jeton`
— il exige la présence de `session`, `owner_user_id` et `approval_token`)
n'est **pas** concerné : `authorize_mission` n'est pas modifié par le présent
correctif ✓ (vérifié : les 70 tests d'audit restent verts).

---

## 8. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-answer-d1ter
git pull --ff-only

# A-alpha : l another session est refusee explicitement
python -m unittest tests.test_answer_d1ter_fixes -v

# B-alpha : plus d analyse pendant l attente
python -m unittest tests.test_answer_d1ter_fixes.TestFenetreD1terSupprimee -v

# non-regression
python -m unittest tests.test_mission_authorize_response
python -m unittest tests.test_web_security_phase6_1 tests.test_web_security
python -m unittest discover -s tests
```

Comportement observable sur le serveur web :

```
POST /mission/<id>/answer   (session B, même utilisateur)
  avant : HTTP 200 {"answered": true, "started": true}      <- mensonger
  après : HTTP 403 {"error": "Cette mission est liee a une autre session.",
                    "reason": "session_mismatch"}

POST /mission/<id>/answer   (session propriétaire)
  avant : HTTP 200 {"answered": true, "started": true}
  après : HTTP 200 {"answered": true, "started": true}      <- inchangé
```

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-answer-d1ter` (poussée sur `origin`) |
| SHA de base | `0be08cd` (`fix/miles-policy-path-typing`) |
| Fichiers modifiés | `app/orchestration/runner.py`, `app/interface/web.py` |
| Fichiers ajoutés | `tests/test_answer_d1ter_fixes.py`, ce rapport |
| `main` | `b9b7e7d` — **inchangée** |
| Intégration | `69bf670` — **inchangée** |
| D1 / D2 / D1-bis / D3 | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` — **inchangées** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |

---

## 10. Prochaine action

1. **Audit indépendant d'Agent B** de la branche `fix/miles-answer-d1ter` :
   - la validation synchrone est-elle complète (identité, session,
     propriété, état, expiration, budget) ?
   - le contrat de `/answer` est-il réellement inchangé ?
   - l'effet de bord du rapport provisoire est-il acceptable ?
   - exécution sous Debian 13.
2. **Décision à trancher** : l'option **A-β** (exiger le jeton sur
   `/answer`) reste ouverte ; elle **change le contrat de l'API web** et n'a
   pas été appliquée.
3. **Ne pas fusionner** avant cet audit ; l'ordre de fusion D1 → D2 → D1-bis
   → D3 → A-α/B-α est à respecter (le refus cross-session repose sur le
   contrôle de session de D1-bis).
