# docs/reports/PHASE_6_3K_READ_ONLY_TRUST_BOUNDARIES_AGENT_A.md — Frontières de confiance de la propriété `read_only`

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Référence de lecture** : `54bd13859602ab007d955115f6273dc2ca9fdb6a` (`fix/miles-results-persistence`)
- **Branche de tests** : `test/miles-read-only-trust-boundaries` — `155dab3` (11 tests, **aucune modification de production**)
- **Branche de correctif** : `fix/miles-read-only-prudent-type` — à partir de `155dab3` (correctif minimal + 1 test de régression)
- **`main`** : `b9b7e7d` — **inchangée** · **Intégration** : `69bf670` — **inchangée**

> **Aucune fusion.** Les audits D1, D2, D1-bis, D3, A-α/B-α, D-B05 et
> D-B05-restants sont **en cours**.

---

## 1. Préalables Git

| Branche | SHA réel vérifié |
|---------|------------------|
| `origin/fix/miles-results-persistence` (référence) | `54bd13859602ab007d955115f6273dc2ca9fdb6a` ✔ |
| `origin/fix/miles-mission-persistence-owner` | `79692fe97bf8b5cef0ab3d7f8bb4db507555d0fc` ✔ |
| `origin/fix/miles-answer-d1ter` | `25baa60e2691f54900111a11194cf7e186419050` ✔ |
| `origin/fix/miles-policy-path-typing` (D3) | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` ✔ |
| `origin/fix/miles-d1bis-authorization-response` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` ✔ |
| `origin/fix/miles-windows-paths` (D2) | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` ✔ |
| `origin/fix/miles-d1-web-authorization` (D1) | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` ✔ |
| `origin/main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` ✔ |
| `origin/integration/miles-phases-5-6-6-1` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` ✔ |
| `origin/audit/agent-b-phase6-1-web-security-review` | `fd25a26d291e58d93c621a1668a51cd8988b02ea` (inchangé) |

Deux worktrees dédiés : `Temp/miles-trust` (branche de tests) et
`Temp/miles-trustfix` (branche de correctif). Le checkout principal reste
sur `fix/miles-d1-web-authorization`, artefact non suivi
`tatus --short--branch` **préservé**, bases du développeur intactes.

---

## 2. Examen préalable : des tests équivalents existent-ils déjà ?

Recherche sur l'ensemble de `tests/` :

| Sujet | Tests existants | Verdict |
|-------|------------------|---------|
| Propriété `read_only` | `test_mission_results_recovery.py` (déclaration + rejouée/non rejouée) | couvre le **comportement**, pas les **frontières de confiance** |
| Le plan ne peut pas choisir un outil interdit | `test_mission_orchestrator.py::test_plan_ia_refuse_outil_non_autorise` / `..._refuse_outil_inconnu` | couvre le `tool_id`, pas les **propriétés** de l'outil |
| Le plan ne peut pas injecter de paramètre | `..._refuse_parametre_non_declare` / `..._refuse_parametre_mal_typé` | couvre les **paramètres**, pas une propriété de sécurité de l'outil |
| Immuabilité du schéma d'outils | aucune | **manquant** |
| Le modèle ne peut pas déclarer une propriété de sécurité | aucune | **manquant** |
| Propriété absente / invalide | aucune | **manquant** |

→ **Les tests demandés n'existaient pas** : ils sont réellement nouveaux.

---

## 3. Les frontières réelles (vérifiées sur le code, pas supposées)

| # | Frontière | Mécanisme réel | Verdict |
|---|-----------|----------------|---------|
| F1 | Le modèle peut-il déclarer lui-même un outil `read_only` ? | `PlanStep` ne possède **aucune** propriété `read_only` ; `PlanStep.from_dict` ignore les clés inconnues ; le runner lit la propriété dans le **registre** | **déjà protégé** |
| F2 | Un plan peut-il modifier les propriétés de sécurité d'un outil enregistré ? | `ToolDefinition` est un dataclass **figé** (`frozen=True`) : toute mutation lève `FrozenInstanceError` ; le registre appartient à l'application | **déjà protégé** |
| F3 | Les propriétés viennent-elles de la définition approuvée ? | `MissionRunner._is_side_effect_free` interroge `self.tool_service.registry.get_tool(tool_id)` — le registre de l'application, **jamais** la mission ni le plan | **déjà protégé** |
| F4 | Un outil inconnu / non identifié peut-il être rejoué ? | `get_tool` renvoie `None` → aucun rejeu | **déjà protégé** |
| F5 | Une propriété **absente** entraîne-t-elle un comportement prudent ? | `getattr(tool, "read_only", False)` → `False` → pas de rejeu | **déjà protégé** |
| F6 | Une propriété **invalide** (mauvais type) entraîne-t-elle un comportement prudent ? | `bool(getattr(tool, "read_only", False))` → **une valeur non booléenne « vraie » passe pour une déclaration** | **DÉFAUT CONFIRMÉ** |

### 3.1 Le défaut, mesuré

```
   valeur de read_only -> comportement de la reprise
   True     (bool)    -> REJEU (déclaration)
   False    (bool)    -> prudent
   None     (NoneType)-> prudent
   'oui'    (str)     -> REJEU (non prudent)   <-- DEFAUT
   'false'  (str)     -> REJEU (non prudent)   <-- DEFAUT (pire cas : l'inverse du sens)
   1        (int)     -> REJEU (non prudent)   <-- DEFAUT
   0        (int)     -> prudent
   []       (list)    -> prudent
   ''       (str)     -> prudent
   outil inconnu     -> prudent
```

**Analyse de l'exploitabilité** :

- la déclaration est posée par **l'application** (schéma des outils), le
  modèle ne peut pas l'influencer (F1, F2) → **aucune élévation de
  privilège possible par le modèle** ;
- le défaut est une **défaillance du principe de prudence** : une
  déclaration malformée (chaîne issue d'une configuration, valeur-truthy
  introduite par une refonte) autoriserait silencieusement la **reprise
  automatique d'une opération susceptible d'avoir un effet** — exactement ce
  que la règle « ne reprendre que ce dont l'absence d'effet est
  démontrable » interdit ;
- le cas `"false"` (chaîne) est le plus défavorable : la valeur **signifie
  « faux »** mais est traitée comme une declaration « sans effet ».

**Correction minimale** (une ligne) : ne reconnaître la déclaration que si
la valeur est **exactement** le booléen `True` :

```python
return getattr(tool, "read_only", False) is True
```

Tout le reste (absente, `None`, chaîne, entier, liste) redevient prudent ✓.

---

## 4. Tests livrés

### 4.1 Branche de tests `test/miles-read-only-trust-boundaries` (11 tests)

`tests/test_read_only_trust_boundaries.py` — **aucune modification de code
de production**. Ces tests **documentent** les protections déjà en place
(ils passent sur le code actuel) :

| # | Test | Frontière |
|---|------|-----------|
| 1 | `test_le_plan_ne_comporte_aucune_propriete_read_only` | F1 : `PlanStep` n'a pas de propriété `read_only` ; une déclaration du modèle est ignorée |
| 2 | `test_une_declaration_du_modele_est_ignoree_a_la_reprise` | F1 de bout en bout : un plan qui prétend `read_only: true` ne déclenche **aucune** reprise |
| 3 | `test_la_definition_d_un_outil_est_immuable` | F2 : `ToolDefinition` est figé (`FrozenInstanceError`) |
| 4 | `test_un_parametre_read_only_non_declare_est_refuse` | F2 : le plan ne peut pas non plus passer `read_only` en *paramètre* (paramètre non déclaré → refus) |
| 5 | `test_une_propriete_absente_ne_declenche_pas_de_rejeu` | F5 : propriété absente → prudent |
| 6 | `test_une_propriete_a_none_ne_declenche_pas_de_rejeu` | F5 : `None` → prudent |
| 7 | `test_la_propriete_est_lue_dans_le_registre` | F3 : la décision vient du registre (application) |
| 8 | `test_la_mission_ne_peut_pas_influer_sur_la_decision` | F3 : une mission persistée ne peut pas rendre un outil sans effet |
| 9 | `test_un_outil_non_identifie_n_est_jamais_rejoue` | F4 : outil inconnu → jamais rejoué |
| 10 | `test_un_outil_non_declare_par_l_application_n_est_jamais_rejoue` | F4 : outil enregistré sans déclaration → jamais rejoué |
| 11 | `test_une_propriete_inconnue_est_ignoree` | propriété supplémentaire (`side_effect_free`) sans effet |

### 4.2 Branche de correctif `fix/miles-read-only-prudent-type`

Le correctif minimal (une ligne) **plus** le test de régression qui expose le
défaut :

| # | Test | Rôle |
|---|------|------|
| 12 | `test_une_propriete_de_type_incorrect_ne_declenche_pas_de_rejeu` | valeurs `"oui"`, `"false"`, `1`, `-1`, `["oui"]`, `{"read_only": True}` → **prudent** |

---

## 5. Résultats exacts

| Commande / situation | Résultat |
|----------------------|----------|
| `python -m unittest tests.test_read_only_trust_boundaries` *(branche de tests)* | **11 tests, 0 échec** (0,5 s) |
| `python -m unittest tests.test_read_only_trust_boundaries` *(branche de correctif)* | **12 tests, 0 échec** (0,8 s) |
| **revert de `app/orchestration/runner.py`** (branche de correctif) | **`FAILED (failures=6)`** : les 6 valeurs de type incorrect déclenchent une reprise automatique → **le défaut est bien couvert** |
| `python -m unittest discover -s tests` *(branche de tests)* | **665 tests, 0 échec, 4 ignorés** (101,9 s) |
| `python -m unittest discover -s tests` *(branche de correctif)* | **666 tests, 0 échec, 4 ignorés** (135,7 s) |
| `tests.test_mission_results_recovery` / `test_mission_persistence_owner` | 12 / 9 tests, 0 échec |
| `tests.test_mission_orchestrator` / `test_mission_bounds` / `test_mission_authorize_response` | 73 / 20 / 20 tests, 0 échec |
| `tests.test_web_security_phase6_1` / `test_tool_engine` / `test_tool_integration` / `test_tool_registry` / `test_tool_policy` / `test_policy_path_typing` | 35 / 26 / 40 / 6 / 11 / 40 tests, 0 échec |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (26,0 s) |

Les tests ignorés (4 + 2) sont des **limites de plateforme Windows**
(liens symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13.
**Aucune validation Debian 13** n'a été possible (environnement
indisponible). **Aucun appel API payant**, aucune donnée réelle lue ni
écrite : les tests utilisent des outils simulés, un magasin temporaire et un
compteur d'appels par fichier (le moteur exécute les outils dans un
processus séparé, la mémoire n'est pas partagée).

---

## 6. Diff

### Branche de tests `test/miles-read-only-trust-boundaries`

```
 tests/test_read_only_trust_boundaries.py | 400 +++++++++++++++++++++++++
 1 file changed, 400 insertions(+)
```

**Aucun code de production modifié.**

### Branche de correctif `fix/miles-read-only-prudent-type`

```
 app/orchestration/runner.py           | 11 ++++++++++-
 tests/test_read_only_trust_boundaries.py | 26 ++++++++++++
 2 files changed, 36 insertions(+), 1 deletion(-)
```

Le correctif de production (11 lignes, dont 8 de documentation) :

```python
-        return bool(tool is not None and getattr(tool, "read_only", False))
+        if tool is None:
+            return False
+        return getattr(tool, "read_only", False) is True
```

---

## 7. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | La déclaration `read_only` reste une **affirmation** de l'application | le défaut est « à effet » (faux par défaut) ; la correction ne change que le traitement des **valeurs malformées** |
| 2 | Un outil déclaré sans effet mais qui en a un (erreur de l'application) serait rejoué | inchangé : c'est la déclaration qui est en cause, pas le type de la valeur ; un test vérifie la cohérence de la déclaration avec `READ_ONLY_TOOLS` |
| 3 | La reprise d'une étape de lecture relit la donnée | résultat plus frais, pas faux ; documenté |
| 4 | Le budget global peut être atteint par la reprise | comportement voulu (le budget global est la borne) |
| 5 | Un outil à effet interrompu laisse la mission en `partial` avec une étape incertaine | comportement explicite et signalé |
| 6 | Aucune validation Debian 13 | environnement indisponible |

**Aucune nouvelle vulnérabilité n'est inventée** : les frontières F1 à F5
étaient déjà garanties par l'architecture (donc non exploitables) ; seul F6
(une valeur de type incorrect) était réellement en défaut, et il l'est
seulement pour l'application, jamais pour le modèle.

---

## 8. Interactions avec les audits en cours

| Branche | Interaction |
|---------|-------------|
| **D1** (`3a59dae`), **D2** (`d3240d2`), **D1-bis** (`1ef4878`), **A-α/B-α** (`25baa60`), **D-B05** (`79692fe`), **D-B05-restants** (`54bd138`) | `app/orchestration/runner.py` : le hunk touché est `_is_side_effect_free` (nouveau, propre à la reprise) → **aucun conflit de code** |
| **D3** (`0be08cd`) | `app/tools/registry.py` / `builtin.py` : **non touchés** par cette mission → pas de conflit |
| **Audit contradictoire** (`fd25a26`) | ne porte que sur l'arbre Phase 5/6/6.1 ; ne contredit aucun constat et ne signale aucune régression → **aucune suspension appliquée** |

La branche de correctif est empilée sur la branche de tests
(`155dab3` → correctif) : à la fusion, l'ordre est
`test/miles-read-only-trust-boundaries` puis
`fix/miles-read-only-prudent-type` (ou l'inverse, le second contenant le
premier).

---

## 9. Vérification manuelle

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-read-only-prudent-type
git pull --ff-only

python -m unittest tests.test_read_only_trust_boundaries -v

# preuve du défaut (avant le correctif) :
git stash push app/orchestration/runner.py
python -m unittest tests.test_read_only_trust_boundaries   # 6 échecs
git stash pop
```

---

## 10. État Git

| Élément | Valeur |
|---------|--------|
| Branche de tests | `test/miles-read-only-trust-boundaries` → `155dab3` (poussée) |
| Branche de correctif | `fix/miles-read-only-prudent-type` (poussée), base `155dab3` |
| SHA de base (référence de lecture) | `54bd138` (`fix/miles-results-persistence`) |
| Fichiers modifiés (correctif) | `app/orchestration/runner.py` ; `tests/test_read_only_trust_boundaries.py` |
| `main` / intégration | `b9b7e7d` / `69bf670` — **inchangées** |
| D1 / D2 / D1-bis / D3 / A-α·B-α / D-B05 / D-B05-restants | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` / `25baa60` / `79692fe` / `54bd138` — **inchangées** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |

---

## 11. Prochaine action

1. **Audit indépendant d'Agent B** des deux branches :
   - la branche de tests (frontières de confiance) ;
   - la branche de correctif (traitement prudent des valeurs malformées).
2. Décider si la déclaration `read_only` doit devenir un **énumération**
   stricte plutôt qu'un booléen (ex. `ToolEffect.NONE` / `READ_ONLY`) : cela
   supprimerait par construction toute valeur malformée. Non fait ici : le
   changement de type est plus large que le correctif minimal demandé.
3. **Ne pas fusionner** sans décision explicite.
