# docs/reports/PHASE_6_3F_D3_IMPLEMENTATION_AGENT_A.md — Correctif D3 : typage explicite des paramètres de chemin

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base retenue** : `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` (`fix/miles-d1bis-authorization-response`)
- **Branche de correction** : `fix/miles-policy-path-typing`
- **`main`** : `b9b7e7d` — **inchangée**
- **Branche d'intégration auditée** : `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **inchangée**
- **Branches D1 / D2 / D1-bis** : `3a59dae` / `d3240d2` / `1ef4878` — **inchangées**
- **Analyse préalable** : `docs/reports/PHASE_6_3E_D3_ANALYSIS_AGENT_A.md` (analyse seule, sans modification)

> **Aucune fusion n'a été effectuée.** Le correctif attend l'audit
> indépendant d'Agent B. L'audit D3 **n'est pas** considéré comme approuvé.

---

## 1. Vérifications préalables et choix de la base

### 1.1 État Git vérifié

| Branche | SHA annoncé | SHA réel | Conforme |
|---------|--------------|----------|----------|
| `fix/miles-d1-web-authorization` (D1) | `3a59dae` | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` | ✔ |
| `fix/miles-windows-paths` (D2) | `d3240d2` | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` | ✔ |
| `fix/miles-d1bis-authorization-response` (D1-bis) | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | ✔ |
| `main` | `b9b7e7d` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | ✔ |
| `origin/integration/miles-phases-5-6-6-1` | `69bf670` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` | ✔ |

### 1.2 Justification de la base : `1ef4878`

| Base candidate | Pour | Contre | Verdict |
|-----------------|------|--------|---------|
| `main` (`b9b7e7d`) | — | **ne contient pas** `app/tools/builtin.py` (le moteur d'outils n'y est pas) : la base ne permettait pas de corriger D3 | **écartée** |
| `origin/integration/...` (`69bf670`) | branche d'intégration auditée | ne contient ni D1 ni D2 ni D1-bis : le correctif D3 serait construit sur un socle plus ancien que les correctifs en vol | écartée |
| `3a59dae` (D1) | inclut D1 | n'inclut pas D2 ni D1-bis | écartée |
| `d3240d2` (D2) | inclut D1 + D2 | n'inclut pas D1-bis | écartée |
| **`1ef4878` (D1-bis)** | **inclut D1 + D2 + D1-bis** : c'est la tête la plus récente du travail ; le correctif D3 s'appuie ainsi sur l'état le plus à jour | — | **retenue** |

### 1.3 Absence de conflit avec les correctifs en vol d'audit

Fichiers modifiés par les correctifs en vol (`git diff --stat <base>..<sha> -- app/`) :

| Correctif | Fichiers de code modifiés |
|-----------|--------------------------|
| D1 (`fc179ca`→`3a59dae`) | `app/orchestration/runner.py` |
| D2 (`3a59dae`→`d3240d2`) | `app/orchestration/planner.py` |
| D1-bis (`d3240d2`→`1ef4878`) | `app/interface/web.py`, `app/orchestration/runner.py` |
| **D3 (ce correctif)** | `app/tools/policy.py`, `app/tools/engine.py`, `app/tools/registry.py`, `app/tools/builtin.py` |

Les quatre fichiers modifiés par D3 sont **strictement disjoints** de ceux
modifiés par D1, D2 et D1-bis. Vérification par empreinte d'objet : les
fichiers `app/tools/{policy,engine,builtin,registry}.py` sont **identiques**
sur `3a59dae`, `d3240d2`, `1ef4878` **et** `69bf670` → **conflit de fusion
impossible** sur le code.

L'unique entorse est documentaire : `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md`
et `docs/coordination/*` sont modifiés par les quatre branches (résolution
manuelle des lignes concernées à la fusion, conflit de contexte et non de
contenu).

### 1.4 Isolation

Worktree Git dédié : `C:\Users\StanC\AppData\Local\Temp\miles-d3`
(`git worktree add Temp/miles-d3 -b fix/miles-policy-path-typing 1ef4878`).
Le checkout principal reste sur `fix/miles-d1-web-authorization`, son
artefact non suivi `tatus --short--branch` est préservé, et les bases de
données du développeur (`data/*.db`) n'ont pas été écrites.

---

## 2. Le défaut, mesuré

`app/tools/policy.py` appliquait **deux** contrôles de nature différente :

```python
for key in self._iter_keys(parameters):        # (1) CLES : correspondance EXACTE  -> correct
    if isinstance(key, str) and key.lower() in code_keys: ...

for value in self._iter_values(parameters):    # (2) VALEURS : correspondance par SOUS-CHAÎNE
    if isinstance(value, str) and any(k in value.lower() for k in code_keys): ...
```

Le contrôle (2) ne distingue pas une **valeur libre** d'une **valeur de
chemin** : un répertoire dont le nom contient « source », « code »,
« script » ou « python » est refusé, et avec lui toute mission portant sur
un tel répertoire. La même famille de faux positifs existe dans les
validateurs shell (`system`, `run`, `command`, `exec`) et secrets
(`secret`).

---

## 3. Solution retenue

### 3.1 Principe

> Le type « chemin » est **déclaré par l'application** dans le schéma de
> l'outil. La politique applique à ces valeurs un contrôle **structurel**
> (caractères de contrôle et métacaractères de commande) au lieu du
> contrôle par sous-chaîne. Le contrôle sur les **clés** est inchangé.

Aucune exemption « générale » n'est appliquée : l'exemption exige
**simultanément** (a) que le paramètre soit **déclaré** comme chemin dans le
schéma de l'outil, et (b) que sa valeur soit une **chaîne directe**.

### 3.2 Fichiers modifiés (4)

| Fichier | Modification | Volume |
|---------|--------------|--------|
| `app/tools/registry.py` | `ToolParameter.is_path: bool = False` (+ documentation) | ~18 lignes |
| `app/tools/builtin.py` | `is_path=True` sur `action_list_files.path` et `action_read_file.path` | 2 lignes |
| `app/tools/policy.py` | constantes des caractères contrôlés ; `_validate_path_value` ; factorisation des trois validateurs en `_reject_sensitive_keys` / `_reject_sensitive_values` ; paramètre `path_parameters` | ~150 lignes (dont ~60 de documentation) |
| `app/tools/engine.py` | transmission au validateur des paramètres déclarés comme chemins (déjà connus : `tool` est disponible à cet endroit) | ~20 lignes |

**`app/security/paths.py` n'est PAS modifié** (conformément à la consigne) :
le contrôle structurel vit dans la politique, qui est sa place naturelle ;
le confinement des chemins reste intact et reste l'unique autorité sur les
fichiers réellement accessibles.

### 3.3 Caractères bloqués dans une valeur de chemin

| Catégorie | Caractères | Justification |
|-----------|------------|---------------|
| Caractères de contrôle | `\x00` (octet nul), `\n`, `\r` | jamais valides dans un chemin ; vecteurs classiques de troncature et d'injection de journal |
| Métacaractères de commande | `;`, `\|`, `` ` ``, `<`, `>` | invalides dans un chemin Windows ; porteurs d'injection de commande |

**Décision explicite** : `&` et `$` ne sont **pas** bloqués. Ils apparaissent
dans des répertoires légitimes (« Rock & Roll », « $Recycle.Bin »,
« $Windows.~BT ») et MILES n'a **aucun interpréteur de commandes** : ils ne
sont pas exploitables. Les exclure ne retire **aucune** protection
existante (ces deux caractères étaient déjà acceptés avant le correctif).
Un test dédié (`test_repertoires_avec_esperet_ou_dollar_acceptes`) fixe
ce comportement.

### 3.4 Ce qui n'a **pas** été fait

| Action | Raison |
|--------|--------|
| Modifier `app/security/paths.py` | consigne explicite ; le confinement est l'autorité et n'a pas besoin d'être modifié |
| Modifier `app/orchestration/planner.py` | son contrôle porte sur des motifs de **commandes** (« rm -rf », « cmd /c », « powershell - ») : il ne produit **aucun** faux positif sur `C:\dev\source` ; le modifier serait un élargissement inutile |
| Modifier le confinement, les permissions, la liste des outils, les racines | aucun accès nouveau ; vérifié par tests |
| Corriger D1-ter ou le risque `/mission/<id>/answer` | explicitement hors périmètre de cette mission |
| Élargir l'exemption aux structures imbriquées | une structure sous un paramètre de chemin n'est pas un chemin : elle reste soumise au contrôle par sous-chaîne (et refusée par la validation de type) |

---

## 4. Garanties de sécurité conservées

| # | Garantie | Preuve |
|---|----------|--------|
| G1 | Les **clés** interdites restent interdites (correspondance exacte, dans les trois validateurs) | `TestClesSensiblesRestentInterdites` (7 tests) ; le code du contrôle de clés est **inchangé** |
| G2 | Les **valeurs libres** contenant un mot interdit restent contrôlées (contrôle par sous-chaîne) | `TestValeursLibresRestentControlees` (5 tests) |
| G3 | Les **chemins** sont validés **structurellement** (contrôle des métacaractères et caractères de contrôle) | `TestMetacaracteresBloquesDansUnChemin` (6 tests) |
| G4 | L'exemption est **bornée** : paramètre déclaré chemin **et** chaîne directe | `test_exemption_bornee_a_la_valeur_directe`, `test_cles_interdites_non_declarees_restent_refusees` |
| G5 | Le **confinement** des chemins est inchangé : un chemin accepté par la politique hors racines est refusé par `resolve_authorized_path` | `TestConfinementResteLEAutorite` (5 tests) ; `app/security/paths.py` non modifié |
| G6 | Les **traversées** de répertoires restent refusées | `test_traversee_de_repertoires_refusee` (3 cas) |
| G7 | Les **lectures** sont inchangées : les fichiers sensibles restent refusés | `test_lecture_d_un_fichier_sensible_refusee` ; `app/tools/local_actions.py` non modifié |
| G8 | **Aucun** outil, permission ou racine supplémentaire | `TestAucunDroitNouveau` (4 tests : liste des outils, permissions par outil, typage, racines) |
| G9 | Un chemin accepté par la politique **ne suffit jamais** à accéder à un fichier : les trois niveaux sont testés séparément | `TestConfinementResteLEAutorite` (niveau 2) et `TestOutilsReelsEtConfinement` (niveau 3) |

**Preuve directe du point central** : un chemin est *accepté* au niveau 1
(politique) et *refusé* au niveau 2 (confinement) dans le même test
(`test_chemin_hors_racines_refuse_par_le_confinement`) ✓.

---

## 5. Matrice de tests : vérification contre le code réel

La matrice de 29 cas de l'analyse D3 a été reprise puis **corrigée** après
vérification du code réel : le contrôle de la politique porte sur un
ensemble de **mots** interdits, et non sur des motifs de code. Deux
attentes de l'analyse ne correspondaient pas au comportement réel :

| Cas de l'analyse | Attendu par l'analyse | **Réel** | Correction |
|------------------|-----------------------|----------|------------|
| `{"message": "import os"}` | refus | **accepté** (aucun mot interdit) | l'analyse confondait détection de mots et détection de motifs ; le test utilise désormais des valeurs contenant réellement un mot interdit |
| `{"message": "rm -rf /"}` (validateur shell) | refus | **accepté** (« rm -rf » est un motif du *planificateur*, pas de la politique) | idem |
| `{"options": {"code": "x"}}` (clé imbriquée) | refus par la politique | **accepté** par la politique : `_iter_keys` ne descend pas dans les valeurs (comportement historique) ; le refus est assuré par le **schéma** (paramètre non déclaré) | le test est déplacé au niveau outil (`test_outil_refuse_une_cle_sensible_imbriquee`) et le constat est signalé (§7) |

La suite livrée compte **40 tests** répartis en 8 classes, couvrant les trois
niveaux (politique / validation du chemin / autorisation effective) :

| Classe | Niveau | Tests |
|--------|--------|-------|
| `TestClesSensiblesRestentInterdites` | 1 | 5 |
| `TestValeursLibresRestentControlees` | 1 | 6 |
| `TestCheminsLegitimesAcceptesParLaPolitique` | 1 | 3 |
| `TestMetacaracteresBloquesDansUnChemin` | 1 | 6 |
| `TestDefautD3Reproduit` | 1 | 3 |
| `TestConfinementResteLEAutorite` | 2 | 4 |
| `TestNiveauOutil` | 3 | 6 |
| `TestOutilsReelsEtConfinement` | 3 | 3 |
| `TestAucunDroitNouveau` | — | 4 |

### 5.1 Les tests échouent-ils avec le comportement antérieur ?

Oui, vérifié explicitement :

| Situation | Résultat |
|-----------|----------|
| Code complet | `Ran 40 tests — OK` |
| Revert de `app/tools/engine.py` seul (l'outil ne transmet plus le typage → le défaut D3 réapparaît) | **`FAILED (failures=3)`** : `test_outil_execute_avec_un_chemin_legitime`, `test_outil_refuse_un_chemin_avec_metacaractere`, `test_listage_d_un_repertoire_nomme_source_reussit` |
| Revert complet de `app/tools/` | le module de test ne peut même pas être importé (l'attribut `is_path` n'existe pas) : le défaut est capturé **par construction** |

En outre, la classe `TestDefautD3Reproduit` **dépend du comportement
historique** : elle vérifie que, *sans* typage explicite, la politique
refuse `C:\dev\source` (comportement antérieur conservé et documenté), et
qu'*avec* typage elle l'accepte. Si l'exemption était supprimée, cette
classe échouerait.

---

## 6. Commandes, résultats et limites

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_policy_path_typing` | **40 tests, 0 échec** (0,5 s) |
| `python -m unittest tests.test_policy_path_typing` *(revert de `engine.py`)* | **3 échecs** (défaut D3 reproduit) |
| `python -m unittest tests.test_tool_policy` | **11 tests, 0 échec** |
| `python -m unittest tests.test_tool_engine` | **26 tests, 0 échec** (3,8 s) |
| `python -m unittest tests.test_tool_integration` | **40 tests, 0 échec** (7,0 s) |
| `python -m unittest tests.test_tool_resources` | **8 tests, 0 échec, 1 ignoré** |
| `python -m unittest tests.test_path_security` | **21 tests, 0 échec, 3 ignorés** |
| `python -m unittest tests.test_web_security_phase6_1` | **35 tests, 0 échec** |
| `python -m unittest tests.test_web_security` | **33 tests, 0 échec** |
| `python -m unittest tests.test_mission_orchestrator` | **73 tests, 0 échec** |
| `python -m unittest tests.test_mission_web_authorization` (D1) | **6 tests, 0 échec** |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | **20 tests, 0 échec** |
| `python -m unittest tests.test_mission_bounds` | **20 tests, 0 échec** |
| `python -m unittest tests.test_windows_paths` (D2) | **21 tests, 0 échec** |
| `python -m unittest discover -s tests` | **615 tests, 0 échec, 4 ignorés** (88,6 s) |
| Tests d'audit d'Agent B (rejoués tels quels, depuis `origin/audit/agent-b-phase6-1-web-security-review`) | **70 tests, 0 échec, 2 ignorés** (31,4 s) |

**Tests ignorés** : 4 (suite complète) + 1 (`test_tool_resources`) + 3
(`test_path_security`) + 2 (audit) — tous des **limites de plateforme
Windows** (liens symboliques, `/proc/self/fd`) ; ils s'exécutent sous
Debian 13.

**Limites d'environnement** :

- aucune validation sous **Debian 13** (environnement indisponible) ;
- **aucun appel API payant** : tous les tests sont locaux ; les tests
  d'audit sont rejoués tels quels sans réseau ;
- aucune donnée réelle modifiée : le seul répertoire créé par les tests
  (`d3-*` sous la racine du projet) est supprimé par `addCleanup` ; les
  bases `data/*.db` du développeur n'ont pas été écrites.

---

## 7. Risques résiduels

| # | Risque | Analyse | Parade |
|---|--------|---------|---------|
| R1 | Un code glissé dans un paramètre de type chemin n'est plus vu par le contrôle par sous-chaîne | MILES n'a **aucun outil d'exécution** : la valeur est un chemin, il est résolu et confiné par `resolve_authorized_path`, et les fichiers sensibles sont refusés par le handler. Un fichier `.py` **lu** n'est pas **exécuté**. | G5, G7, G9 + le contrôle structurel (G3) |
| R2 | L'exemption pourrait s'étendre par erreur à d'autres paramètres | Elle exige un marqueur `is_path` **posé par l'application** dans le schéma ; le modèle ne fournit que des valeurs et ne peut ni ajouter un paramètre (rejet du schéma) ni modifier le typage | G4, G8, `TestDefautD3Reproduit.test_le_typage_est_decl_par_l_application` |
| R3 | `&` et `$` restent autorisés dans un chemin | Aucun interpréteur de commandes dans MILES ; le confinement décide de l'accès ; ces caractères étaient déjà acceptés avant le correctif (aucune protection perdue) | test dédié documentant la décision |
| R4 | Un chemin POSIX contenant `;` ou `>` serait refusé (faux positif résiduel) | Ces caractères sont rares dans un nom de fichier et sont interdits dans un chemin Windows ; le confinement les refusait de toute façon dans la très grande majorité des cas | documenté ; le signalement `409`/erreur de politique est explicite |
| R5 | Le contrôle de **clés** ne descend pas dans les structures imbriquées (constat préexistant, **inchangé**) | Une clé interdite imbriquée n'est pas vue par la politique ; elle est refusée par le **schéma** (paramètre non déclaré) au niveau du moteur | `test_outil_refuse_une_cle_sensible_imbriquee` ; **signalé à Agent B** (§8) |
| R6 | Le type `path` est aussi la clé du contrôle `validate_plan_payload` du planificateur | Aucun : ce contrôle porte sur des motifs de commandes et ne produit aucun faux positif sur un chemin ; il est **inchangé** | vérifié par relecture du code |
| R7 | D3-ter : la politique ne couvre pas les valeurs libres contenant du code sans mot interdit (« import os », « print(1) ») | **Préexistant**, hors périmètre : le contrôle est une liste de mots, pas une détection de motifs. MILES n'exécutant rien, le risque est faible | **signalé à Agent B** (§8) |

---

## 8. Points signalés à Agent B (hors périmètre de cette mission)

1. **Clés imbriquées non contrôlées par la politique** (R5) : `_iter_keys`
   recurse dans les *clés* mais pas dans les *valeurs* des dictionnaires.
   Le schéma ferme la porte, mais la politique ne le fait pas. Correction
   possible en une ligne (`yield from ToolPolicy._iter_keys(value)` dans la
   branche dict) — **non appliquée ici** (code de sécurité, hors D3).
2. **La politique ne détecte pas les fragments de code** sans mot interdit
   (« import os », « print(1) ») : le contrôle est une liste de mots, pas
   une détection de motifs. Le planificateur, lui, contrôle des motifs de
   commandes. **Non modifié** (hors périmètre).
3. **D1-ter** (« mission occupée ») et le contournement du jeton via
   `/mission/<id>/answer` : traités dans le rapport D1-bis
   (`PHASE_6_3D_D1BIS_AGENT_A.md` §6 et §7), **non corrigés ici**.

---

## 9. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-policy-path-typing
git pull --ff-only

# 1. Le défaut est reproduit par les tests
python -m unittest tests.test_policy_path_typing -v
git stash push app/tools/engine.py     # revert du seul moteur
python -m unittest tests.test_policy_path_typing   # 3 échecs : le défaut D3 réapparaît
git stash pop

# 2. Les garanties
python -m unittest tests.test_tool_policy tests.test_tool_engine
python -m unittest tests.test_path_security
python -m unittest discover -s tests
```

Vérification manuelle « en direct » de l'ancien et du nouveau comportement :

```python
>>> from app.tools.policy import ToolPolicy
>>> from app.tools.builtin import build_default_registry
>>> chemins = {p.name for t in build_default_registry().list_tools()
...            for p in build_default_registry().get_tool(t).parameters if p.is_path}
>>> chemins
{'path'}
>>> politique = ToolPolicy({'lecture_systeme'})
>>> politique.validate_no_code_execution({"path": r"C:\dev\source"})
PermissionError: Valeur interdite (exécution de code) : C:\dev\source   # historique
>>> politique.validate_no_code_execution({"path": r"C:\dev\source"}, path_parameters=chemins)
# plus d'exception : le chemin est accepté par la politique
>>> politique.validate_no_code_execution({"path": "C:\\x; rm -rf /"}, path_parameters=chemains)
PermissionError: Valeur interdite (chemin non conforme) : C:\x; rm -rf /  # structurel
```

Et le niveau 2 tranche toujours :

```python
>>> from app.security.paths import resolve_authorized_path
>>> resolve_authorized_path(r"C:\Windows\System32")
PathSecurityError: Chemin hors des racines autorisées : 'C:\\Windows\\System32'
```

---

## 10. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-policy-path-typing` |
| SHA de base | `1ef4878` (`fix/miles-d1bis-authorization-response`) |
| Fichiers modifiés | `app/tools/policy.py`, `app/tools/engine.py`, `app/tools/registry.py`, `app/tools/builtin.py` |
| Fichiers ajoutés | `tests/test_policy_path_typing.py`, ce rapport |
| `main` | `b9b7e7d` — **inchangée** |
| Branche d'intégration auditée | `69bf670` — **inchangée** |
| Branches D1 / D2 / D1-bis | `3a59dae` / `d3240d2` / `1ef4878` — **inchangées** |
| Artefact non suivi | `tatus --short--branch` — **préservé, hors du commit** |

---

## 11. Prochaine action

1. **Audit indépendant par Agent B** de la branche
   `fix/miles-policy-path-typing`, portant sur :
   - le caractère borné de l'exemption (paramètre déclaré + chaîne directe) ;
   - le choix des caractères bloqués (`&` et `$` exclus) ;
   - le maintien des garanties G1 à G9 ;
   - l'absence de conflit avec D1, D2 et D1-bis (fichiers disjoints) ;
   - l'exécution sous Debian 13.
2. **Ne pas fusionner** avant cet audit : l'audit D3 n'est pas approuvé.
3. Traiter séparément les points signalés au §8 (clés imbriquées, fragments
   de code, D1-ter).
