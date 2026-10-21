# docs/reports/PHASE_6_3C_D2_WINDOWS_PATHS_AGENT_A.md — Correction D2 et analyse D3

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Dépôt** : `C:\Users\StanC\Desktop\Milescorp` (remote `https://github.com/Miles-corp/Milescorp.git`)
- **SHA de base (vérifié)** : `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` (`fix/miles-d1-web-authorization`, tête `3a59dae`)
- **Branche de correction** : `fix/miles-windows-paths`
- **`main`** : `b9b7e7d` — **inchangée**
- **Branche auditée par Agent B** : `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **inchangée**
- **Branche du correctif D1** : `fix/miles-d1-web-authorization` = `3a59dae` — **inchangée**
- **Défaut corrigé** : D2 du rapport `PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md` (§4)
- **Défaut analysé (non modifié)** : D3

> **Aucune fusion n'a été effectuée.** Le correctif attend l'audit
> indépendant d'Agent B.

---

## 1. Vérifications préalables

| Vérification | Résultat |
|--------------|----------|
| État Git avant intervention | arbre propre, sauf l'artefact non suivi `tatus --short--branch` (**préservé, non committé**) |
| SHA de base attendu `3a59dae` | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` ✔ conforme |
| `origin/fix/miles-d1-web-authorization` | `3a59dae…` (local = distant) |
| `origin/main` | `b9b7e7d…` (ne pas modifier) |
| `origin/integration/miles-phases-5-6-6-1` | `69bf670…` (ne pas modifier) |
| Isolation du travail | **worktree Git dédié** : `C:\Users\StanC\AppData\Local\Temp\miles-d2` (`git worktree add -b fix/miles-windows-paths 3a59dae`) ; le checkout principal reste sur `fix/miles-d1-web-authorization` avec son artefact non suivi |

Le travail a donc été fait **hors** du checkout principal : ni la branche D1
(objet de l'audit en cours) ni l'artefact local n'ont été touchés.

---

## 2. D2 — Diagnostic

### 2.1 Cause

`app/orchestration/planner.py::extract_target_path` reconnaît un chemin dans
l'objectif à l'aide de l'expression régulière suivante (avant correctif) :

```python
_PATH_LIKE = re.compile(r"[A-Za-z0-9_.\-]*[\\/][A-Za-z0-9_.\-/\\]*|[A-Za-z0-9_.\-]+\\")
```

La classe de caractères n'inclut pas `:`. Pour `C:/Windows`, le moteur
d'expression régulière ne peut donc pas consommer `C:` et démarre le jeton à
la position du séparateur :

| Objectif | Jeton reconnu (avant) | Cible déduite (avant) |
|----------|----------------------|-----------------------|
| `Analyse C:/Windows` | `/Windows` | `/Windows` |
| `Analyse C:\Windows` | `\Windows` | `\Windows` |
| `Analyse D:\donnees\rapports` | `\donnees\rapports` | `\donnees\rapports` |
| `Analyse C:\Program Files\Dossier` | `\Program` + `Files\Dossier` | `None` (ambiguïté) |

### 2.2 Impact réel (mesuré, pas supposé)

Le chemin déduit est transmis à `resolve_authorized_path()`
(`app/security/paths.py`), qui le résout de façon canonique. Un chemin
Windows sans lettre de lecteur n'est plus absolu : il est interprété comme
**racine du lecteur courant**.

```
Objectif : Analyse D:\donnees\rapports en lecture

AVANT  cible extraite : '/donnees/rapports'
       chemin canonique : C:\donnees\rapports     <-- lecteur D: perdu
APRES  cible extraite : 'D:\donnees\rapports'
       chemin canonique : D:\donnees\rapports     <-- lecteur conservé
```

Conséquences, par ordre de gravité :

1. **Mauvais répertoire analysé.** Une demande portant sur `D:\donnees` était
   servie par `C:\donnees`. Si ce chemin de substitution tombe dans les
   racines autorisées (racine du projet ou `data/`), la mission lit un
   **autre** répertoire en silence ; sinon, l'échec est trompeur.
2. **Message d'erreur trompeur.** Le refus de périmètre citait le chemin
   tronqué, jamais celui demandé :
   *avant* → « Chemin hors périmètre autorisé : **/Windows/System32** » ;
   *après* → « Chemin hors périmètre autorisé : **C:/Windows/System32** ».
3. **Chemins avec espaces non pris en charge** : `C:\Program Files\Dossier`
   produisait deux candidats distincts → aucun chemin déduit → clarification
   inutile.
4. **Aucun effet sur les protections.** Le contrôle d'accès reste appliqué
   par `resolve_authorized_path` (racines autorisées : racine du projet et
   `data/`) : le défaut est un défaut de **fidélité** de la cible, pas une
   porte déverrouillée.

> Point important : le défaut est **invisible sur un seul lecteur**. Comme
> `\Users\...` se résout sur le lecteur courant, un chemin du même lecteur
> que le projet fonctionnait par chance. Le défaut n'apparaît qu'au passage
> à un autre lecteur, ou dans le message d'erreur.

---

## 3. D2 — Correctif appliqué

Un seul fichier modifié : `app/orchestration/planner.py`.

### 3.1 Principes

1. **Fidélité** : la cible déduite est exactement le chemin écrit par
   l'utilisateur (lettre de lecteur, tirets, espaces, segments).
2. **Prudence** : aucune extension de la cible. Les protections ne sont ni
   relâchées ni contournées ; la politique de sécurité reste le seul juge.
3. **Explicitation** : en cas d'ambiguïté, la mission demande toujours une
   clarification (comportement conservé).

### 3.2 Détail

| Élément | Avant | Après |
|---------|-------|-------|
| Lettre de lecteur | absente de la classe de caractères | `(?:[A-Za-z]:)?` + garde `(?<![A-Za-z0-9_.~-])` (pas de milieu de mot) |
| Segments | `[A-Za-z0-9_.\-]` | `[A-Za-z0-9_.~-]` (le tiret est restauré : `miles-d2`) |
| Espaces internes | impossible | prolongement en Python : un mot qui contient lui-même un séparateur prolonge le chemin (`C:\Program Files\Dossier`) ; un mot **capitalisé** prolonge un chemin **Windows absolu** (`C:\Users\Jean\Mes Documents`) |
| Chemins entre guillemets | ignorés | acceptés tels quels (« `"C:\Users\Jean\Mes Documents"` ») : forme non ambiguë |
| Marqueur `dossier <nom>` | capturait un **préfixe** de chemin (`dossier C:/Windows` → `C`) | le préfixe est ignoré si le chemin complet est déjà candidat ; un marqueur situé **dans** un chemin reconnu (`C:\...\Dossier Avec Espace`) n'est plus pris pour une autre cible |
| Lettre de lecteur seule | — | `C:` et `C:\` ne désignent aucun dossier : cible inconnue → clarification |

### 3.3 Règle de prolongement (lisible et testable)

```python
def _word_continues_path(word: str, token: str) -> bool:
    if "/" in word or "\\" in word:
        return True
    if word[:1].isupper() and _WINDOWS_ABSOLUTE.match(token):
        return True
    return False
```

- Un mot qui contient un séparateur prolonge toujours le chemin.
- Un mot capitalisé prolonge **seulement** un chemin Windows absolu : les
  noms de dossiers Windows contiennent souvent des espaces, et la règle est
  volontairement limitée à Windows pour ne pas avaler la prose qui suit un
  chemin POSIX.
- Les chemins relatifs et POSIX ne sont **jamais** prolongés par un mot
  capitalisé : « docs/ identifie son organisation » reste « docs/ ».

**Limite assumée et documentée** : un chemin dont le dernier segment
comporte des espaces et des mots **entièrement en minuscules**
(`C:\...\dossier avec espace`) n'est pas reconnu sans guillemets — c'est
l'ambiguïté classique entre un chemin et la prose. L'écriture entre
guillemets est la forme non ambiguë, désormais acceptée.

---

## 4. D2 — Tests

Fichier nouveau : `tests/test_windows_paths.py` (**21 tests**).

| # | Couverture | Test |
|---|-----------|------|
| 1 | Chemins absolus Windows (lettre de lecteur conservée) | `test_chemin_absolu_windows_conserve_la_lettre_de_lecteur` |
| 2 | Chemins Windows avec espaces | `test_chemin_windows_avec_espaces_est_conserve` |
| 3 | Chemins relatifs (`docs/coordination`, `./docs`, `../docs`, `docs\coordination`) | `test_chemin_relatif_est_conserve` |
| 4 | Chemins POSIX (`/home/user/projet`, `/etc`) | `test_chemin_posix_est_conserve` |
| 5 | Non-régression (comportements antérieurs) | `test_non_regression_des_comportements_existants`, `test_espaces_ne_avalent_pas_la_phrase` |
| 6 | Ambiguïté → clarification | `test_ambiguite_exige_une_clarification` |
| 7 | `C:` seul → aucune cible | `test_lecteur_seule_ne_designe_aucun_dossier` |
| 8 | Marqueur / préfixe | `test_marqueur_ne_capture_qu_un_prefixe_de_chemin` |
| 9 | Entrées malformées | `test_entrees_malformees_ne_donnent_aucun_chemin` |
| 10 | Chemins entre guillemets | `test_chemin_entre_guillemets_est_cible` |
| 11 | **Hors périmètre refusé** (plateforme portable) | `test_chemin_windows_hors_perimetre_refuse` |
| 12 | **Hors périmètre avec espaces refusé** | `test_chemin_windows_avec_espaces_hors_perimetre_refuse` |
| 13 | **Traversée de répertoires refusée** (`../`, `../../etc`) | `test_traversee_de_repertoires_refusee` |
| 14 | **Racines autorisées inchangées** (projet + `data/`) | `test_les_racines_autorisees_ne_sont_pas_elargies` |
| 15 | Entrée malformée → aucun plan | `test_entree_malformee_refusee` |
| 16 | Mission hors périmètre → échec | `test_mission_avec_chemin_hors_perimetre_echoue` |
| 17 | Chemin absolu du projet ciblé | `test_chemin_absolu_du_projet_est_cible` |
| 18 | Dossier avec espace réellement analysé (planificateur) | `test_dossier_avec_espace_analyse` |
| 19 | Mission : cible conservée | `test_mission_conserve_la_cible_demandee` |
| 20 | Mission : chemin Windows externe jamais analysé | `test_mission_avec_chemin_windows_externe_echoue` |

### 4.1 Le test échoue-t-il **avant** le correctif ?

Vérifié explicitement (correctif retiré par `git stash`, puis restauré) :

```
sans correctif : Ran 21 tests — FAILED (failures=9)
avec correctif : Ran 21 tests — OK
```

Les 9 échecs portent sur la conservation de la lettre de lecteur, les espaces,
les guillemets, le marqueur et la cible de mission. Les 12 autres tests
passent dans les deux cas : ils vérifient des propriétés de sécurité
(confinement), déjà correctes avant le correctif.

### 4.2 Commandes exécutées et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_windows_paths` | **21 tests, 0 échec** (0,02 s) |
| `python -m unittest tests.test_windows_paths` *(sans le correctif)* | **9 échecs** |
| `python -m unittest tests.test_mission_orchestrator` | **73 tests, 0 échec** (14,8 s) |
| `python -m unittest tests.test_mission_bounds` | **20 tests, 0 échec** (4,8 s) |
| `python -m unittest tests.test_mission_web_authorization` | **6 tests, 0 échec** (1,4 s) — non-régression D1 |
| `python -m unittest tests.test_web_security_phase6_1` | **35 tests, 0 échec** (9,5 s) |
| `python -m unittest tests.test_tool_policy` | **11 tests, 0 échec** |
| `python -m unittest tests.test_web_security` | **33 tests, 0 échec** (10,1 s) |
| `python -m unittest discover -s tests` | **555 tests, 0 échec, 4 ignorés** (80,6 s) |
| Tests d'audit d'Agent B (rejoués tels quels depuis `origin/audit/agent-b-phase6-1-web-security-review`) | **70 tests, 0 échec, 2 ignorés** (22,7 s) |

Les 4 + 2 tests ignorés sont des **limites de plateforme Windows** (3 liens
symboliques, 1 `/proc/self/fd`, 2 liens symboliques d'audit) ; ils
s'exécutent sous Debian 13.

---

## 5. D3 — Analyse (aucune modification apportée)

> **Rien n'a été modifié dans le code de sécurité.** Cette section est une
> analyse et une proposition ; elle demande une validation explicite avant
> toute écriture dans `app/tools/policy.py`.

### 5.1 Localisation exacte

| Élément | Emplacement |
|---------|-------------|
| Politique concernée | `app/tools/policy.py::ToolPolicy.validate_no_code_execution` (l. 90-104) |
| Éléments frères concernés | `validate_no_shell_access` (l. 74-88), `validate_no_secret_access` (l. 106-120) |
| Point d'application | `app/tools/engine.py::ToolEngine.execute`, étape 2 (l. 229-233), **avant** toute exécution d'outil |
| Paramètres concernés | ceux des outils `action_list_files` et `action_read_file` (`app/tools/builtin.py` l. 92-96 et 126-131 : `path`, type `str`) |
| Contrôle secondaire | `app/orchestration/planner.py::validate_plan_payload` (contrôle de sous-chaîne **sur les clés uniquement**, l. 283-290) — celui-ci est correct |

### 5.2 Cause

Les trois validateurs appliquent **deux contrôles de nature différente** :

```python
# (1) contrôle sur les CLES : correspondance EXACTE  -> correct
for key in self._iter_keys(parameters):
    if isinstance(key, str) and key.lower() in code_keys:
        raise PermissionError(...)

# (2) contrôle sur les VALEURS : correspondance par SOUS-CHAÎNE -> faux positifs
for value in self._iter_values(parameters):
    if isinstance(value, str) and any(k in value.lower() for k in code_keys):
        raise PermissionError(...)
```

Le contrôle (2) ne distingue pas une **valeur libre** (un fragment de code)
d'une **valeur de chemin** (un nom de répertoire). Mesure sur la politique
actuelle :

| Valeur de paramètre `path` | shell | code | secret |
|-----------------------------|-------|------|--------|
| `C:\dev\source` | ok | **refusé** (`source`) | ok |
| `C:\dev\source\projet` | ok | **refusé** | ok |
| `C:\Users\X\Documents\code` | ok | **refusé** (`code`) | ok |
| `C:\Users\X\Documents\scripts` | ok | **refusé** (`script`) | ok |
| `C:\Python39\Lib` | ok | **refusé** (`python`) | ok |
| `C:\Users\X\mon-script-de-notes.txt` | ok | **refusé** | ok |
| `C:\Windows\System32` | **refusé** (`system`) | ok | ok |
| `C:\Users\X\AppData\Local\run` | **refusé** (`run`) | ok | ok |
| `C:\Users\X\Desktop\command` | **refusé** (`command`) | ok | ok |
| `C:\Users\X\Desktop\exec` | **refusé** (`exec`) | ok | ok |
| `C:\Users\X\Documents\secret` | ok | ok | **refusé** (`secret`) |
| `C:\projet\docs\coordination` | ok | ok | ok |
| `docs/coordination`, `/home/user/projet` | ok | ok | ok |

Deux constats :

1. **D3 proprement dit** : les faux positifs de `code`, `source`, `script`,
   `python`, `javascript` sur les valeurs de chemin. Le symptôme rapporté
   (`C:\dev\source\`) est confirmé.
2. **Même famille, deux autres validateurs** : `system`, `run`, `command`,
   `exec` (contrôle shell) et `secret` (contrôle secrets) produisent les
   mêmes faux positifs sur des chemins. Corriger uniquement `validate_no_code_execution`
   laisserait `C:\Windows\System32` refusé.

**Portée réelle de l'impact** : les racines autorisées sont la racine du
projet et `data/`. Un chemin de projet contenant l'une de ces sous-chaînes
(par exemple un projet situé dans `C:\dev\source\Milescorp`) rend **toute**
mission impossible : chaque appel d'outil est refusé par la politique, avant
même la résolution du chemin. Le blocage est total, pas marginal.

### 5.3 Stratégie proposée

**Principe : distinguer les clés sensibles des valeurs de chemin.**

| # | Règle | Statut |
|---|-------|--------|
| 1 | Le contrôle sur les **CLÉS** reste une correspondance **exacte** (insensible à la casse), inchangé, pour les trois validateurs. Il est précis : un paramètre nommé `code`, `script`, `python`, `javascript`, `shell_code`, `source`, `shell`, `command`, `cmd`, `exec`, `eval`, `run`, `system`, `password`, `secret`, `api_key`, `token`… est un vecteur d'exécution ou de fuite, quelle que soit sa valeur. | **à conserver tel quel** |
| 2 | Le contrôle par sous-chaîne sur les **VALEURS** cesse de s'appliquer aux paramètres dont le **type déclaré est un chemin**. Le type est porté par le schéma de l'outil, pas deviné : c'est la seule façon de ne pas ouvrir une brèche. | **proposition principale** |
| 3 | Pour un paramètre de type chemin, le contrôle par sous-chaîne est remplacé par un contrôle **structurel** : la valeur ne doit contenir aucun métacaractère de commande (`;`, `|`, `&`, `` ` ``, `$`, `>`, `<`, retour ligne). La protection contre l'injection est conservée, les faux positifs sur les noms de répertoires disparaissent. | **proposition** |
| 4 | Le contrôle par sous-chaîne reste **inchangé** pour toute valeur qui n'est pas un chemin (paramètre libre, requête, texte). Aucun assouplissement. | **à conserver tel quel** |
| 5 | La même notion de « paramètre de chemin » est appliquée aux **trois** validateurs (shell, code, secrets), sinon les faux positifs `system`, `run`, `command`, `exec`, `secret` subsistent. | **proposition** |
| 6 | Le contrôle de confinement reste inchangé et prévalent : un chemin de type chemin est de toute façon soumis à `resolve_authorized_path` (racines autorisées) et, pour la lecture, au refus des fichiers sensibles (`.env`, clés privées). La politique n'a donc **pas** à faire le travail du confinement. | **à conserver tel quel** |

**Comment déclarer un paramètre « chemin » (option 2) — deux voies, à trancher par Agent B :**

- **2-a — Typage explicite dans le registre** *(recommandé)* : ajouter au
  `ToolParameter` (`app/tools/registry.py`) un marqueur de type, par exemple
  `is_path: bool = False` (ou un type dédié `"path"`), puis le porter sur les
  paramètres `path` de `action_list_files` et `action_read_file`. La
  politique reçoit alors la liste des paramètres de type chemin (via la
  définition d'outil déjà disponible dans le moteur) et n'applique pas le
  contrôle par sous-chaîne à ces valeurs.
  *Pour :* précis, déclaratif, vérifiable par le schéma, aucun heuristique.
  *Contre :* modifie le registre, la politique et l'appel du moteur — donc
  du code de sécurité, qui exige une revue dédiée.
- **2-b — Heuristique sur la valeur** : ne pas appliquer le contrôle par
  sous-chaîne à une valeur qui « ressemble à un chemin » (séparateur, lettre
  de lecteur).
  *Pour :* moins de modifications.
  *Contre :* une valeur containing du code peut être déguisée en chemin
  (`C:\x\..\code.py`) ; la garantie repose alors uniquement sur le
  confinement. **Moins bon que 2-a.**

**Recommandation d'Agent A : 2-a**, avec 2-b écartée.

### 5.4 Tests proposés (à écrire lors de la correction, **non écrits ici**)

**Doivent rester BLOQUÉS (interdits absolus) :**

| Cas | Attendu |
|-----|---------|
| paramètre nommé `code` / `script` / `python` / `javascript` / `shell_code` / `source` (toute valeur) | refus |
| paramètre nommé `shell` / `command` / `cmd` / `exec` / `eval` / `run` / `system` | refus |
| paramètre nommé `password` / `secret` / `api_key` / `token` / `private_key` / `credential` | refus |
| paramètre **libre** (non chemin) contenant `import os`, `os.system(`, `rm -rf`, `print(`, `eval(` | refus |
| paramètre **libre** (non chemin) contenant le mot `script` ou `code` | refus (le contrôle par sous-chaîne reste) |
| paramètre de type chemin contenant un métacaractère (`;`, `|`, `&`, `` ` ``, `$`) | refus (contrôle structurel) |
| chemin hors racines autorisées, même sans mot suspect | refus par le confinement |

**Doivent devenir ACCEPTÉS (faux positifs à éliminer) :**

| Cas | Attendu |
|-----|---------|
| `path = "C:\dev\source"` (projet situé sous `source`) | accepté par la politique, puis refusé par le confinement s'il est hors périmètre |
| `path = "C:\Users\X\Documents\code"` | accepté par la politique |
| `path = "C:\projet\python\app"` | accepté par la politique |
| `path = "C:\Users\X\mon-script.txt"` | accepté par la politique |
| `path = "C:\Windows\System32"` | accepté par la politique, refusé par le confinement |
| `path = "C:\Users\X\secret\notes"` | accepté par la politique, refusé par le confinement |

**Non-régression à vérifier :** les tests existants de
`tests/test_tool_policy.py` (11 tests) et `tests/test_tool_integration.py`
doivent rester verts ; les 70 tests d'audit d'Agent B également.

### 5.5 Décision demandée à Agent B

1. Voie **2-a** (typage explicite) ou **2-b** (heuristique) ?
2. La correction D3 doit-elle être faite par Agent A (avec revue d'Agent B)
   ou par Agent B lui-même ?
3. Un lot commun D3 + D1-bis, ou deux lots séparés ?

---

## 6. Guide utilisateur mis à jour

`docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` :

| § | Modification |
|---|------------|
| §1 | nouvelle ligne « Chemin Windows absolu et chemin avec espaces » → §4.10 |
| §3 | branche de travail : `fix/miles-windows-paths` |
| §4.10 | **nouvelle procédure** : chemin Windows absolu, chemin avec espaces (guillemets), chemin hors périmètre — avec les sorties observées |
| §6 | ligne **D2** : passée à « CORRIGÉ » (symptôme, cause, correctif) ; ligne **D3** : analyse faite, **aucune modification**, renvoi vers ce rapport |
| §7.1 | suite complète : **555 tests, 0 échec, 4 ignorés** ; nouvelle ligne « Chemins Windows (D2) : 21 tests » |

La séparation demandée reste explicite : **§7.1 = tests locaux, sans aucun
coût** (aucun appel réseau, aucun fournisseur) ; **§7.2 = tests nécessitant
une API distante payante** (conversation IA, plan proposé par le fournisseur,
analyse qualitative du rapport — non exécutés) ; **§7.3 = tests matériel**.
Le §2 rappelle qu'une mission déclenche 2 appels au fournisseur configuré et
donne la recette du test sans coût (`MILES_REMOTE_TIMEOUT=1`, repli
déterministe).

---

## 7. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-windows-paths
git pull --ff-only

$env:MILES_REMOTE_TIMEOUT = "1"   # test sans coût ni fournisseur

# 1. chemin Windows absolu (racine du projet) -> completed
$racine = (Get-Location).Path
@("/mission Analyse $racine\docs en lecture seule","o","/quit") | python miles.py
# attendu : « Autoriser l'accès en lecture dans C:\...\docs … » puis
#            Motif d'arrêt : completed

# 2. chemin avec espaces (entre guillemets) -> completed
@("/mission Analyse `"$racine\docs\coordination`" en lecture seule","o","/quit") | python miles.py

# 3. chemin hors périmètre -> failed, message citant le chemin demandé
@("/mission Analyse C:/Windows/System32 en lecture","o","/quit") | python miles.py
# attendu : « Chemin hors périmètre autorisé : C:/Windows/System32 »
```

Résultats **observés le 2026-10-21** sur Windows (Python 3.12.10) :

```
=== 1. Mission sur un chemin Windows ABSOLU (racine du projet) ===
  Autoriser l'accès en lecture dans C:\Users\StanC\AppData\Local\Temp\miles-d2\docs pour les outils : action_list_files, action_read_file ?
  Mission 976f81419fa3 — état : completed
  Motif d'arrêt : completed
  == Faits observés ==
  - 4 fichier(s) non lus (binaire, hors texte ou sensible).

=== 2. Chemin Windows HORS perimetre ===
  Mission af6fe52da707 — état : failed
  Motif d'arrêt : failed
  - Chemin hors périmètre autorisé : C:/Windows/System32 (Chemin hors des racines autorisées : 'C:/Windows/System32').

=== 3. Chemin Windows avec ESPACES (guillemets) ===
  Autoriser l'accès en lecture dans C:\Users\StanC\AppData\Local\Temp\miles-d2\docs\coordination pour les outils : action_list_files, action_read_file ?
  Mission 6594c649f778 — état : completed
  Motif d'arrêt : completed
```

**Avant le correctif**, le cas 2 affichait « Chemin hors périmètre autorisé :
**/Windows/System32** » (chemin tronqué) — la comparaison a été faite sur la
même machine, correctif retiré puis restauré.

---

## 8. Limites connues

| Limite | Statut |
|--------|--------|
| Un chemin dont le dernier segment porte des espaces et des mots **en minuscules** (`C:\...\dossier avec espace`) n'est reconnu qu'entre guillemets | assumé et documenté (§3.3) |
| Sur **POSIX**, un chemin Windows (`C:/Windows`) n'est pas absolu : il est traité comme un chemin relatif au projet, donc refusé par le confinement comme inexistant | comportement correct : un chemin Windows n'a pas de sens sous Linux ; le message est explicite |
| Aucun test sous **Debian 13** | environnement indisponible ; les 6 tests ignorés sont des limites Windows |
| Le chemin `~` n'est pas développé (`~/projet` reste littéral) | choix : le confinement décide ; aucune expansion du dossier personnel |
| **D1-bis** non corrigé (réponse HTTP trompeuse sur jeton d'approbation invalide) | hors périmètre de cette mission ; déjà signalé à Agent B (M-006) |
| **D3 non corrigé** | analyse et proposition seulement (§5), en attente d'une validation explicite |
| D4 (délai du fournisseur) non corrigé | hors périmètre |

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-windows-paths` (poussée sur `origin`) |
| SHA de base | `3a59dae` (`fix/miles-d1-web-authorization`) |
| Fichiers modifiés | `app/orchestration/planner.py` (correctif D2) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` (guide) ; `docs/coordination/*` (coordination) |
| Fichiers ajoutés | `tests/test_windows_paths.py` ; ce rapport |
| `main` | `b9b7e7d` — **inchangée** |
| Branche auditée par Agent B | `69bf670` — **inchangée** |
| Branche du correctif D1 | `3a59dae` — **inchangée** |
| Artefact non suivi | `tatus --short--branch` — **préservé, hors du commit** |

---

## 10. Points à signaler

1. **Conflit avec l'audit D1 en cours ?** **Aucun conflit de code** : la
   branche D2 part de `3a59dae` et ne modifie que
   `app/orchestration/planner.py` (fichier **non modifié** par le correctif
   D1, qui portait sur `app/orchestration/runner.py`). Les deux branches
   peuvent être auditées séparément, puis fusionnées dans l'ordre
   D1 → D2. Seule entorse : le guide utilisateur est modifié par **les
   deux** branches (`docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md`) — une
   fusion D1+D2 demandera de **resoudre manuellement** les lignes §1, §3, §6
   et §7.1 (conflict de contexte, pas de contenu contradictoire).
2. **Le correctif D1 est-il préservé ?** Oui : les 6 tests
   `tests/test_mission_web_authorization` et les 73 tests
   `tests/test_mission_orchestrator` passent sur cette branche, et le
   correctif D1 (`app/orchestration/runner.py::_ensure_authorization`) est
   intact.
3. **D3** : la proposition de la voie **2-a** (typage explicite du
   paramètre chemin) est submission à Agent B avant toute écriture.

---

## 11. Prochaine action

1. **Audit indépendant par Agent B** du commit de correction D2 :
   - fidélité de l'extraction (lettre de lecteur, espaces, guillemets) ;
   - absence d'élargissement du périmètre (les 21 tests de confinement) ;
   - non-régression D1 ;
   - exécution sous Debian 13.
2. **D3** : choix de la voie (2-a ou 2-b) puis correction séparée, avec
   validation explicite avant toute modification de `app/tools/policy.py`.
3. **Aucune fusion** avant ces validations.
