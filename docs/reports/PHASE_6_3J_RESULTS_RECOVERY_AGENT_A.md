# docs/reports/PHASE_6_3J_RESULTS_RECOVERY_AGENT_A.md — Persistance des résultats et reprise des missions interrompues

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base de travail (référence de lecture, non modifiée)** : `79692fe97bf8b5cef0ab3d7f8bb4db507555d0fc` (`fix/miles-mission-persistence-owner`)
- **Branche de correction** : `fix/miles-results-persistence`
- **Défauts traités** : D-B05, points restants (« `results` non persistés » et « étape `RUNNING` non reprise »)
- **`main`** : `b9b7e7d` — **inchangée** · **Intégration** : `69bf670` — **inchangée**

> **Aucune fusion.** Les audits D1, D2, D1-bis, D3, A-α/B-α et D-B05 sont
> **en cours** : ce correctif n'est pas validé.

---

## 1. Préalables Git

| Branche | SHA réel vérifié | Conforme |
|---------|------------------|----------|
| `origin/fix/miles-mission-persistence-owner` (référence) | `79692fe97bf8b5cef0ab3d7f8bb4db507555d0fc` | ✔ |
| `origin/fix/miles-answer-d1ter` | `25baa60e2691f54900111a11194cf7e186419050` | ✔ |
| `origin/fix/miles-policy-path-typing` (D3) | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` | ✔ |
| `origin/fix/miles-d1bis-authorization-response` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | ✔ |
| `origin/fix/miles-windows-paths` (D2) | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` | ✔ |
| `origin/fix/miles-d1-web-authorization` (D1) | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` | ✔ |
| `origin/main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | ✔ |
| `origin/integration/miles-phases-5-6-6-1` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` | ✔ |
| `origin/audit/agent-b-phase6-1-web-security-review` | `fd25a26d291e58d93c621a1668a51cd8988b02ea` | inchangé |

Worktree dédié : `C:\Users\StanC\AppData\Local\Temp\miles-results`. Le
checkout principal reste sur `fix/miles-d1-web-authorization`, artefact non
suivi `tatus --short--branch` **préservé**, bases du développeur intactes.

---

## 2. Diagnostic

### 2.1 Ce que `results` contient et quand il doit être conservé

Dans `_execute_loop` (runner.py), le dictionnaire `results` associe
l'identifiant d'une étape à son résultat d'outil. Il sert **uniquement** à
résoudre la source d'une étape dépendante
(`Executor.resolve_source_value`) : par exemple, l'étape « lecture de
fichier » prend le chemin du premier fichier listé par l'étape « listage ».

| Point | Constat |
|-------|---------|
| Portée | variable **locale** de `_execute_loop`, recréée à chaque `run()` |
| Écriture | `results[step.step_id] = outcome.result`, **uniquement** pour les étapes `SUCCEEDED` |
| Durée de vie utile | le temps d'une exécution de la boucle : une **reprise** repart avec un dictionnaire vide |
| Besoin réel | la valeur extraite (`results[source.step_id][key][index][field]`) : un scalaire, pas le résultat entier |

**Point clé (qui simplifie la correction)** : le résultat d'une étape est
**déjà persisté** dans le plan : `PlanStep.to_dict()` écrit `"result"` et le
magasin sérialise le plan entier en `plan_json`. Les données de
`results[step_id]` et de `step.result` sont **les mêmes**.

→ **Aucun changement de schéma n'est nécessaire** : le dictionnaire `results`
peut être **reconstruit** à partir du plan persisté. C'est la correction
retenue (elle évite une colonne de plus et une migration).

### 2.2 Effets de bord d'une étape laissée à l'état `RUNNING`

`resume()` traitait `FAILED` et `UNCERTAIN` (→ `UNCERTAIN`, non rejouées)
mais **ignorait `RUNNING`** : une étape interrompue par l'arrêt du
programme restait dans un état qui ne veut rien dire.

| Scénario de crash | État persisté | Conséquence avant correction |
|-------------------|---------------|-----------------------------|
| Arrêt du programme **pendant** l'exécution d'une étape | l'étape est `RUNNING` (elle est écrite `RUNNING` avant l'appel, le résultat n'est pas encore enregistré) | l'étape n'est ni rejouée, ni signalée ; ses étapes dépendantes ne résolvent pas leur source → **sautées** ; la mission s'achève en `partial` avec une étape « non terminée » sans explication |
| Arrêt du programme **après** l'exécution, avant la sauvegarde | l'étape est `RUNNING` dans la base, le résultat est perdu | idem, plus : le résultat observé est perdu (relecture possible) |
| Reprise d'une mission **interrompue** (pas de crash) | le résultat est dans le plan, mais `results` est vide | les étapes dépendantes sont **sautées** alors que la source est disponible : la mission perd ses dernières étapes sans raison |

**Risque de duplication** (le point critique) : rejouer une étape dont
l'action a pu produire un effet (écriture, envoi, suppression) **reproduirait
l'effet**. MILES n'expose aujourd'hui que des outils de lecture, mais le
moteur n'a **aucune garantie** que ce soit le cas pour un outil enregistré
par l'application. Le rejouage automatique ne peut donc pas être la règle
générale.

---

## 3. Conception retenue

### 3.1 Persistance des résultats — sans changement de schéma

Dans `_execute_loop`, le dictionnaire est reconstruit à partir du plan
persisted :

```python
results: Dict[str, Any] = {
    step.step_id: step.result
    for step in (mission.plan.steps if mission.plan else [])
    if step.status == StepStatus.SUCCEEDED and step.result is not None
}
```

Les étapes `SUCCEEDED` ne sont **pas** rejouées (elles ne sont plus
`PENDING`) : leurs résultats sont simplement **relus**, ce qui permet aux
étapes dépendantes de résoudre leur source ✓.

### 3.2 Reprise d'une étape interrompue — deux catégories explicites

`resume()` distingue désormais l'étape **interrompue** (`RUNNING`) :

| Catégorie | Condition | Traitement | Justification |
|-----------|-----------|-----------|---------------|
| **(a) absence d'effet démontrable** | l'outil est déclaré `read_only` dans le schéma de l'application | l'étape est **rejouée** (statut remis à `PENDING`, résultat effacé) | la déclaration est posée par l'application ; l'absence d'effet précédent est **démontrée** par elle |
| **(b) effet possible** | l'outil n'est **pas** déclaré | l'étape est marquée **`UNCERTAIN`**, **jamais** rejouée, avec une note explicite (« interrompue : résultat incertain, action non rejouée, vérification requise ») | l'action a pu produire un effet : la rejouer le doublerait |

La déclaration est **portée par l'application** (`ToolDefinition.read_only`),
**faux par défaut** : un outil non déclaré n'est **jamais** rejoué
automatiquement. Les cinq outils de lecture seule de MILES
(`status_read`, `action_datetime`, `action_workdir`, `action_list_files`,
`action_read_file`) sont déclarés sans effet — la liste existante
`READ_ONLY_TOOLS` reste la référence.

### 3.3 Ce qui n'est **pas** modifié

- le budget global : la reprise consomme une étape et un appel d'outil de
  plus (le budget reste la borne) ;
- l'isolation par propriétaire et les contrôles d'autorisation : la reprise
  passe par `runner.resume()`, qui ne contourne ni le grant ni le
  propriétaire ;
- la politique de sécurité, le confinement des chemins, les routes
  d'autorisation : **aucun changement**.

---

## 4. Diff complet

| Fichier | Modification | Volume |
|---------|--------------|--------|
| `app/orchestration/runner.py` | reconstruction de `results` depuis le plan persisté ; traitement explicite des étapes `RUNNING` dans `resume()` ; nouvelle méthode `_is_side_effect_free()` | +48 / −1 |
| `app/tools/registry.py` | `ToolDefinition.read_only: bool = False` (+ documentation) | +13 / −2 |
| `app/tools/builtin.py` | `read_only=True` sur les cinq outils de lecture seule | +5 |
| `tests/test_mission_results_recovery.py` | **nouveau** — 12 tests | +380 |

**Aucun changement de schéma SQLite** : la correction de la persistance
repose sur des données déjà stockées.

---

## 5. Tests

`tests/test_mission_results_recovery.py` — **12 tests**, déterministes
(outils simulés, magasin temporaire, **compteur d'appels par fichier** car le
moteur exécute les outils dans un processus séparé, aucun fournisseur, aucune
donnée réelle).

| # | Test | Couverture demandée |
|---|------|---------------------|
| 1 | `test_les_resultats_sont_persistes_avec_la_mission` | **persistance et rechargement des résultats** |
| 2 | `test_une_mission_reprise_resout_les_sources` | l'étape dépendante n'est plus sautée |
| 3 | `test_une_mission_reprise_dans_un_nouveau_processus_aboutit` | **redémarrage** : les résultats relus suffisent, la source n'est pas rejouée |
| 4 | `test_une_etape_sans_effet_interrompue_est_rejouee` | **interruption pendant une étape RUNNING** (catégorie a) |
| 5 | `test_une_etape_avec_effet_interrompue_n_est_pas_rejouee` | catégorie (b) : **action non rejouée**, étape incertaine, vérification exigée |
| 6 | `test_les_budgets_restent_coherents_apres_reprise` | **cohérence des compteurs et budgets** |
| 7 | `test_une_mission_terminee_n_est_pas_rejouee` | **redémarrage avec une mission terminée** |
| 8 | `test_aucun_outil_n_est_decl_double` | **absence de double exécution** |
| 9 | `test_les_outils_de_lire_seule_sont_declares_sans_effet` | cohérence de la déclaration avec `READ_ONLY_TOOLS` |
| 10 | `test_un_outil_non_declare_n_est_pas_sans_effet` | le défaut est « à effet » |
| 11 | `test_migration_depuis_le_schema_precedent` | **migration depuis le schéma précédent** (base sans `owner_user_id`) |
| 12 | `test_isolation_des_proprietaires_apres_reprise` | **isolation des propriétaires** |

### 5.1 Les tests échouent-ils sans le correctif ?

| Situation | Résultat |
|-----------|----------|
| Correctifs appliqués | `Ran 12 tests — OK` |
| **Revert de `app/orchestration/runner.py`** | **`FAILED (failures=4)`** : `test_une_mission_reprise_dans_un_nouveau_processus_aboutit`, `test_une_etape_sans_effet_interrompue_est_rejouee`, `test_une_etape_avec_effet_interrompue_n_est_pas_rejouee`, `test_aucun_outil_n_est_decl_double` |

Les 4 échecs sont exactement ceux qui décrivent les deux défauts ; les
autres vérifient des propriétés acquises (budgets, migration, isolation,
déclaration) et restent verts.

### 5.2 Scénarios avant/après

| Scénario | Avant | Après |
|----------|-------|-------|
| Mission reprise après redémarrage, l'étape source est réussie | l'étape dépendante est **sautée** (« résultat de l'étape s1 indisponible »), la mission finit en `partial` | l'étape dépendante **exécute** l'outil avec la valeur extraite ; la mission **aboutit** |
| Étape interrompue (`RUNNING`), outil de lecture | l'étape reste `RUNNING` : ni rejouée ni signalée | l'étape est **rejouée** (outil déclaré sans effet) et la mission se poursuit |
| Étape interrompue (`RUNNING`), outil à effet possible | l'étape reste `RUNNING` : ambiguïté silencieuse | l'étape est marquée **incertaine**, **jamais rejouée**, avec « vérification requise » ; elle figure dans « Étapes non terminées » |
| Mission terminée, puis `resume()` | aucun effet | aucun effet, **aucun appel d'outil** (aucune double exécution) |

### 5.3 Commandes et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_mission_results_recovery` | **12 tests, 0 échec** (5,0 s) |
| `python -m unittest tests.test_mission_results_recovery` *(revert runner.py)* | **4 échecs** |
| `python -m unittest tests.test_mission_persistence_owner` (D-B05) | 9 tests, 0 échec |
| `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_web_authorization` (D1) | 6 tests, 0 échec |
| `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| `python -m unittest tests.test_tool_engine` / `test_tool_integration` / `test_tool_policy` | 26 / 40 / 11 tests, 0 échec |
| `python -m unittest tests.test_policy_path_typing` (D3) / `test_windows_paths` (D2) | 40 / 21 tests, 0 échec |
| `python -m unittest tests.test_path_security` | 21 tests, 0 échec, 3 ignorés |
| `python -m unittest discover -s tests` | **654 tests, 0 échec, 4 ignorés** (125,3 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (28,6 s) |

Les tests ignorés (4 + 2 + 3) sont des **limites de plateforme Windows**
(liens symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13.
**Aucune validation Debian 13** n'a été possible (environnement
indisponible), comme pour les missions précédentes. Aucun appel API payant,
aucune donnée réelle lue ni écrite.

---

## 6. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | La déclaration `read_only` est une **affirmation** de l'application : si elle est fausse pour un outil donné, l'étape interruptible sera rejouée | le défaut est « à effet » (faux par défaut) ; la déclaration est explicite et testée ; c'est le même modèle de confiance que `required_permissions` |
| 2 | La reprise d'une étape de lecture **relit** la donnée (le fichier a pu changer entre l'interruption et la reprise) | le résultat est plus frais, pas faux ; l'étape est marquée « reprise après interruption » |
| 3 | Le budget global peut être atteint par la reprise (une étape et un appel de plus) | c'est le comportement voulu : le budget global reste la borne ; la mission s'arrête alors avec `step_budget_exceeded` |
| 4 | Les résultats des étapes sont déjà persistés dans le plan (ils y étaient déjà) : la base ne grossit pas | aucun changement de volume de données |
| 5 | Un outil à effet **interrompu** laisse la mission en `partial` avec une étape incertaine | comportement explicite et signalé ; l'utilisateur doit vérifier l'effet |
| 6 | La reprise ne restaure pas les *étapes* en attente d'autorisation (elles sont marquées par le runner) | inchangé |
| 7 | Aucun test sous Debian 13 | environnement indisponible |

---

## 7. Interactions avec les audits en cours

| Branche | Interaction |
|---------|-------------|
| **D1** (`3a59dae`) | aucun fichier commun (`runner.py` : hunk `resume()`/`_execute_loop`/`_is_side_effect_free`, distinct de `_ensure_authorization`) → pas de conflit |
| **D2** (`d3240d2`) | aucun fichier commun (`planner.py`) → pas de conflit |
| **D1-bis** (`1ef4878`) | `runner.py` : hunk distinct (`check_answer`/`answer` vs `resume`/`_execute_loop`) → pas de conflit ; `web.py` : non touché |
| **D3** (`0be08cd`) | `app/tools/registry.py` et `app/tools/builtin.py` sont touchés par D3 (`is_path`) : hunk **différent** (champ `ToolParameter.is_path` vs champ `ToolDefinition.read_only`) → pas de conflit de code, mais **les deux branches modifient les deux mêmes fichiers** → à fusionner dans l'ordre D3 puis D1-bis/D-B05, ou à fusionner simultanément |
| **A-α/B-α** (`25baa60`) | `runner.py` : hunk distinct → pas de conflit |
| **D-B05** (`79692fe`) | **base** de la présente branche : le correctif s'appuie dessus (colonne `owner_user_id`, liste complète) |
| **Audit contradictoire** (`fd25a26`) | ne porte que sur l'arbre Phase 5/6/6.1 ; **ne contredit aucun constat** ; aucun correctif n'est signalé en régression → aucune suspension appliquée |

---

## 8. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-results-persistence
git pull --ff-only

python -m unittest tests.test_mission_results_recovery -v
python -m unittest tests.test_mission_orchestrator tests.test_mission_bounds
python -m unittest discover -s tests
```

Observation manuelle de la reprise (console) : une mission interrompue
(`/mission-resume <id>`) doit
- rejouer une étape de lecture interrompue et **achever** la mission ;
- laisser une étape à effet **incertaine**, jamais rejouée, et le signaler
  dans « Étapes non terminées ».

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-results-persistence` (poussée sur `origin`) |
| SHA de base | `79692fe` (`fix/miles-mission-persistence-owner`, **non modifiée**) |
| Fichiers modifiés | `app/orchestration/runner.py`, `app/tools/registry.py`, `app/tools/builtin.py` |
| Fichiers ajoutés | `tests/test_mission_results_recovery.py`, ce rapport |
| `main` / intégration | `b9b7e7d` / `69bf670` — **inchangées** |
| D1 / D2 / D1-bis / D3 / A-α·B-α | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` / `25baa60` — **inchangées** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |

---

## 10. Prochaine action

1. **Audit indépendant d'Agent B** de la branche
   `fix/miles-results-persistence` : reconstruction des résultats, politique
   de reprise (catégories a et b), cohérence des budgets, absence de double
   exécution, exécution sous Debian 13.
2. **Fusion** : D3 touche `app/tools/registry.py` et `app/tools/builtin.py`
   comme cette branche → fusionner D3 **avant** (ou simultanément), et
   vérifier le hunk `ToolParameter` / `ToolDefinition`.
3. **Ne pas fusionner** sans décision explicite.
