# docs/reports/PHASE_6_2_MISSION_BOUNDS_AGENT_A.md — Limites globales d'exécution des missions MILES

- **Auteur** : Agent A
- **Date** : 2026-10-20
- **Dépôt** : `C:\Users\StanC\Desktop\Milescorp` (remote `https://github.com/Miles-corp/Milescorp.git`)
- **Branche de travail** : `fix/miles-mission-bounds`
- **Base** : `69bf670` (`integration/miles-phases-5-6-6-1`, code `263b604`) — branche **d'audit d'Agent B, non modifiée**
- **`main`** : `b9b7e7d` — **inchangée**
- **Tâche** : TASK-DEV-017

---

## 1. Diagnostic initial des trois points P2

### 1.1 P2-6-07 — les bornes étaient par boucle, pas par mission : **CONFIRMÉ**

Dans `app/orchestration/runner.py`, `_execute_loop` (avant correction) calculait
ses propres compteurs à chaque entrée de boucle :

```python
deadline = self._clock() + limits.max_duration_seconds   # recalculé à chaque boucle
executed = 0                                             # remis à zéro à chaque boucle
identical = 0                                            # remis à zéro à chaque boucle
last_signature = ""                                      # remis à zéro à chaque boucle
```

Or la boucle est rejouée par plusieurs chemins publics :

| Chemin | Appel | Effet sur le budget |
|--------|-------|----------------------|
| `run()` | `_execute_loop()` | nouvelle boucle → compteurs à zéro |
| `answer()` (clarification) | `self.run(mission_id)` (L334) | **nouvelle boucle → budget à zéro** |
| `answer()` (autorisation) | `self.authorize(...)` → `self.run(...)` (L424) | **nouvelle boucle → budget à zéro** |
| `resume()` | `self.run(mission_id)` (L440, L455) | **nouvelle boucle → budget à zéro** |
| replanification | `mission.plan = None` puis `run()` | nouvelle boucle + **nouvelles étapes** (compteur d'étapes à zéro) |

**Conséquence mesurée dans le code** : une mission qui alterne clarification
et autorisation pouvait exécuter un nombre illimité d'étapes et une durée
totale illimitée, alors que chaque boucle isolée respectait 12 étapes /
120 s. Le plafond d'étapes était également remis à zéro par une
replanification (nouvelles étapes).

### 1.2 P2-6-08 — le plafond d'échanges n'existait que dans le CLI : **CONFIRMÉ**

| Emplacement | Borne |
|-------------|-------|
| `app/interface/cli.py` (`_drive_mission`) | `max_interactions = 5` — **constante locale de l'interface** |
| `app/orchestration/runner.py` | **aucune** |
| `app/interface/web.py` (`answer_mission`, `authorize_mission`) | **aucune** → une alternance illimitée était possible par HTTP |

### 1.3 P2-6-05 — aucun plafond global d'appels d'outils : **CONFIRMÉ**

- Une étape = un appel d'outil ; une **reprise** d'étape transitoire = un
  nouvel appel (plafonnée par étape, `max_attempts_per_step`, mais le compteur
  est porté par l'étape : une replanification crée de nouvelles étapes, donc
  de nouveaux compteurs).
- Le jeton de confirmation est renvoyé à l'appelant
  (`app/tools/service.py` : `describe_result` → `payload["confirmation_token"]`),
  ce qui reste un risque **latent** tant que les outils ne sont pas exposés
  au modèle. Le budget global d'appels d'outils est ici la garde
  complémentaire demandée par la mission.

### 1.4 Contrôle de l'annulation, des erreurs et du nettoyage : **conforme**

- Annulation : `self._cancelled` est vérifié en tête de boucle, `cancel()`
  passe la mission à l'état `CANCELLED` — mais **sans motif d'arrêt
  explicite** (le rapport ne disait pas pourquoi la mission s'était arrêtée).
- Erreurs : les échecs d'étape sont collectés (`mission.errors`), les étapes
  dépendantes sont marquées sautées.
- Nettoyage des ressources : inchangé (les files multiprocessing sont fermées
  dans un `finally` par le moteur, invariant S-006).

**Conclusion : une correction était nécessaire.**

---

## 2. Changements réalisés, fichier par fichier

### 2.1 `app/orchestration/models.py`

| Changement | Détail |
|------------|--------|
| `MissionBudget` (nouveau) | Budget porté par la mission : `executed_seconds`, `steps_executed`, `tool_calls`, `interactions`, `last_signature`, `identical_results`, `stop_reason`, `stop_detail`. Sérialisation `to_dict` / `from_dict`. |
| `StopReason` (nouveau) | 12 motifs d'arrêt stables : `not_started`, `completed`, `partial`, `failed`, `cancelled`, `time_budget_exceeded`, `step_budget_exceeded`, `tool_call_budget_exceeded`, `interaction_budget_exceeded`, `repeated_results`, `authorization_required`, `clarification_required`. |
| `Mission.budget` | Champ ajouté, sérialisé et rechargé. |
| `ExecutionLimits` | Ajout de `max_tool_calls` (24) et `max_interactions` (5). Les valeurs existantes (12 étapes, 2 tentatives, 120 s) sont **inchangées**. |

### 2.2 `app/orchestration/runner.py`

| Changement | Détail |
|------------|--------|
| `_execute_loop` | Les compteurs locaux (`deadline`, `executed`, `identical`, `last_signature`) sont **supprimés** : tout est lu dans `mission.budget`. Le temps d'exécution cumulé est mesuré par boucle (`base_seconds + (now - loop_start)`) et imputé au budget global, y compris en sortie anormale (`finally`). Le temps d'**attente humaine** n'est pas consommé (comportement inchangé). |
| Plafonds appliqués **avant** chaque étape | durée cumulée, nombre d'étapes, nombre d'appels d'outils. Chaque dépassement arrête la mission avec `LIMIT_REACHED` et un motif explicite. |
| `_request_authorization` (nouveau) | Point unique de création d'une demande d'autorisation : vérifie le plafond d'interactions, débite le compteur, renseigne le motif d'arrêt. Utilisé par le pré-contrôle (`_ensure_authorization`) **et** par la branche `BLOCKED` de la boucle. |
| `_ensure_authorization` | Ne lève plus la demande lui-même : délègue à `_request_authorization` (budget global) et **ne déclare jamais** l'étape exécutable si une demande est en attente. |
| `_build_plan` | La clarification est débitée du budget d'interactions ; si le plafond est atteint, aucune nouvelle question n'est posée et la mission s'arrête. |
| `answer()` | Vérifie le budget d'interactions ; la relance d'une clarification (réponse non comprise) est débitée ; au plafond, la mission s'arrête au lieu de reposer une question. |
| `authorize()` | Motif d'arrêt `failed` propagé ; le grant émis reste lié à la session du demandeur (inchangé). |
| `resume()` | **Ne réinitialise pas** le budget : une mission qui a consommé son budget s'arrête immédiatement. |
| `cancel()` | Motif d'arrêt `cancelled` + événement de journalisation. |

### 2.3 `app/orchestration/store.py`

| Changement | Détail |
|------------|--------|
| Schéma v2 | Nouvelle colonne `budget_json` ; **migration additive** (`PRAGMA table_info` + `ALTER TABLE`) pour les bases existantes, sans perte de données. |
| `save()` / `load()` | Le budget est écrit et relu ; une mission rechargée conserve son budget. |

### 2.4 `app/orchestration/report.py`

Le compte rendu indique désormais le **budget consommé** et le **motif d'arrêt**.

### 2.5 `app/interface/web.py`

La charge utile d'une mission expose `budget` (temps, étapes, appels d'outils,
échanges, motif, détail) → l'appelant sait toujours pourquoi la mission s'est
arrêtée.

### 2.6 `app/interface/cli.py`

La borne d'échanges du terminal n'est plus une constante locale (5) mais
provient de l'orchestrateur (`limits.max_interactions`) : **source unique de
vérité**, identique au web.

### 2.7 `app/config/settings.py` + `miles.py` + `docs/installation/INSTALL.md`

| Élément | Valeur | Justification |
|---------|--------|---------------|
| `MILES_MISSION_MAX_TOOL_CALLS` | 24 | `max_steps` (12) × `max_attempts_per_step` (2) : cohérent avec les bornes déjà fixées, **non arbitraire** |
| `MILES_MISSION_MAX_INTERACTIONS` | 5 | valeur **déjà appliquée** par l'interface en ligne de commande, désormais appliquée par l'orchestrateur (donc aussi par le web) |

Les deux variables sont documentées dans INSTALL.md (section 3quater et table
récapitulative) ; le test anti-dérive `test_docs_configuration` a été mis à
jour (30 variables reconnues, 28 dans `env_mapping`).

---

## 3. Limites globales garanties

| Limite | Avant | Après | Portée |
|--------|-------|-------|--------|
| Durée d'exécution | 120 s **par boucle** | **120 s cumulés par mission** (temps d'attente humaine exclu) | mission |
| Étapes | 12 **par boucle** (remises à zéro par replanification) | **12 cumulées par mission** | mission |
| Appels d'outils | aucun plafond global (2 tentatives par étape, compteur par étape) | **24 cumulés par mission** | mission |
| Échanges utilisateur | 5 **uniquement dans le CLI** ; aucun dans le web | **5 cumulés par mission**, appliqués par l'orchestrateur (CLI **et** web) | mission |
| Tentatives par étape | 2 par étape | 2 par étape (**inchangé**) | étape |
| Détection de boucle | 2 résultats identiques **par boucle** | 2 résultats identiques **par mission** (global) | mission |
| Motif d'arrêt | aucun (état + erreurs déduits) | `StopReason` explicite, propagé au rapport et à l'API web | mission |

**Le budget n'est réinitialisé par aucun chemin** : nouvelle boucle,
replanification, réponse de l'utilisateur, reprise explicite, rechargement
depuis la base.

---

## 4. Tests exécutés et résultats exacts

### 4.1 Nouveau fichier `tests/test_mission_bounds.py` (20 tests)

Horloge **injectée** (aucun `sleep` → tests déterministes) ; le détecteur de
boucle est explicitement isolé (`max_identical_results=99`) pour que chaque
test ne mesure qu'un mécanisme.

| # | Cas exigé | Test(s) |
|---|-----------|---------|
| 1 | mission normale qui se termine correctement | `test_mission_normale_terminee`, `test_le_compte_rendu_porte_le_budget_et_le_motif` |
| 2 | dépassement du budget global de temps | `test_le_temps_consomme_dans_la_boucle_est_compte`, `test_le_budget_de_temps_arrete_la_mission` |
| 3 | dépassement du nombre global d'étapes | `test_plafond_d_etapes_global` |
| 4 | dépassement du nombre global d'appels d'outils | `test_plafond_d_appels_d_outils_global` |
| 5 | boucles répétées ne réinitialisent pas les compteurs | `test_les_boucles_ne_reinitialisent_pas_le_plafond_d_etapes`, `test_une_reponse_ne_reinitialise_pas_le_budget`, `test_le_budget_de_temps_est_cumule_entre_les_boucles` |
| 6 | arrêt propagé aux sous-tâches et aux outils | `test_le_premier_echangement_compte`, `test_le_plafond_d_interactions_arrete_la_mission` (mission arrêtée **sans** que l'étape ne soit exécutée), `test_une_autorisation_refusee_arrete_la_mission` |
| 7 | erreurs, annulation et limites existantes | `test_annulation_propage_le_motif`, `test_une_etape_en_echec_est_signalee`, `test_le_compte_rendu_signale_le_motif_d_arret`, `test_la_borne_par_etape_est_preservee` |
| 8 | persistance et reprise | `test_le_budget_est_recharge_depuis_la_base`, `test_une_mission_rechargee_conserve_son_budget` |
| 9 | compatibilité des valeurs | `test_les_valeurs_par_defaut_sont_coherentes`, `test_les_reglages_sont_exposes` |

### 4.2 Résultats d'exécution

| Exécution | Commande | Résultat |
|-----------|----------|----------|
| Tests de bornes | `python -m unittest tests.test_mission_bounds` | **20 OK, 0 échec** |
| Orchestrateur (Phase 6) | `python -m unittest tests.test_mission_orchestrator` | 73 OK, 0 échec |
| Suite complète | `python -m unittest discover -s tests` | **528 tests OK, 0 échec, 4 ignorés** (95,9 s) |
| Tests d'audit d'Agent B (tels quels, depuis `origin/audit/agent-b-phase6-1-web-security-review`) | `python -m unittest tests.test_audit_phase6_agent_b tests.test_audit_phase6_v2_agent_b tests.test_audit_phase6_1_agent_b` | **70 tests OK, 0 échec, 2 ignorés** |
| Compilation | `python -m compileall app miles.py` | **OK** |

Les 4 + 2 tests ignorés sont des **limites de plateforme Windows**
(3 liens symboliques, 1 `/proc/self/fd`, 2 liens symboliques d'audit) : ils
s'exécutent sous Debian 13 et ne sont **pas** comptés comme réussis sur la
plateforme qui les ignore.

> Note de lecture : un premier jet de mes tests déclarait les handlers
> d'échec comme des **fonctions locales**. Le moteur exécute les handlers
> dans un sous-processus (`spawn`) : une fonction locale n'est pas
> désérialisable, l'enfant ne démarrait pas et le test passait **pour une
> mauvaise raison**. Les handlers sont désormais au niveau du module, et le
> test vérifie réellement l'échec de l'outil.

---

## 5. Risques résiduels et tests manquants

| Risque / limite | Statut |
|------------------|--------|
| La durée mesure le **temps d'exécution**, pas le temps d'horloge murale : une mission laissée en attente d'un humain ne consomme pas de budget, mais une mission qui dort *entre deux boucles* ne serait pas non plus bornée en temps d'horloge murale. Choix assumé et documenté (cohérent avec le comportement d'origine) ; un plafond d'horloge murale reste possible si ce semantics est jugé insuffisant. |
| Le budget n'est pas partagé entre **deux missions** : chaque mission a son propre budget (choix : une mission = une unité de travail bornée). |
| `max_tool_calls` (24) est déduit de `max_steps × max_attempts` ; un budget d'appels distinct du nombre d'étapes n'est pas nécessaire aujourd'hui, mais le paramètre existe pour le contraindre indépendamment. |
| Le **plafond d'échanges** (5) est désormais appliqué au web, mais le web n'a toujours pas de limitation de débit HTTP : un client authentifié peut enchaîner des missions **en parallèle**, chacune avec son propre budget. Limite d'un agent authentifié, non corrigée ici. |
| **P2-6-05** (jeton de confirmation renvoyé à l'appelant) n'est pas levé : il est atténué par le budget global d'appels d'outils et par le fait que les outils ne sont pas exposés au modèle. La correction de fond (ne pas renvoyer le jeton, mais un jeton de décision non rejouable) reste à faire. |
| **P2-6-09 / P2-6-10** (résultats non persistés, étape restée `RUNNING` non reprise) : non traités, hors périmètre demandé. |
| **P3-6-12** (interface web non lançable par `miles.py`) : non traité, hors périmètre demandé. |
| Aucune validation **Debian 13** n'a été faite pour ce changement (environnement indisponible) : à rejouer par Agent B. |
| Tests manquants acceptés : pas de test multi-processus (deux missions en parallèle), pas de test de charge (le budget est-il bien respecté sous charge ?). |

---

## 6. Branche et SHA exacts

| Élément | Valeur |
|---------|--------|
| Branche de travail | `fix/miles-mission-bounds` |
| Base | `69bf670` (`integration/miles-phases-5-6-6-1`) |
| SHA **à auditer** | voir §8 (commit de tête de la branche) |
| Branche d'intégration auditée | `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **non modifiée** |
| `main` | `b9b7e7d` — **non modifiée** |
| Fichier non suivi | `tatus --short --branch` — **préservé, non committé** |

---

## 7. Vérification finale

| Contrôle | Résultat |
|----------|----------|
| Diff complet | 10 fichiers modifiés + 1 fichier créé, **tous dans MILES** (`app/orchestration/*`, `app/interface/{cli,web}.py`, `app/config/settings.py`, `miles.py`, `docs/installation/INSTALL.md`, `docs/coordination/*`, `tests/*`) |
| Aucun fichier hors périmètre MILES modifié | **confirmé** (`git status` : uniquement des chemins MILES) |
| Branche d'intégration auditée par Agent B | **inchangée** (`69bf670`) |
| `main` | **inchangée** (`b9b7e7d`) |
| Artefact non suivi | **préservé** |
| Force-push / reset --hard / clean -fd / suppression de branche | **aucun** |

---

## 8. Procédure de vérification indépendante

```bash
# 1. Récupérer la branche
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-mission-bounds
git pull --ff-only

# 2. Tests de bornes (déterministes, horloge injectée)
python -m unittest tests.test_mission_bounds -v

# 3. Suite complète
python -m unittest discover -s tests

# 4. Tests d'audit d'Agent B (tels quels)
git show origin/audit/agent-b-phase6-1-web-security-review:tests/test_audit_phase6_agent_b.py > tests/test_audit_phase6_agent_b.py
git show origin/audit/agent-b-phase6-1-web-security-review:tests/test_audit_phase6_v2_agent_b.py > tests/test_audit_phase6_v2_agent_b.py
git show origin/audit/agent-b-phase6-1-web-security-review:tests/test_audit_phase6_1_agent_b.py > tests/test_audit_phase6_1_agent_b.py
python -m unittest tests.test_audit_phase6_agent_b tests.test_audit_phase6_v2_agent_b tests.test_audit_phase6_1_agent_b
rm tests/test_audit_phase6_agent_b.py tests/test_audit_phase6_v2_agent_b.py tests/test_audit_phase6_1_agent_b.py

# 5. Vérifier l'indépendance du budget (contrôle manuel)
#    - une mission qui boucle ne doit jamais dépasser 12 étapes,
#      24 appels d'outils, 5 échanges et 120 s d'exécution cumulés,
#    - le rapport doit porter un motif d'arrêt explicite.
```

**Aucun appel API payant, aucun téléchargement, aucune dépendance ajoutée.**
