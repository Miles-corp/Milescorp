# docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_A.md — Orchestrateur de missions MILES (Agent A)

- **Auteur** : Agent A
- **Date** : 2026-10-20
- **Branche** : `feature/miles-mission-orchestrator`
- **Base de départ** : `a11ab4a` (Phase 5 — `feature/miles-tool-engine-integration`, elle-même based on `bccdc1c` = branche V1)
- **Tâche** : TASK-DEV-014
- **Environnement de validation** : Windows, Python 3.12.10

---

## 1. Résumé exécutif

MILES reçoit désormais un **objectif en langage naturel**, prépare un **plan
explicite**, exécute **plusieurs étapes** avec les outils autorisés, **observe**
les résultats réels, **ajuste** le plan en cas d'échec, **s'arrête** quand une
autorisation manque et produit un **compte rendu** qui distingue les faits
observés, les erreurs et les étapes non terminées.

Livré :

- un package `app/orchestration/` (mission, plan, planificateurs, exécuteur,
  observateur, coordinateur, persistance, compte rendu) ;
- un **correctif du défaut de sécurité** signalé par la Phase 5 : les
  confirmations et les autorisations sont désormais liées à une **session** et à
  une **mission**, expirent, sont bornées en usages et ne sont pas rejouables ;
- une **extension de lecture strictement encadrée** (`action_read_file`) et un
  listing borné en profondeur, sans nouvelle permission ;
- une **mission pilote d'analyse en lecture seule** ;
- l'intégration **CLI** (6 commandes) et **web** (6 routes) ;
- **73 nouveaux tests** couvrant les 20 catégories exigées ;
- **451 tests OK** au total sur Windows (378 antérieurs + 73), 0 échec,
  4 ignorés (limites plateforme Windows).

Aucun appel API payant, aucun téléchargement, aucune nouvelle dépendance, aucun
fichier du dépôt modifié par la mission pilote.

---

## 2. Synchronisation préalable

| Contrôle | Résultat |
|----------|----------|
| Dépôt distant | `https://github.com/Miles-corp/Milescorp.git` (correct) |
| `git fetch origin --prune` | `main` = `b9b7e7d`, V1 = `bccdc1c`, Phase 5 = `a11ab4a` |
| Phase 5 présente | `a11ab4a` vérifié, locale = distante, **0 divergence** |
| Phase 5 dans `main` ? | **NON** — `git merge-base --is-ancestor a11ab4a origin/main` échoue |
| Base choisie | `a11ab4a` (la Phase 5 n'est pas fusionnée : partir de `main` aurait privé la mission du moteur d'outils) |
| Artefact local | `tatus --short --branch` **préservé**, hors commit |

`main` n'a pas été modifiée et n'est pas Fusionnée.

---

## 3. Architecture livrée

```
   CLI : /mission, /missions, /mission-status, /mission-answer,
         /mission-cancel, /mission-resume
   Web : POST /mission, GET /missions, GET /mission/<id>,
         POST /mission/<id>/{authorize,answer,cancel}
                    \                              /
                     \        MissionRunner          /
                      \  (planifier → exécuter →   /
                       \   observer → ajuster →     /
                        \  terminer)                 /
                         \__________________________/
                                      |
                              ToolService (Phase 5)
                                      |
                         ToolEngine → ToolRegistry / ToolPolicy
                                      |
                              GrantRegistry (session + mission)
```

| Module | Rôle |
|--------|------|
| `app/orchestration/models.py` | `Mission`, `Plan`, `PlanStep`, `SourceRef`, `PendingRequest`, `ExecutionLimits`, états et statuts |
| `app/orchestration/planner.py` | `DeterministicPlanner` (sans IA) et `ProviderPlanner` (IA, sortie validée), `validate_plan_payload` |
| `app/orchestration/executor.py` | `Executor` : exécute une étape via `ToolService`, résout les dépendances, ne fabrique jamais de confirmation |
| `app/orchestration/observer.py` | `Observer` : transforme un résultat en faits, calcule une signature pour détecter les boucles |
| `app/orchestration/runner.py` | `MissionRunner` : cycle complet, bornes, annulation, autorisations, reprise |
| `app/orchestration/store.py` | `MissionStore` : persistance SQLite (`data/missions.db`), dégradation gracieuse |
| `app/orchestration/report.py` | `ReportBuilder` : compte rendu structuré (faits / erreurs / étapes non terminées) |
| `app/tools/grants.py` | `ToolGrant`, `GrantRegistry` : autorisations liées à la session et à la mission |

Le moteur d'outils **n'est pas réimplémenté** : toute exécution passe par
`ToolService` → `ToolEngine` → `ToolPolicy`. L'orchestrateur ne fait qu'
ordonner, contraindre et observer.

---

## 4. Correction du défaut de sécurité de la Phase 5

Le rapport de la Phase 5 signalait : « le jeton de confirmation n'est pas lié à
l'identité de l'utilisateur ». Le défaut a été **vérifié dans le code** puis
**corrigé** dans le périmètre nécessaire.

### 4.1 Avant

- Le jeton de confirmation n'était lié qu'à l'outil et à l'empreinte des
  paramètres.
- Il ne portait ni session, ni mission, ni expiration par usage.
- Une action sensible pouvait donc être confirmée dans un contexte différent de
  celui qui l'avait demandée.

### 4.2 Après

| Contrôle | Comportement |
|----------|--------------|
| Jeton lié au contexte | `_PendingConfirmation` porte `context_id` (mission) et `actor_id` (session) ; un jeton émis ailleurs est **refusé** (échec fermé) |
| Usage unique | Le jeton est consommé à la confirmation ; un rejeu est refusé |
| Expiration | TTL inchangé (300 s), vérifié avant usage |
| Autorisation de mission | `ToolGrant` : émis par l'application, lié à session **et** mission, liste explicite d'outils, racines de chemin optionnelles, expiration, nombre d'usages borné, révocable |
| Le modèle ne peut pas forger un grant | Le grant est un paramètre **interne** du moteur, injecté par l'application ; il n'est jamais un paramètre d'appel d'outil |
| Un grant ne contourne pas la politique | Il remplace seulement la confirmation interactive ; permissions, politique, types de paramètres et délais restent vérifiés par `ToolEngine` |

Tests associés : `test_jeton_de_confirmation_rejoue_refuse`,
`test_jeton_de_confirmation_refuse_dans_une_autre_session`,
`test_jeton_de_confirmation_expire_refuse`, `test_grant_lie_a_la_session_et_a_la_mission`,
`test_grant_expire`, `test_grant_borne_en_usages`, `test_grant_reste_revoable`.

---

## 5. Extension de lecture strictement encadrée

Les outils de la Phase 5 permettaient de **lister** un dossier mais pas d'en
**lire** le contenu : la mission pilote n'aurait pas pu examiner les fichiers.

| Outil | Risque | Permission | Comportement |
|-------|--------|------------|--------------|
| `action_read_file` | MEDIUM | `lecture_systeme` (existante, aucune nouvelle) | Lecture d'un fichier texte, bornée à 64 Kio (20 Kio par défaut) |

Garde-fous :

- **confinement** canonique des chemins (racines autorisées : projet, `data/`) ;
- **fichiers sensibles refusés** (`.env`, `.env.*`, clés privées `.pem`/`.key`,
  `.netrc`, `.npmrc`, `credentials`, `id_rsa*`…) ;
- **taille bornée** : au-delà, le fichier n'est pas lu et le fait est explicite
  (« Fichier non lu : taille … supérieure à la limite ») ;
- **contenu expurgé** des motifs de secrets avant retour (`app.utilities.redaction`).

`action_list_files` a été enrichi d'un paramètre `depth` (1 à 3, borné) et
d'un plafond de 500 entrées ; la descente dans un sous-dossier n'a lieu que si
sa résolution canonique reste dans les racines autorisées (le confinement
s'applique donc aussi en profondeur).

**Changement de contrat assumé** : `action_list_files` retourne désormais un
dictionnaire structuré (`path`, `depth`, `entries`, `count`, `truncated`) au
lieu d'une chaîne. Les entrées portent `name`, `path`, `is_dir`, `size`,
`is_text`, `sensitive` : l'orchestrateur exploite des données, il ne devine
pas. Les tests de la Phase 5 concernés ont été adaptés (contrat documenté).

---

## 6. Boucle d'exécution contrôlée

Toutes les bornes sont **appliquées par le code** (configurables :
`MILES_MISSION_MAX_STEPS`, `MILES_MISSION_MAX_ATTEMPTS`,
`MILES_MISSION_MAX_DURATION_SECONDS`).

| Borne | Valeur par défaut | Comportement |
|-------|-------------------|--------------|
| Étapes par mission | 12 | Au-delà : état `limit_reached`, mission arrêtée |
| Tentatives par étape | 2 | Reprise **limitée**, et uniquement si l'échec est *transitoire* |
| Durée de mission | 120 s | Au-delà : état `limit_reached` |
| Résultats identiques consécutifs | 2 | Détection de boucle : mission arrêtée |
| Échanges avec l'utilisateur | 5 | Bornage des boucles de questions (CLI) |

Classification des échecs (reprise autorisée **uniquement** pour les échecs
techniques) :

| Catégorie | Reprise | Exemple |
|-----------|---------|---------|
| `transient` | oui (bornée) | « Erreur d'exécution. », « Délai d'attente dépassé » |
| `permission` | non | « Permissions manquantes : … » |
| `policy` | non | « Action refusée par la politique de sécurité. » |
| `unknown_tool` | non | « Outil inconnu : … » |
| `authorization` | — | la mission passe en attente d'autorisation |
| `fatal` | non | tout le reste |

Une étape en échec **cascade** : les étapes qui en dépendent sont marquées
« sautées » et ne sont pas exécutées.

---

## 7. Fournisseur IA et fonctionnement dégradé

- Le planificateur IA interroge le fournisseur configuré via l'interface
  existante `AIProvider` (`app/ai_providers/base.py`) : **aucune dépendance
  ajoutée, aucun fournisseur codé en dur**.
- La réponse est **validée avant toute exécution** : objet JSON, liste
  `steps` non vide, outil enregistré **et** autorisé par la mission,
  paramètres déclarés et correctement typés, pas de commande, nombre
  d'étapes borné.
- En cas de fournisseur absent, indisponible, instable, de réponse non JSON ou
  de plan refusé : **repli sur le plan déterministe**, et la mission conserve
  la trace factuelle (`planner = "deterministe+repli"`, `planner_note`).
- **Aucune décision IA n'est simulée** : en l'absence de fournisseur, le
  compte rendu indique explicitement « Analyse qualitative non produite ».
- L'analyse qualitative facultative (fournisseur disponible) est **étiquetée
  « non vérifiée »** et n'est jamais présentée comme un fait observé.

---

## 8. Mission pilote : analyse en lecture seule

Objectif de démonstration :

> « Analyse ce dossier de projet, identifie son organisation, examine les
> fichiers pertinents et indique les améliorations possibles sans modifier
> aucun fichier. »

Déroulé réel (exécution manuelle, terminal) :

```
Autoriser l'accès en lecture dans C:\...\Milescorp\docs pour les outils :
action_list_files, action_read_file ?

Mission cff1e2702630 — état : completed
== Faits observés ==
- Résultat de l'étape s1 : 32 caractère(s).
- Analyse de C:\...\docs (profondeur 2) : 45 entrée(s) : 6 répertoire(s), 39 fichier(s).
- Fichiers observés : .gitkeep, DECISIONS.md, HANDOFF.md, MESSAGES.md,
  REPORT_TEMPLATE.md, STATUS.md, TASKS.md, WORKFLOW.md, .gitkeep, INSTALL.md,
  QUICKSTART.md, AUDIT-TASK-DEV-003.md …
- 4 fichier(s) non lus (binaire, hors texte ou sensible).
- Contenu lu : 5610 caractère(s), 69 ligne(s).
- Contenu lu : 2433 caractère(s), 53 ligne(s).
- Contenu lu : 2313 caractère(s), 24 ligne(s).
== Erreurs ==
- Aucune erreur.
== Étapes non terminées ==
- Aucune : toutes les étapes prévues sont terminées.
```

Le même scénario **dans les tests** (`test_mission_pilote_ne_modifie_aucun_fichier`) :

1. `runner.create("Analyse le dossier docs/ …")` ;
2. `runner.run(...)` → état `awaiting_authorization` (les outils MEDIUM
   exigent une autorisation humaine) ;
3. `runner.authorize(mission_id, approved=True)` → émission du grant lié à la
   session et à la mission ;
4. exécution du plan (5 étapes), puis état `completed` ;
5. **vérification** : les tailles de modification de tous les fichiers de
   `docs/` sont identiques avant/après, et aucun fichier n'a été créé.

Comportement face à une ambiguïté : « Analyse l'organisation du code » (aucun
dossier nommé) → état `needs_clarification`, question posée à l'utilisateur ;
la réponse `docs/` relance la planification.

---

## 9. Persistance et reprise

- Base SQLite locale `data/missions.db` (`MissionStore`), chemin confiné aux
  racines autorisées, dégradation gracieuse si la base est indisponible
  (la mission continue en mémoire seule).
- Contenu persisté : identifiant, objectif, état, plan et étapes (statut,
  tentatives, résultat, erreur), faits, erreurs, étapes non terminées,
  demande en attente, horodatages, note du planificateur.
- Tout contenu écrit est **expurgé des motifs de secrets**.
- **Reprise** (`/mission-resume <id>`) :
  - les étapes **succédées** ne sont pas rejouées ;
  - une étape en échec est marquée `uncertain` et **n'est pas rejouée
    automatiquement** (son résultat est incertain) ;
  - les **autorisations sont revalidées** : un grant expiré, révoqué ou émis
    pour une autre session est refusé, la mission repasse en attente
    d'autorisation (test `test_reprise_revalide_l_autorisation`).

---

## 10. Intégration aux interfaces

### 10.1 CLI (6 commandes)

| Commande | Effet |
|----------|-------|
| `/mission <objectif>` | Crée et exécute la mission ; gère la clarification et l'autorisation par interaction |
| `/missions` | Liste les missions |
| `/mission-status <id>` | Plan, faits, erreurs, étapes non terminées |
| `/mission-answer <id> <texte>` | Répond à une demande en attente |
| `/mission-cancel <id>` | Arrête la mission |
| `/mission-resume <id>` | Reprend une mission interrompue |

Le CLI transmet désormais son `session_id` aux appels d'outils : les jetons de
confirmation de la Phase 5 sont ainsi liés à la session.

### 10.2 Web (6 routes)

| Route | Effet |
|-------|-------|
| `POST /mission` | Crée la mission, l'exécute dans un fil séparé |
| `GET /missions` | Liste les missions |
| `GET /mission/<id>` | État détaillé |
| `POST /mission/<id>/authorize` | Accorde ou refuse l'autorisation |
| `POST /mission/<id>/answer` | Répond à une demande |
| `POST /mission/<id>/cancel` | Arrête la mission |

- Contrôles conservés côté serveur : le client ne décide d'aucune permission ;
  il ne fait qu'*acquiescer* à une demande d'autorisation déjà formulée par
  l'orchestrateur.
- **Anti-double-exécution** : `POST /mission` avec un objectif déjà en cours
  renvoie la mission existante (`already_running: true`) et ne relance rien ;
  le fil d'exécution d'une mission n'est jamais dupliqué.
- Aucune nouvelle page HTML n'a été ajoutée (l'interface web reste
  pilotée par l'API, conformément à la consigne « intégration compatible
  uniquement »).

---

## 11. Tests

### 11.1 Nouveau fichier `tests/test_mission_orchestrator.py` (73 tests)

| # | Catégorie exigée | Classes de tests |
|---|------------------|------------------|
| 1 | Création d'une mission | `TestMissionCreation` (4) |
| 2 | Génération et validation d'un plan | `TestPlanGeneration` (7) |
| 3 | Exécution dans l'ordre | `TestStepExecution.test_etapes_executees_dans_ordre` |
| 4 | Résultat d'une étape utilisé dans la suivante | `TestStepExecution.test_resultat_etape_utilise_dans_etape_suivante` |
| 5 | Échec d'outil et reprise limitée | `TestFailureHandling.test_echec_transitoire_repris_une_fois` |
| 6 | Épuisement des tentatives | `TestFailureHandling.test_tentatives_epuisees_echec_definitif` |
| 7 | Dépassement du nombre maximal d'étapes | `TestExecutionBounds.test_depassement_max_etapes` |
| 8 | Dépassement de durée / annulation | `TestExecutionBounds.test_depassement_duree`, `test_annulation` |
| 9 | Demande de clarification | `TestClarification` (4) |
| 10 | Refus d'un outil non autorisé | `TestAuthorization.test_outil_non_autorise_refuse` |
| 11 | Action sensible sans confirmation | `TestAuthorization.test_action_sensible_bloquee_sans_autorisation` |
| 12 | Confirmation expirée ou rejouée | `TestAuthorization` (3 tests de jeton) + 4 tests de grant |
| 13 | Aucun fichier modifié | `TestPilotMission.test_mission_pilote_ne_modifie_aucun_fichier` |
| 14 | Absence d'invention de résultats | `TestNoFabrication` (3) |
| 15 | Fournisseur indisponible / réponse mal formée | `TestProviderDegradation` (5) |
| 16 | Persistance et reprise | `TestPersistence` (5) |
| 17 | Intégration CLI | `TestCliIntegration` (7) |
| 18 | Intégration web | `TestWebIntegration` (7) |
| 19 | Chemins hors du répertoire autorisé | `TestPilotMission.test_chemin_hors_perimetre_refuse`, `test_lecture_fichier_sensible_refusee` |
| 20 | Absence de régression | `TestNoRegression` (5) |

### 11.2 Résultats

| Contrôle | Commande | Résultat |
|----------|----------|----------|
| Tests Phase 6 | `python -m unittest tests.test_mission_orchestrator` | **73 OK** |
| Suite complète | `python -m unittest discover -s tests` | **451 OK, 0 échec, 4 ignorés** (44–79 s) |
| Compilation | `python -m compileall app miles.py` | **OK** |
| Intégrité | `git diff --check` | aucune erreur d'espace |

Les 4 tests ignorés sont les limites Windows connues (3 symlink, 1
descripteurs de fichiers) : ils ne sont pas des régressions.

---

## 12. Limites restantes et risques

| Limite | Impact | Suite possible |
|--------|--------|----------------|
| L'identité de session est un jeton aléatoire par exécution, **pas** une identité humaine authentifiée | Une autorisation n'est pas rattachée à une personne | Authentification réelle avant exposition multi-utilisateur |
| Le serveur web est local (`127.0.0.1`) et **sans authentification** | Toute personne ayant accès à la machine peut agir par l'API | Authentification + isolation multi-session |
| Les outils ne sont **pas** exposés au modèle | L'orchestrateur est piloté par l'utilisateur (CLI/web) | Function calling avec grant lié à l'utilisateur |
| La mission pilote n'analyse que 2 niveaux et 3 fichiers | Analyse non exhaustive | Liste configurable, parcours récursif borné |
| `status_read` reste un état de référence statique | Pas d'état live | Snapshot partagé |
| Pas d'outil d'écriture | La mission ne peut rien corriger | Phase ultérieure, avec risque HIGH et double confirmation |
| L'analyse qualitative IA est « non vérifiée » | Peut contenir une erreur | Croisement obligatoire avec les faits |
| Validation Debian 13 non faite | Tests validés sous Windows uniquement | À exécuter par Agent B |
| `action_read_file` lit 20 Kio par fichier | Un gros fichier n'est pas lu | Lecture par Windowes, avec mention explicite |

**Aucun risque bloquant n'a été contourné.** Les zones non testées sont
listées ci-dessus de façon explicite.

---

## 13. Confidentialité

- Aucun secret, clé API, mot de passe ou donnée personnelle dans le code, les
  tests, la documentation ou les messages.
- Les contenus lus par les outils sont expurgés avant retour et avant écriture
  sur disque.
- L'artefact local parasite `tatus --short --branch` est **préservé et non
  committé**.
- Aucun appel API payant, aucun téléchargement de modèle, aucune installation.

---

## 14. Fichiers

**Créés**
- `app/orchestration/__init__.py`
- `app/orchestration/models.py`
- `app/orchestration/planner.py`
- `app/orchestration/executor.py`
- `app/orchestration/observer.py`
- `app/orchestration/runner.py`
- `app/orchestration/store.py`
- `app/orchestration/report.py`
- `app/tools/grants.py`
- `tests/test_mission_orchestrator.py`
- `docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_A.md`

**Modifiés**
- `app/tools/engine.py` (contexte/session sur les confirmations, grant checker)
- `app/tools/service.py` (propagation `context_id` / `actor_id`, `grant_checker`)
- `app/tools/builtin.py` (`action_read_file`, paramètre `depth`, `READ_ONLY_TOOLS`)
- `app/tools/local_actions.py` (listing structuré et borné, lecture encadrée)
- `app/interface/cli.py` (6 commandes de mission, session id)
- `app/interface/web.py` (6 routes de mission, exécution en fil séparé)
- `app/config/settings.py` (paramètres de l'orchestrateur)
- `miles.py` (câblage du service, du registre d'autorisations et de l'orchestrateur)
- `docs/installation/INSTALL.md` (section 3quater, 6 variables documentées)
- `docs/coordination/{TASKS,STATUS,DECISIONS}.md` (TASK-DEV-014, DEC-009)
- `tests/test_docs_configuration.py` (compte des variables : 25)
- `tests/test_tool_integration.py` (contrat du listing structuré, 5 outils)
