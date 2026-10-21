# docs/reports/PHASE_6_3E_D3_ANALYSIS_AGENT_A.md — Analyse D3 : faux positifs de la politique sur les valeurs de chemin

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Statut** : **ANALYSE SEULE — AUCUNE MODIFICATION DU CODE DE SÉCURITÉ**
- **Objet** : défaut D3 du rapport de validation Phase 6.3 (§4)
- **Base de l'analyse** : `d3240d2ecce9847cdcc13b49769f482d9c5a1956` (`fix/miles-windows-paths`)
- **Branche de travail** : `fix/miles-d1bis-authorization-response` (même base, aucun commit D3)

> **Rien n'a été modifié dans `app/tools/policy.py`, `app/tools/engine.py`,
> `app/tools/registry.py`, `app/tools/builtin.py` ni
> `app/security/paths.py`.** Ce document est une analyse et une proposition ;
> toute écriture dans ces fichiers exige un accord explicite d'Agent B
> (AGENTS.md, règle 14, et la consigne de la mission).

---

## 1. Les trois validateurs

`app/tools/policy.py` contient trois validateurs de même forme :

| Validateur | Clés (correspondance **exacte**) | Valeurs (correspondance **par sous-chaîne**) |
|------------|----------------------------------|---------------------------------------------|
| `validate_no_shell_access` (l. 74-88) | `shell`, `command`, `cmd`, `exec`, `eval`, `run`, `system` | les mêmes, cherchées **dans** la valeur |
| `validate_no_code_execution` (l. 90-104) | `code`, `script`, `python`, `javascript`, `shell_code`, `source` | les mêmes, cherchées **dans** la valeur |
| `validate_no_secret_access` (l. 106-120) | `password`, `secret`, `api_key`, `token`, `private_key`, `credential`, `apikey`, `access_key`, `secret_key` | les mêmes, cherchées **dans** la valeur |

Structure commune :

```python
for key in self._iter_keys(parameters):        # (1) CLES : correspondance exacte -> correct
    if isinstance(key, str) and key.lower() in forbidden_keys:
        raise PermissionError(...)

for value in self._iter_values(parameters):    # (2) VALEURS : sous-chaîne -> faux positifs
    if isinstance(value, str) and any(k in value.lower() for k in forbidden_keys):
        raise PermissionError(...)
```

Le contrôle **(1)** est précis : un paramètre *nommé* `code` est un vecteur
d'exécution quelle que soit sa valeur. Le contrôle **(2)** ne distingue pas
une **valeur libre** (un fragment de code) d'une **valeur de chemin** (un nom
de répertoire) : c'est là que se logent les faux positifs.

---

## 2. Mesure des faux positifs (politique actuelle)

Valeurs passées dans `{"path": <valeur>}` :

| Valeur | shell | code | secret |
|---------|-------|------|--------|
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
| `docs/coordination` | ok | ok | ok |
| `/home/user/projet` | ok | ok | ok |

**Deux constats :**

1. **D3 proprement dit** : les faux positifs de `code`, `source`, `script`,
   `python`, `javascript` sur les valeurs de chemin — le symptôme rapporté
   (`C:\dev\source\`) est confirmé.
2. **Même famille dans les deux autres validateurs** : `system`, `run`,
   `command`, `exec` (shell) et `secret` (secrets). Corriger uniquement
   `validate_no_code_execution` laisserait `C:\Windows\System32` refusé.

**Portée réelle.** Les racines autorisées sont la racine du projet et `data/`
(`app/security/paths.py::default_allowed_roots`). Un projet situé sous un
dossier dont le nom contient l'une de ces sous-chaînes (par exemple
`C:\dev\source\Milescorp`) rend **toute** mission impossible : chaque appel
d'outil est refusé par la politique, avant même la résolution du chemin. Le
blocage est total, pas marginal.

---

## 3. Comment le moteur identifie les paramètres : le typage explicite est-il applicable ?

### 3.1 Chaîne d'appel réelle

```
app/orchestration/executor.py::Executor.execute
  └─ parameters = dict(step.parameters)
     └─ parameters[step.target_parameter] = valeur issue d'une étape source   (l. 210)
        └─ app/tools/service.py::ToolService.request_tool
           └─ app/tools/engine.py::ToolEngine.execute
              ├─ tool = self._registry.get_tool(tool_id)          (l. 213)  ← la DÉFINITION est disponible
              ├─ self._policy.validate_no_shell_access(parameters) (l. 231)
              ├─ self._policy.validate_no_code_execution(parameters)(l. 232)
              └─ self._policy.validate_no_secret_access(parameters)(l. 233)
```

**Fait favorable n°1** : au point exact où la politique est appliquée, le
moteur dispose déjà de la **définition de l'outil** (`tool`), donc de la
**liste de ses paramètres déclarés** et de leur type. Il n'est pas nécessaire
de deviner le type d'une valeur.

**Fait favorable n°2** : la valeur de chemin injectée par l'exécuteur
(`parameters[step.target_parameter] = value`, l. 210) est **déjà présente**
quand la politique s'applique : l'exception doit donc couvrir ce chemin
injecté, pas seulement le chemin déclaré dans le plan.

**Fait favorable n°3** : la valeur injectée l'est dans le paramètre
`target_parameter`, qui vaut `"path"` pour `action_read_file` — le même nom
que le paramètre déclaré. Une typage par **nom de paramètre** suffit donc.

### 3.2 Le schéma d'outils : combien de paramètres de type chemin ?

Recherche exhaustive de `ToolParameter(` dans `app/` :

| Fichier | Paramètre | Type | Nature |
|---------|-----------|------|--------|
| `app/tools/builtin.py` l. 92 | `action_list_files.path` | `str` | **chemin** |
| `app/tools/builtin.py` l. 98 | `action_list_files.depth` | `int` | nombre |
| `app/tools/builtin.py` l. 126 | `action_read_file.path` | `str` | **chemin** |
| `app/tools/builtin.py` l. 132 | `action_read_file.max_bytes` | `int` | nombre |

Les autres outils enregistrés (`status_read`, `action_datetime`,
`action_workdir`) **n'ont aucun paramètre**.

→ **Il n'existe que 2 paramètres de type chemin dans toute l'application.**
Le typage explicite est donc **trivialement applicable** : deux marqueurs à
poser, aucun outil à réinventer, aucun risque d'oubli massif.

### 3.3 L'autre point d'application : le planificateur

`app/orchestration/planner.py::validate_plan_payload` (l. 283-290) applique
**aussi** un contrôle par sous-chaîne aux valeurs :

```python
if isinstance(value, str) and any(
    forbidden in value.lower()
    for forbidden in ("shell", "rm -rf", "cmd /c", "powershell -")
):
    raise PlanRejected(...)
```

Ce contrôle est **plus ciblé** que celui de la politique (il vise des
commandes, pas des mots) et il est **déjà limité aux valeurs de type chaîne** ;
il ne produit pas de faux positif sur `C:\dev\source`. Il connaît par
ailleurs les types déclarés (`declared = {p.name: p for p in tool.parameters}`)
→ il est lui aussi en mesure d'appliquer une exception « paramètre de type
chemin » si cela est décidé. **Aucune modification n'y est nécessaire pour
D3** ; il est signalé pour cohérence.

### 3.4 Le confinement, qui reste l'autorité

Quel que soit le correctif retenu, un chemin de type chemin reste soumis à :

- `app/security/paths.py::resolve_authorized_path` (racines : projet + `data/`,
  résolution canonique, symlinks résolus) ;
- `app/tools/local_actions.py` : refus des fichiers sensibles (`.env`, clés
  privées) et bornes de lecture.

C'est **ce** contrôle qui décide de l'accès ; la politique n'est qu'une
défense en profondeur **en amont**. Un chemin qui contient « code » mais qui
sort des racines autorisées doit rester refusé — par le confinement, pas par
la politique.

### 3.5 Les tests existants n'épinglent pas le comportement fautif

`tests/test_tool_policy.py` (11 tests) ne vérifie que des cas de **clés**
(`{"code": "print(1)"}`, `{"source": "…"}`…) et des valeurs libres autorisées
(`{"message": "bonjour"}`). **Aucun test n'épingle le refus d'un chemin par
sous-chaîne** → un correctif D3 ne casserait pas les attentes existantes, il
faudrait **ajouter** des tests.

---

## 4. Les quatre catégories à distinguer

| Catégorie | Définition | Exemple | Traitement attendu |
|-----------|-----------|---------|---------------------|
| **A. Clé sensible** | le *nom* du paramètre est un vecteur (`code`, `script`, `python`, `javascript`, `shell_code`, `source`, `shell`, `command`, `cmd`, `exec`, `eval`, `run`, `system`, `password`, `secret`, `api_key`, `token`…) | `{"code": "print(1)"}` | **toujours refusé**, quelle que soit la valeur — contrôle **exact**, inchangé |
| **B. Valeur libre** | valeur d'un paramètre qui n'est **pas** un chemin | `{"message": "import os"}` | **inchangé** : refus par sous-chaîne si elle contient un mot interdit |
| **C. Chemin** | valeur d'un paramètre **déclaré** de type chemin | `{"path": "C:\\dev\\source"}` | **accepté par la politique** (fauxpositif à supprimer), puis soumis au **confinement** ; contrôle **structurel** obligatoire (pas de métacaractère) |
| **D. Métacaractère** | caractère de commande dans une valeur | `{"path": "C:\\x; rm -rf /"}` | **toujours refusé**, chemin ou non |

---

## 5. Matrice de tests proposée (à écrire lors du correctif)

### 5.1 Doivent rester **REFUSÉS**

| # | Cas | Catégorie | Attendu | Autorité du refus |
|---|-----|-----------|---------|-------------------|
| R1 | `{"code": "print(1)"}` | A | refus | clé (exact) |
| R2 | `{"script": "alert(1)"}` | A | refus | clé |
| R3 | `{"python": "import os"}` | A | refus | clé |
| R4 | `{"javascript": "eval('1')"}` | A | refus | clé |
| R5 | `{"shell_code": "whoami"}` | A | refus | clé |
| R6 | `{"source": "open('/etc/passwd')"}` | A | refus | clé |
| R7 | `{"shell": "ls"}` / `{"command": "rm -rf /"}` / `{"cmd": …}` / `{"exec": …}` / `{"eval": …}` / `{"run": …}` / `{"system": …}` | A | refus | clé |
| R8 | `{"password": "…"}` / `{"secret": "…"}` / `{"api_key": "…"}` / `{"token": "…"}` / `{"private_key": …}` / `{"credential": …}` | A | refus | clé |
| R9 | `{"message": "import os"}` | B | refus | sous-chaîne (inchangé) |
| R10 | `{"message": "eval(x)"}`, `{"query": "rm -rf /"}` | B | refus | sous-chaîne |
| R11 | `{"message": "script"}`, `{"query": "code"}` | B | refus | sous-chaîne (**inchangé**) |
| R12 | `{"path": "C:\\x; rm -rf /"}` | D | refus | contrôle structurel |
| R13 | `{"path": "C:\\x`whoami`"}`, `{"path": "C:\\x|c"}`, `{"path": "C:\\x&y"}`, `{"path": "C:\\x>y"}`, `{"path": "C:\\x<y"}` | D | refus | contrôle structurel |
| R14 | `{"path": "C:\\Windows\\System32"}` (hors racines) | C | refus | **confinement** (`resolve_authorized_path`) |
| R15 | `{"path": "../docs"}` (traversée) | C | refus | confinement |
| R16 | `{"path": "C:\\dev\\source\\..\\..\\Windows"}` | C | refus | confinement (résolution canonique) |
| R17 | clé sensible **imbriquée** : `{"options": {"code": "x"}}` | A | refus | clé (récursion conservée) |
| R18 | `{"path": "C:\\x\nrm -rf /"}` (retour ligne) | D | refus | contrôle structurel |

### 5.2 Doivent devenir **ACCEPTÉS** (par la politique ; le confinement tranche ensuite)

| # | Cas | Catégorie | Attendu |
|---|-----|-----------|---------|
| A1 | `{"path": "C:\\dev\\source"}` | C | accepté par la politique, puis refusé par le confinement s'il est hors racines |
| A2 | `{"path": "C:\\Users\\X\\Documents\\code"}` | C | idem |
| A3 | `{"path": "C:\\projet\\python\\app"}` | C | idem |
| A4 | `{"path": "C:\\Users\\X\\mon-script-de-notes.txt"}` | C | idem |
| A5 | `{"path": "C:\\Windows\\System32"}` | C | accepté par la politique, refusé par le confinement |
| A6 | `{"path": "C:\\Users\\X\\secret\\notes"}` | C | idem |
| A7 | `{"path": "C:\\Users\\X\\AppData\\Local\\run"}` | C | idem |
| A8 | `{"path": "C:\\Users\\X\\Desktop\\command"}` | C | idem |
| A9 | `{"path": "docs/coordination"}` | C | accepté (et exécuté) |
| A10 | `{"message": "bonjour"}` | B | accepté (inchangé) |
| A11 | `{"depth": 2}`, `{"max_bytes": 2048}` | — | acceptés (types non chaîne) |

### 5.3 Tests de bout en bout à ajouter

| # | Test | Résultat attendu |
|---|-------|------------------|
| E1 | mission sur un projet situé sous `…\source\` | la mission **aboutit** (`completed`) |
| E2 | `action_list_files` avec `path` contenant `code` | l'outil s'exécute (refus par confinement si hors racines) |
| E3 | `action_read_file` avec `path` contenant `script` | l'outil s'exécute |
| E4 | la politique est toujours appliquée aux **clés** | R1-R8 restent refusés après correctif |
| E5 | les 11 tests existants de `test_tool_policy.py` | restent verts |
| E6 | les 70 tests d'audit d'Agent B | restent verts |
| E7 | un chemin avec métacaractère est refusé avant exécution | R12-R13 |

---

## 6. Risques de contournement

| # | Risque | Analyse | Parade |
|---|--------|---------|---------|
| 1 | Un code glissé dans un **paramètre de type chemin** (`path = "C:\x\..\evil.py"`) n'est plus vu par le contrôle par sous-chaîne | MILES n'a **aucun outil d'exécution** : la valeur est un chemin, il est résolu et confiné par `resolve_authorized_path`, et les fichiers sensibles sont refusés par `read_file_handler`. Un fichier `.py` **lu** n'est pas **exécuté**. | Le confinement reste l'autorité ; ajouter le contrôle structurel (R12-R13) ; conserver la lecture comme seule capacité |
| 2 | Un nom de répertoire « piégé » (`C:\source\malicious.cmd`) passerait le filtre par sous-chaîne | Un fichier `.cmd` est un *contenu*, pas une commande : il ne serait pas exécuté. Le handler `read_file` refuse les fichiers sensibles ; un `.cmd` serait lu comme du texte. | Le contrôle structurel (métacaractères) ; le confinement ; le refus des fichiers sensibles |
| 3 | Retrait du filtre sur les valeurs de chemin = **affaiblissement** de la défense en profondeur | Vrai si le retrait est **global**. | Le retrait doit être **borné aux paramètres déclarés de type chemin** (2 sur 4 paramètres de l'application), jamais « à toute valeur qui ressemble à un chemin » |
| 4 | Un modèle pourrait déclarer un paramètre libre comme « chemin » pour contourner le filtre | Le typage est porté par le **registre**, écrit par l'application, **jamais par le modèle**. Le modèle ne fournit que des *valeurs*, et la validation du plan refuse tout paramètre non déclaré (`engine.py` l. 251-266) et tout type incorrect (`planner.py` l. 267-282). | Le typage est une donnée de l'application ; le modèle ne peut pas le modifier |
| 5 | Un paramètre chemin imbriqué (`{"options": {"path": …}}`) ne serait pas reconnu comme chemin | Le typage par **nom de paramètre** ne couvre que le premier niveau. | Soit on accepte cette limite (MILES n'a pas de paramètres imbriqués : les 4 paramètres sont plats), soit on propage le typage récursivement |
| 6 | La correction rompt un audit de sécurité existant | Les 70 tests d'audit d'Agent B vérifient notamment que la politique refuse des clés sensibles et que le confinement fonctionne. | Les tests d'audit doivent être rejoués **tels quels** ; la matrice §5 doit être couverte par de nouveaux tests |
| 7 | Un contrôle structurel trop strict casse des chemins légitimes | Un chemin Windows peut contenir `&` (rare), `$`, `~`… | Le contrôle structurel doit porter sur un ensemble **mince** de métacaractères de commande (`;`, `|`, `&`, backtick, `$`, `<`, `>`, retour ligne) et être **testé** sur des chemins légitimes |

---

## 7. Modification minimale proposée

**Aucune n'a été appliquée.** Deux voies, avec recommandation.

### Voie 1 — La politique ignore les valeurs de type chemin (recommandée)

| Fichier | Modification | Volume |
|---------|--------------|--------|
| `app/tools/registry.py` | ajouter `is_path: bool = False` à `ToolParameter` (+ 2 lignes de documentation) | ~3 lignes |
| `app/tools/builtin.py` | `is_path=True` sur `action_list_files.path` et `action_read_file.path` | 2 lignes |
| `app/tools/policy.py` | les trois validateurs acceptent un ensemble de **noms de paramètres de type chemin** ; la boucle sur les **valeurs** les ignore, et les remplace par un contrôle **structurel** (métacaractères) | ~30 lignes |
| `app/tools/engine.py` | transmettre au validateur l'ensemble des paramètres de type chemin de l'outil (`tool.parameters`) | ~4 lignes |

Points forts :

- le **type est déclaré** dans le schéma : aucun heuristique, pas de
  « ressemble à un chemin » ;
- le refus des **clés** est **strictement inchangé** (contrôle exact) ;
- les valeurs libres restent soumises au contrôle par sous-chaîne ;
- un chemin reçoit un contrôle **structurel** (métacaractères) : la
  protection contre l'injection de commande est conservée, sans faux positif
  sur les noms de répertoires ;
- le confinement (`resolve_authorized_path`) reste l'autorité sur l'accès.

Point de vigilance : la politique n'est plus appelée qu'avec un contexte
supplémentaire → **c'est du code de sécurité**, la modification exige une
revue dédiée.

### Voie 2 — Filtrer les valeurs de chemin **avant** la politique (recommandée par l'agent A)

| Fichier | Modification | Volume |
|---------|--------------|--------|
| `app/tools/registry.py` | `is_path: bool = False` sur `ToolParameter` | ~3 lignes |
| `app/tools/builtin.py` | `is_path=True` sur les 2 paramètres `path` | 2 lignes |
| `app/security/paths.py` | nouvelle fonction `validate_path_value(value)` : contrôle **structurel** des métacaractères (et rien d'autre) | ~15 lignes |
| `app/tools/engine.py` | les valeurs des paramètres de type chemin sont **retirées** du dictionnaire transmis à la politique, et validées par `validate_path_value` | ~6 lignes |

Points forts :

- **`app/tools/policy.py` n'est PAS modifié** : la politique de sécurité
  reste intacte, ce qui réduit fortement la charge de revue ;
- le contrôle par sous-chaîne continue de s'appliquer à **tout** ce qui n'est
  pas un chemin déclaré ;
- le confinement reste inchangé.

Point de vigilance : la politique ne « voit » plus les valeurs de chemin —
c'est un choix assumé (le contrôle structurel + le confinement les remplacent),
et il faut que ce choix soit **explicite et assumé** par l'auditeur.

### Recommandation d'Agent A

**Voie 2**, pour trois raisons : (1) le fichier de politique de sécurité
n'est pas touché ; (2) le mécanisme est plus simple et plus lisible ; (3) le
risque de divergence entre la politique et le moteur est nul. La voie 1 reste
préférable si l'auditeur considère que la politique doit rester le point
unique de contrôle.

Dans les deux cas : **2 marqueurs de type + 1 contrôle structurel + le
confinement inchangé**, et la matrice de tests §5 doit être couverte.

### Ordre de grandeur

Le correctif D3 représente environ **30 lignes** sur 4 à 5 fichiers, dont
**aucun** ne touche au périmètre d'accès (les racines autorisées, le
confinement, la politique de lecture) : le **périmètre de lecture/écriture
n'est pas élargi**, seuls des faux positifs sur des noms de répertoires
disparaissent.

---

## 8. Décisions demandées à Agent B

1. **Voie 1 ou voie 2** (§7) ?
2. Le périmètre du contrôle structurel : quels métacaractères retenir
   (`;`, `|`, `&`, backtick, `$`, `<`, `>`, retour ligne) ? Faut-il en
   retirer certains pour ne pas casser des chemins légitimes ?
3. Le contrôle de session de D1-bis (`session_mismatch`) : la voie 2 rend-elle
   le typage des paramètres encore plus nécessaire, ou est-ce sans rapport ?
4. Qui écrit le correctif D3, et dans quel lot (D3 seul, ou D3 + D1-ter) ?
5. Faut-il appliquer le correctif racine « mission occupée » (§6.1 du
   rapport D1-bis) dans le même lot ?

---

## 9. Ce qui n'a pas été fait, et pourquoi

| Action | Raison |
|--------|--------|
| Modification de `app/tools/policy.py` | consigne explicite de la mission : ne modifier aucun code de sécurité D3 sans accord explicite |
| Écriture des tests de la matrice §5 | ils ne peuvent pas être écrits **avant** le choix de la voie (le comportement attendu diffère) ; les écrire maintenant figerait un choix qui appartient à l'auditeur |
| Correction du défaut « mission occupée » (D1-ter) | hors périmètre de D3 ; proposition détaillée dans le rapport D1-bis §6.1 |
| Élargissement des racines autorisées | **hors sujet** : D3 ne porte pas sur le périmètre d'accès, et rien ne l'autorisait |
