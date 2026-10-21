# docs/reports/PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md — Ce qui est testable aujourd'hui (validation utilisateur)

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Dépôt** : `C:\Users\StanC\Desktop\Milescorp` (remote `https://github.com/Miles-corp/Milescorp.git`)
- **Branche de travail** : `fix/miles-mission-bounds` (aucun commit de code produit par cette mission)
- **Code testé** : `615b0abd984f3c2d03d891276c6a0c3c03e3a706` (tête de branche `3d0bfb8`)
- **`main`** : `b9b7e7d` — **inchangée**
- **Branche auditée par Agent B** : `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **inchangée**
- **Livrable developer** : `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md`

> **Aucun fichier de code n'a été modifié par cette mission** : le diagnostic
> a été fait sur un environnement de test isolé (worktree jetable) et les
> corrections proposées sont documentées, **non appliquées**.

---

## 1. Environnement de test (isolation)

| Élément | Valeur |
|---------|--------|
| Méthode | `git worktree add --detach <temp> fix/miles-mission-bounds` |
| Chemin | `C:\Users\StanC\AppData\Local\Temp\miles-val` (hors du dépôt) |
| `.env` | **absent** (aucune clé API copiée) |
| `config/config.json` | absent (config par défaut) |
| `data/` | ne contient que `.gitkeep` → les bases `conversations.db` et `missions.db` ont été **créées par le test**, jamais celles du développeur |
| Données réelles du développeur | **non touchées** : `data/conversations.db` (20/10 13:13), `data/memory.db` (20/10 12:33), `data/missions.db` (21/10 10:50 — écrit par la mission Phase 6.2, **vide de toute mission**) |
| Nettoyage | worktree et bases de test supprimés après la campagne ; aucun fichier du dépôt modifié |

---

## 2. Commandes disponibles (vérifiées dans le code et exécutées)

| Commande | Effet | Exécutée |
|----------|-------|-----------|
| `python miles.py --help` | options, dont `--web` / `--web-port` | ✅ (code 0) |
| `python miles.py` | interface en ligne de commande | ✅ (arrêt propre, code 0) |
| `python miles.py --provider remote\|local` | force un fournisseur | non exécuté (service externe) |
| `python miles.py --list-conversations` | liste les conversations | non exécuté (hors périmètre) |
| `python miles.py --new-conversation` / `--conversation <id>` | gestion de l'historique | non exécuté (hors périmètre) |
| `python miles.py --no-persist` | mode éphémère | non exécuté (hors périmètre) |
| `python miles.py --web [--web-port N]` | interface web locale (127.0.0.1) | ✅ |
| `python -m unittest discover -s tests` | suite complète | ✅ 528 tests, 0 échec, 4 ignorés |
| `python -m unittest tests.<fichier>` | test ciblé | ✅ |

**Dépendances** : aucune (bibliothèque standard). `requirements.txt` ne
contient que des dépendances vocales **commentées**. `pyproject.toml`
absent.

**Configuration** : `config/config.json` absent (optionnel, un
`config/config.json.example` est fourni) ; `.env` présent sur la machine du
développeur (variables lues : `MILES_PROVIDER`, `MILES_REMOTE_BASE_URL`,
`MILES_REMOTE_MODEL`, `MILES_REMOTE_TIMEOUT`, `MILES_REMOTE_API_KEY`,
`MILES_LOCAL_*`, `MILES_HISTORY_LIMIT`, `MILES_VOICE_ENABLED`,
`MILES_MEMORY_*`). **Aucune valeur n'a été affichée ni journalisée.**

**Service externe** : un service écoute sur `127.0.0.1:8000` (le
fournisseur distant par défaut). Un appel à ce fournisseur est effectué par
mission (2 appels : plan + analyse qualitative) → d'où le délai observé.

---

## 3. Résultats des tests réellement exécutés

### 3.1 Suite de tests automatisés (environnement isolé)

| Exécution | Résultat |
|-----------|----------|
| `python -m unittest discover -s tests` | **528 tests, 0 échec, 4 ignorés** |
| `python -m unittest tests.test_mission_bounds` | 20 OK, 0 échec |
| `python -m unittest tests.test_mission_orchestrator` | 73 OK, 0 échec |
| `python -m unittest tests.test_web_security_phase6_1` | 35 OK, 0 échec |
| `python -m unittest tests.test_tool_integration` | 40 OK, 0 échec |

Les 4 tests ignorés sont des **limites de plateforme Windows** (3 liens
symboliques, 1 `/proc/self/fd`) ; ils s'exécutent sous Debian 13.

### 3.2 Interface en ligne de commande (exécutée)

| Test | Résultat observé |
|------|------------------|
| Démarrage + `/help` + `/status` + `/quit` | bandeau d'accueil, 16 commandes listées, **code de sortie 0** |
| `/tools` | 5 outils listés avec risque et mention « confirmation requise » (MEDIUM) |
| `/tool action_datetime` | `[Outil exécuté]` + horodatage |
| Mission simple `/mission Analyse le dossier docs/` + `o` | 5 étapes, 5 appels d'outils, 1 échange, **motif `completed`**, rapport complet |
| Clarification `/mission Analyse l'organisation` + `docs/` + `o` | question posée, replanification, **2 échanges**, motif `completed` |
| `/missions` | liste des missions (identifiant, état, objectif) |
| `/mission-status <id>` | plan, budget consommé, motif d'arrêt, erreurs |
| `/mission-resume <id>` | mission terminée → renvoyée sans action |
| `/mission-cancel <id>` | mission terminée → « introuvable ou déjà terminée » |
| Erreur : chemin hors périmètre (`/mission Analyse C:/Windows`) | **motif `failed`**, « Chemin hors périmètre autorisé » |
| Erreur : identifiant inconnu | « Mission inconnue : … » |

### 3.3 Plafonds (exécutés, via variables d'environnement)

| Plafond testé | Motif d'arrêt observé | Message |
|---------------|-----------------------|---------|
| `MILES_MISSION_MAX_TOOL_CALLS=1` | `tool_call_budget_exceeded` | « Nombre maximal d'appels d'outils atteint (1). » |
| `MILES_MISSION_MAX_DURATION_SECONDS=1` | `time_budget_exceeded` | « Durée maximale de mission atteinte (120 s). » |
| `MILES_MISSION_MAX_INTERACTIONS=1` (scénario à 2 demandes) | `interaction_budget_exceeded` | « Nombre maximal d'échanges avec l'utilisateur atteint (1). » |
| `MILES_MISSION_MAX_STEPS=2` | `completed` | **réserve** : le planificateur déterministe dimensionne le plan au budget, donc le plafond n'est pas atteint (voir §5) |

### 3.4 Interface web (exécutée)

| Test | Résultat observé |
|------|------------------|
| `GET /` | **200** (page de connexion, 10 345 octets) |
| `POST /session` (avec jeton) | **200** — `session_id`, `csrf_token`, `user_id` |
| `GET /status`, `/missions`, `/memory` sans session | **401** |
| `GET /status`, `/missions`, `/tools` avec session | **200** |
| `POST /tool` avec `Origin: http://site-malveillant.example` | **403** « Origine non autorisee. » |
| `POST /tool` avec `Content-Type: text/plain` | **415** |
| `POST /mission` | **200**, la mission démarre en arrière-plan et atteint `awaiting_authorization` |
| `POST /mission/<id>/authorize` | **200** mais **la mission redemande une autorisation** (défaut **D1**) |

---

## 4. Défauts constatés (corrections proposées, **non appliquées**)

### D1 — Élevé : l'autorisation d'une mission ne converge pas depuis l'interface web

**Symptôme** : après `POST /mission/<id>/authorize` (200), la mission passe de
`awaiting_authorization` à `awaiting_authorization` (nouvel échange), et ainsi de
suite jusqu'à l'épuisement du budget d'échanges
(`interaction_budget_exceeded`). La mission web ne peut donc pas aboutir.

**Cause** (`app/orchestration/runner.py`) : le registre d'autorisations est
interrogé avec **la session du runner** (`self.session_id`, celle de
l'application) au lieu de la session du client :

- `runner.py:856-857` — la vérification :
  `self.grant_registry.authorize(step.tool_id, parameters, mission.mission_id, self.session_id)`
- `runner.py:442` — l'émission du grant :
  `session_id=requester_session_id or mission.session_id` (session du client)

Les deux sessions diffèrent pour le web (le runner a une session par
application, le web une session par client) ; en CLI, elles coïncident — d'où
un défaut **invisible en ligne de commande**.

**Preuve** (grant artificially issued for the client session) :

```
avec la session du CLIENT  : 3e62423fc5514d55b118777707b8dcb0   (accepté)
avec la session du RUNNER  : None                                 (refusé)
```

**Correctif proposé** (une ligne, uniquement dans le runner) :

```python
grant_id = self.grant_registry.authorize(
    step.tool_id, parameters, mission.mission_id,
    mission.session_id or self.session_id,   # <- session du client propriétaire
)
```

**Non appliqué** : la mission interdit de modifier le code sans autorisation
explicite. **Impact** : la mission web est inutilisable en l'état ; la
validation utilisateur de la Phase 6 (autonomie) ne peut pas être faite via
l'interface web avant correction.

### D2 — Moyen : la lettre de lecteur Windows est perdue dans l'objectif

**Symptôme** : `extract_target_path("Analyse C:/Windows")` → `"/Windows"` (au
lieu de `C:/Windows`) ; idem `"C:\Windows\System32"` → `"\Windows\System32"`.

**Impact** : une mission portant un chemin Windows absolu analyse le mauvais
répertoire ; le message d'erreur affiche un chemin trompeur.

**Cause** (`app/orchestration/planner.py`) : la classe de caractères du motif de
chemin n'inclut pas `:`.

**Correctif proposé** : inclure `:` dans la classe de caractères (et un test
couvrant `C:/...` et `C:\...`).

### D3 — Moyen : des chemins légitimes sont refusés par la politique de sécurité

**Symptôme** : toute valeur de paramètre contenant `code`, `source`, `script`,
`python` ou `javascript` est refusée. Sont donc refusés, à titre d'exemple :
`C:\dev\source\z`, `C:\dev\decode\y`, `C:\Users\X\Documents\code\x`.

**Impact** : une mission ne peut pas analyser un projet situé sous un tel
chemin — c'est le cas de la présente campagne de validation (le répertoire
d'isolation contenait « opencode » : la mission a été refusée avec « Action
refusée par la politique de sécurité »).

**Cause** (`app/tools/policy.py`, `validate_no_code_execution`) : le contrôle
par sous-chaîne est appliqué aux **valeurs**, y compris aux chemins. Le
contrôle sur les **clés** (`code`, `script`, …) est, lui, pertinent.

**Correctif proposé** : ne pas appliquer ce contrôle par sous-chaîne aux
valeurs qui sont des chemins (le contrôle par clé est conservé, ainsi que le
contrôle sur les valeurs non-chemin). **À valider explicitement : c'est du
code de sécurité**, la mission en interdit la modification dans ce cadre.

### D4 — Mineure : démarrage d'une mission retardé par le fournisseur

**Symptôme** : avec le fournisseur par défaut (`http://localhost:8000`, service
qui écoute mais ne répond pas), une mission attend le délai du fournisseur
(jusqu'à 30 s) avant de basculer sur le plan déterministe ; l'interface paraît
figée. Mesuré : session CLI complète en 20,8 s (délai par défaut) contre
14,0 s avec `MILES_REMOTE_TIMEOUT=2`.

**Cause** : le planificateur interroge le fournisseur avant le repli
déterministe ; l'analyse qualitative du rapport fait un second appel.

**Contournement documenté** : `MILES_REMOTE_TIMEOUT=1` (voir le guide), ou
fournisseur non joignable (échec immédiat).

---

## 5. Réserve sur le plafond d'étapes

Le plafond global d'étapes (12) **est appliqué par le code** et couvert par
`tests/test_mission_bounds.py::test_plafond_d_etapes_global`. Il n'est
**pas observable depuis le terminal** avec le planificateur déterministe, car
ce dernier dimensionne le plan au budget disponible
(`max_steps − 2` lectures) : la mission s'arrête proprement en `completed`
sans jamais atteindre le plafond. Le plafond redevient observable avec un
plan proposé par le fournisseur IA (ou via le test unitaire).

---

## 6. Ce qui n'a pas été testé, et pourquoi

| Élément | Motif |
|---------|-------|
| Conversation IA (message → réponse) | appel API payant ; non exécuté. Le repli propre « aucun fournisseur IA configuré » a été vérifié |
| Plan proposé par le fournisseur IA | idem ; le repli déterministe a été vérifié (« Repli : échec de l'appel au fournisseur IA ») |
| Analyse qualitative du rapport | idem ; le rapport indique explicitement « non produite » |
| Plateforme Debian 13 | indisponible depuis ce poste ; les tests ignorés sous Windows y sont exécutés (constat d'Agent B) |
| Matériel (GPU, capteurs) | hors périmètre de cette mission |
| Lecture de fichiers volumineux | hors périmètre |

---

## 7. État Git final

| Élément | Valeur |
|---------|--------|
| Branche de travail | `fix/miles-mission-bounds` (poussée : `origin/fix/miles-mission-bounds` = `3d0bfb8`) |
| Commits produits par cette mission | **aucun commit de code** ; un commit documentaire (ce rapport + le guide développeur) |
| `main` | `b9b7e7d` — **inchangée** |
| Branche auditée par Agent B | `69bf670` — **inchangée** |
| Artefact non suivi | `tatus --short --branch` — **préservé** |
| Fichiers du dépôt modifiés | `docs/reports/PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md` (nouveau), `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` (nouveau) |

---

## 8. Procédure de vérification indépendante

```bash
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-mission-bounds
git pull --ff-only
python -m unittest discover -s tests

# Session CLI isolée (aucune clé API, bases de test séparées)
$env:MILES_REMOTE_TIMEOUT = "1"
$env:MILES_MISSION_DB_PATH = "data/validation-missions.db"
@("/mission Analyse le dossier docs/","o","/quit") | python miles.py

# Plafonds
$env:MILES_MISSION_MAX_TOOL_CALLS = "1"
@("/mission Analyse le dossier docs/","o","/quit") | python miles.py

# Interface web
$env:MILES_WEB_AUTH_TOKEN = "jeton-de-validation"
python miles.py --web --web-port 8123
```

Le guide pas-à-pas destiné au développeur est
`docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md`.

---

## 9. Prochaine action recommandée

1. **Autoriser la correction de D1** (une ligne, runner uniquement) : sans
   elle, la mission web ne fonctionne pas et l'autonomie de la Phase 6 n'est
   pas validable depuis l'interface web.
2. **Autoriser D2 et D3** séparément : D2 est une correction fonctionnelle
   mineure ; D3 touche au code de sécurité et demande une revalidation
   explicite.
3. **Faire réauditer** le SHA de correction par Agent B, puis Integrating.
4. Rejouer la présente procédure une fois D1 corrigé : la section 5.2 du guide
   (mission web) doit alors aboutir à l'état `completed`.
