# MILES — Plan de test phase 6 (mission, outils, interface web)

Guide destiné au développeur pour tester **aujourd'hui**, sur sa machine, ce
que MILES sait faire réellement.

> Toutes les commandes de ce guide ont été **exécutées avec succès** le
> 2026-10-21 sur Windows (Python 3.12.10), sauf celles explicitement
> signalées comme non exécutables ou comme bloquées par un défaut connu
> (voir §6).

---

## 1. Ce que vous pouvez tester aujourd'hui

| # | Fonction | État | Comment |
|---|----------|-------|---------|
| 1 | Démarrage / arrêt de MILES (CLI) | ✅ opérationnel | §4.1 |
| 2 | Commandes d'aide et d'état (`/help`, `/status`, `/provider`, `/tools`) | ✅ opérationnel | §4.2 |
| 3 | Outils isolés (`/tool <id>`) | ✅ opérationnel (avec confirmation pour les outils MEDIUM) | §4.3 |
| 4 | Mission simple en lecture seule | ✅ opérationnel | §4.4 |
| 5 | Demande de clarification (réponse à une question) | ✅ opérationnel | §4.5 |
| 6 | Autorisation d'une mission (CLI) et budgets globaux | ✅ opérationnel | §4.6 |
| 7 | Limites : durée, appels d'outils, échanges, erreurs | ✅ opérationnel (voir la réserve sur les étapes, §4.7) | §4.7 |
| 8 | Consultation / reprise / annulation d'une mission | ✅ opérationnel | §4.8 |
| 9 | Interface web locale (auth, refus d'origine, types de contenu) | ✅ opérationnel | §5.1 |
| 10 | Mission **déclenchée depuis l'interface web** | ✅ opérationnelle (défaut D1 corrigé, branche `fix/miles-d1-web-authorization`) | §5.2 |
| 11 | Conversation avec un fournisseur IA distant | ⚠️ dépend d'un service externe payant | §7 |
| 12 | Lecture de fichiers volumineux / capteurs matériels | ⚠️ non applicable | §7 |

---

## 2. Prérequis

| Élément | Exigence | Vérifié |
|---------|----------|---------|
| Python | 3.10 ou supérieur (3.12.10 utilisé) | ✅ |
| Paquets Python | **aucun** pour le mode texte (`requirements.txt` ne contient que des dépendances vocales optionnelles, commentées) | ✅ |
| Réseau | **aucun** requis si aucun fournisseur n'est configuré | ✅ |
| Fournisseur IA | optionnel ; sans lui, MILES démarre et le planificateur **déterministe** prend le relais | ✅ |
| Clé API | **aucune** requise pour tout ce qui est décrit ici | ✅ |
| Port libre | `8080` pour l'interface web (ou `--web-port <N>`) | ✅ |

> **Coût API — à lire avant de lancer une mission.** MILES a **toujours**
> un fournisseur configuré (par défaut `remote` vers `http://localhost:8000` ;
> `Settings` n'accepte que `remote` ou `local`). Une mission déclenche donc
> **2 appels à ce fournisseur** : 1 pour proposer le plan, 1 pour l'analyse
> qualitative du rapport. Si votre `.env` pointe vers une API payante, chaque
> mission coûte deux appels.
>
> - **Pour un test sans coût** : laissez le fournisseur par défaut
>   (`http://localhost:8000`, non joignable) et réduisez le délai d'attente :
>   ```powershell
>   $env:MILES_REMOTE_TIMEOUT = "1"
>   ```
>   Le planificateur bascule alors sur le plan **déterministe** en ~1 s, sans
>   coût. Le rapport indique alors « Planificateur : deterministe+repli ».
> - **Pour un test avec le vrai fournisseur IA** : c'est un test de service
>   externe (§7.2), pas un test logiciel.

---

## 3. Installation (si ce n'est pas déjà fait)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git checkout fix/miles-mission-bounds
git pull --ff-only
py -m venv .venv
.\.venv\Scripts\Activate.ps1      # ou : .\.venv\Scripts\python.exe ...
```

Aucune installation `pip` n'est nécessaire (bibliothèque standard uniquement).

---

## 4. Procédure de test — interface en ligne de commande

> Astuce pour automatiser : les commandes se saisissent au clavier. Pour un
> test scripté, redirigez l'entrée (`@("/mission ...","o","/quit") | python miles.py`).

### 4.1 Démarrage et arrêt

```powershell
python miles.py
```
Attendu : bandeau d'accueil, nom du fournisseur, invite `> `. Arrêt : `/quit`
(ou `Ctrl+C`). Code de sortie vérifié : **0**.

### 4.2 Commandes d'aide et d'état

Tapez `/help`, `/status`, `/provider`, `/tools`.
`/tools` liste les 5 outils enregistrés avec leur niveau de risque et
l'indication « confirmation requise » pour les outils MEDIUM.

### 4.3 Exécution d'un outil isolé

```
/tool action_datetime
```
→ `[Outil exécuté] action_datetime` + l'horodatage.

Pour un outil de risque MEDIUM (lecture de fichier), le terminal demande une
confirmation explicite :

```
/tool action_list_files path=data
```
→ « Confirmation humaine requise » → répondez `o` pour valider, autre chose
pour annuler.

### 4.4 Mission simple (lecture seule)

  ```
  /mission Analyse le dossier docs/
  ```
  Puis répondez `o` à la demande d'autorisation.

  *Astuce* : lancez avec `$env:MILES_REMOTE_TIMEOUT = "1"` pour ne pas
  attendre le délai du fournisseur (voir §2).

**Résultat vérifié** : 5 étapes, 5 appels d'outils, 1 échange, rapport complet
avec les sections *Faits observés*, *Erreurs*, *Étapes non terminées*,
*Détail des étapes*, et le **motif d'arrêt** `completed`.

Le rapport commence par :
```
Budget consommé : 1.5 s d'exécution, 5 étape(s), 5 appel(s) d'outil(s), 2 échange(s) utilisateur.
Motif d'arrêt : completed
```

### 4.5 Répondre à une demande de clarification

Un objectif qui ne désigne aucun dossier déclenche une question :

```
/mission Analyse l'organisation
```
→ « Quel dossier dois-je analyser ? Indiquez un chemin (ex. « app/ » ou
« docs/coordination »). »

Répondez `docs/` : la mission est replanifiée, puis demande son autorisation
(2 échanges au total), puis s'exécute.

### 4.6 Autorisation d'une mission

La demande d'autorisation liste le périmètre demandé :
```
Autoriser l'accès en lecture dans <dossier> pour les outils : action_list_files, action_read_file ?
```
Répondez `o` (autoriser) ou `n` (refuser → la mission s'arrête en `failed`).

### 4.7 Provoquer les dépassements de limites

Les plafonds sont configurables par variables d'environnement (valeurs par
défaut entre parenthèses) :

| Variable | Défaut | Effet |
|----------|--------|-------|
| `MILES_MISSION_MAX_STEPS` | 12 | nombre d'étapes cumulées par mission |
| `MILES_MISSION_MAX_TOOL_CALLS` | 24 | appels d'outils cumulés |
| `MILES_MISSION_MAX_DURATION_SECONDS` | 120 | durée d'exécution cumulée |
| `MILES_MISSION_MAX_INTERACTIONS` | 5 | échanges avec l'utilisateur |

Exemple (PowerShell, une commande par cas) :

```powershell
$env:MILES_MISSION_MAX_TOOL_CALLS = "1"
@("/mission Analyse le dossier docs/","o","/quit") | python miles.py
Remove-Item Env:MILES_MISSION_MAX_TOOL_CALLS
```
→ `Motif d'arrêt : tool_call_budget_exceeded` et
« Nombre maximal d'appels d'outils atteint (1). »

Résultats **vérifiés** :

| Cas | Motif d'arrêt observé |
|-----|----------------------|
| `MILES_MISSION_MAX_TOOL_CALLS=1` | `tool_call_budget_exceeded` |
| `MILES_MISSION_MAX_DURATION_SECONDS=1` | `time_budget_exceeded` |
| `MILES_MISSION_MAX_INTERACTIONS=1` (scénario à 2 demandes) | `interaction_budget_exceeded` |
| `MILES_MISSION_MAX_STEPS=2` | `completed` — **réserve** : voir ci-dessous |

> **Réserve sur le plafond d'étapes.** Avec le planificateur *déterministe*,
> le plan est automatiquement dimensionné pour ne pas dépasser le budget
> (`max_steps − 2` lectures) : la mission s'arrête donc proprement en
> `completed` sans jamais atteindre le plafond. Le plafond d'étapes **est**
> appliqué par le code et couvert par les tests unitaires
> (`tests/test_mission_bounds.py::test_plafond_d_etapes_global`), mais il
> n'est **pas observable depuis le terminal** tant que le planificateur
> déterministe est utilisé. Avec un plan fourni par le fournisseur IA, il
> devient observable.

### 4.8 Consulter, reprendre, annuler une mission

```
/missions                  → liste des missions (identifiant, état, objectif)
/mission-status <id>       → plan, budget, motif d'arrêt, erreurs
/mission-resume <id>       → reprend une mission interrompue
/mission-cancel <id>       → arrête une mission en cours
```

Note : `/mission-resume` sur une mission déjà `completed` la renvoie sans
action ; `/mission-cancel` sur une mission terminée affiche « Mission
<id> introuvable ou déjà terminée. » (comportement vérifié).

### 4.9 Vérifier les erreurs

- Chemin hors périmètre : `/mission Analyse C:/Windows` → `Motif d'arrêt : failed`
  et « Chemin hors périmètre autorisé ».
- Identifiant inconnu : `/mission-status inexistante` → « Mission inconnue :
  inexistante ».
- Mission annulée : motif d'arrêt `cancelled`.

---

## 5. Procédure de test — interface web

### 5.1 Démarrage, connexion et protections

```powershell
$env:MILES_WEB_AUTH_TOKEN = "un-jeton-que-vous-inventez"
python miles.py --web --web-port 8123
```
Un jeton d'accès est affiché **une seule fois** (si aucun n'est configuré,
MILES en génère un). Le serveur n'écoute que sur `127.0.0.1`.

Puis, dans un autre terminal :

```powershell
# 1. la page publique
curl.exe http://127.0.0.1:8123/            # 200 (page de connexion)

# 2. connexion
curl.exe -X POST http://127.0.0.1:8123/session `
  -H "Content-Type: application/json" -d "{\"token\":\"un-jeton-que-vous-inventez\"}"
# => {"session_id": "...", "csrf_token": "...", "user_id": "local", ...}

# 3. sans session -> refus
curl.exe http://127.0.0.1:8123/status      # 401

# 4. avec session -> ok
curl.exe http://127.0.0.1:8123/status -H "X-MILES-Session: <session_id>"

# 5. origine étrangère -> refus
curl.exe -X POST http://127.0.0.1:8123/tool `
  -H "Content-Type: application/json" -H "Origin: http://site-malveillant.example" `
  -d "{\"tool\":\"status_read\"}"        # 403

# 6. type de contenu incorrect -> refus
curl.exe -X POST http://127.0.0.1:8123/tool `
  -H "Content-Type: text/plain" -d "{}"  # 415
```

Résultats **vérifiés** : 200 / 200 / 401 / 200 / 403 / 415.

### 5.2 Mission depuis l'interface web

`POST /mission` crée la mission et la démarre en arrière-plan. La mission
atteint l'état `awaiting_authorization` ; après `POST /mission/<id>/authorize`
(avec le jeton d'approbation renvoyé dans `pending.approval_token`), elle se
**termine** : état final `completed`, 5 étapes / 5 appels d'outils / 1 échange.
Le défaut D1 (l'autorisation ne convergeait pas) est corrigé dans la branche
`fix/miles-d1-web-authorization`.

---

## 6. Défauts connus qui bloquent une partie des tests

Ces défauts ont été **mis en évidence par cette campagne de validation**. Ils
n'ont **pas** été corrigés (correction à valider séparément) ; ils sont
documentés dans `docs/reports/PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md`.

| # | Gravité | Symptôme | Cause | Correctif proposé |
|---|----------|----------|-------|-------------------|
| **D1** | Élevée | **CORRIGÉ** (branche `fix/miles-d1-web-authorization`) : l'autorisation web converge et la mission se termine. | Le registre d'autorisations était interrogé avec la session du runner au lieu de celle du client. | Une ligne : interroger avec `mission.session_id or self.session_id`. |
| **D1-bis** | Mineure | `POST /mission/<id>/authorize` renvoie `{"approved": true}` même quand le jeton d'approbation est invalide : la validation a lieu dans le fil d'exécution, dont l'exception n'est pas retournée. Aucune élévation de privilège (l'autorisation n'est pas accordée) ; la réponse HTTP est trompeuse. | Valider le jeton d'approbation de façon synchrone dans `WebApp.authorize_mission` avant de démarrer le fil. |
| **D2** | Moyenne | Un chemin Windows absolu perd sa lettre de lecteur : `C:/Windows` → `/Windows`. La mission analyse alors le mauvais répertoire et le message d'erreur est trompeur. | `app/orchestration/planner.py::extract_target_path` : la classe de caractères du chemin n'inclut pas `:`. | Inclure `:` (et un cas de test). |
| **D3** | Moyenne | Toute valeur de paramètre contenant `code`, `source`, `script`, `python` ou `javascript` est refusée : les chemins légitimes (`C:\dev\source\`, `C:\Users\X\Documents\code\`) sont rejetés et la mission ne peut pas les analyser. | `app/tools/policy.py::validate_no_code_execution` applique un contrôle par sous-chaîne aux VALEURS, y compris aux chemins. | Ne pas appliquer ce contrôle par sous-chaîne aux valeurs de type chemin (le contrôle sur les CLÉS est conservé). **Ne pas modifier sans validation explicite : c'est du code de sécurité.** |
| **D4** | Mineure | Avec un fournisseur configuré mais injoignable, une mission attend le délai du fournisseur (jusqu'à 30 s) avant le repli déterministe ; l'interface paraît figée. | Le planificateur interroge le fournisseur avant de basculer. | Documenté ; contournement : ne pas configurer de fournisseur (§2). |

---

## 7. Répartition des tests

### 7.1 Tests logiciels (aucun service externe, aucun matériel)

| Test | Commande | Résultat vérifié |
|------|----------|------------------|
| Suite complète | `python -m unittest discover -s tests` | **528 tests, 0 échec, 4 ignorés** (limites Windows : 3 liens symboliques, 1 `/proc/self/fd`) |
| Garde-fou FPS | `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| Orchestrateur | `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| Sécurité web | `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| Contrat IPC | `python -m unittest tests.contrat_ipc` | 18 tests, 0 échec |
| Outils | `python -m unittest tests.test_tool_integration` | 40 tests, 0 échec |
| Démarrage/arrêt CLI | §4.1 | code de sortie 0 |
| Mission, clarification, autorisation, budgets, erreurs | §4.4 → §4.9 | voir les motifs d'arrêt observés |
| Interface web (auth, refus) | §5.1 | 200 / 200 / 401 / 200 / 403 / 415 |

### 7.2 Tests nécessitant une API ou un service externe

| Test | Prérequis | État |
|------|-----------|-------|
| Conversation IA (message utilisateur → réponse) | endpoint compatible OpenAI + clé valide | **non exécuté** (coût API) ; le repli propre « aucun fournisseur IA configuré » **a été vérifié** |
| Plan de mission proposé par le fournisseur IA | idem | **non exécuté** ; le repli déterministe **a été vérifié** (le planificateur signale « Repli : échec de l'appel au fournisseur IA ») |
| Analyse qualitative du rapport | idem | non exécuté ; le rapport indique explicitement « non produite » |

### 7.3 Tests nécessitant du matériel

| Test | Matériel requis | État |
|------|-----------------|-------|
| Température / utilisation GPU | `nvidia-smi` (carte NVIDIA) | non applicable hors de cette machine ; les valeurs affichées proviennent de `nvidia-smi` |
| Lecture de fichiers volumineux | disque local | non exécuté (hors périmètre du point 8) |
| Capteurs (batterie, etc.) | matériel portable | hors périmètre |

---

## 8. Comment ¶ublier la validation

Consigner pour chaque test : la commande exacte, la sortie observée, le SHA
utilisé (`git rev-parse HEAD`) et la plateforme. Les rapports de la Phase 6
sont dans `docs/reports/` ; ce guide dans `docs/user_guide/`.
