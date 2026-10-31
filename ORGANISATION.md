# Organisation du dépôt MILES

Ce document décrit **ce que contient le dépôt, à quoi sert chaque dossier, et
quelle version fait référence**. Il complète `AGENTS.md` (règles de
collaboration) : `AGENTS.md` dit comment travailler, ce document dit où se
trouve le travail.

Dernière mise à jour : 2026-10-27 (Agent A).

---

## 1. En une phrase

MILES est un **assistant personnel local** : interface terminal, interface web,
mémoire persistante, outils autorisés, orchestration de missions. Le dépôt
contient le code de l'assistant **et** le pilotage du projet (documents de
coordination). L'ensemble des interfaces écoute en boucle locale uniquement
(`127.0.0.1`) et ne charge aucune ressource distante.

---

## 2. Référence du code

| Élément | Valeur |
|---|---|
| Branche de référence | `main` — avancée sur l'intégration le 2026-10-27 (avance rapide, sans `reset --hard`) |
| Ancienne branche de travail | `integration/miles-post-d1` — conservée à l'identique du commit de référence |
| Règle de publication | un commit local **n'est pas** une publication : aucun `push` sans accord explicite de l'utilisateur (DEC-004) |
| État de `origin/main` | en retard sur la référence locale tant que le `push` n'est pas autorisé |

Toute branche de travail est fusionnée dans la référence avant d'ouvrir un
nouveau lot. Un identifiant de tâche (`TASK-###`) ou de décision (`DEC-###`)
est **immuable et unique** (DEC-013).

---

## 3. Carte du dépôt

```
miles.py                 point d'entrée : CLI, mode web, sous-commandes
app/                     le programme (aucune dépendance externe obligatoire)
assets/                  ressources des interfaces (web et réservées)
tests/                   suite de tests (stdlib unittest)
docs/                    coordination, rapports datés, guides
config/                  exemples de configuration
data/                    données locales à l'exécution (hors Git)
logs/                    journaux à l'exécution (hors Git)
hardware/                emplacements réservés au matériel (Miles Box)
experiments/             emplacement réservé aux essais
scripts/                 emplacement réservé aux scripts d'exploitation
```

### Fichiers à la racine

| Fichier | Rôle |
|---|---|
| `miles.py` | unique point d'entrée : `--web`, sous-commandes (statut, mémoire, conversations…). C'est lui qui affiche le jeton d'accès web. |
| `AGENTS.md` | règles permanentes de collaboration entre agents (à lire avant toute tâche). |
| `ORGANISATION.md` | ce document : carte du dépôt, référence, réservé, supprimé. |
| `requirements.txt` | dépendances **optionnelles** (voix, `requests`) ; le socle fonctionne avec la bibliothèque standard seule. |
| `.env.example` | modèle de configuration locale — **sans secret**. |
| `.gitignore` | exclut `.env`, `config/*.local.json`, `data/*.db`, `logs/*.log`, caches Python. |

---

## 4. `app/` — le programme

| Paquet | Rôle |
|---|---|
| `app/ai_providers/` | fournisseurs IA : interface commune, distant (HTTP), local (serveur de modèle local), messages d'erreur publics. |
| `app/config/` | configuration (`settings.py`), assistant de première configuration, liaison de comptes OAuth. |
| `app/connectors/` | connecteurs locaux. `computer/actions.py` = actions locales autorisées ; les autres sous-dossiers sont **réservés**. |
| `app/core/` | cœur conversationnel (`conversation.py`) : historique et tours de parole. |
| `app/interface/` | interfaces : `cli.py` (terminal), `web.py` (serveur web + API), `web_auth.py` (sessions, origine, CSRF), `project_board.py` (lecture des documents de coordination), `device_telemetry.py` (mesures réelles du poste). |
| `app/interface/companion/` | **Miles Companion** : site local propriétaire (serveur 8787, coque React dans `frontend/` et build `dist/`, comptes et sessions, capteurs réels, relais borné vers MILES). L'ancien export Readdy (`index.html`, `miles-bridge.js`, `assets/`) n'est plus servi. |
| `app/memory/` | mémoire persistante locale (`persistent.py`), historique (`history.py`), transcriptions de conversations (`transcript.py`). |
| `app/orchestration/` | missions : planification, exécution, observation, compte rendu, persistance, messages d'attente honnêtes (`progress.py`). |
| `app/routing/` | routeur de demandes (`router.py`) : classification rapide/approfondi, désactivé par défaut. |
| `app/security/` | confinement des chemins (`paths.py`), registre et validation des actions locales (`validator.py`). |
| `app/tools/` | outils autorisés : registre, politique, moteur, autorisations (`grants.py`), audit, actions locales, service unique pour le CLI et le web. |
| `app/utilities/` | diagnostics GPU, neutralisation des secrets dans les textes sortants (`redaction.py`). |
| `app/voice/` | interface vocale **optionnelle** (`base.py`). |

---

## 5. Les interfaces (une seule implémentation par vue)

| Interface | Adresse | Ce qu'elle sert | Source |
|---|---|---|---|
| Serveur MILES | `127.0.0.1:8080` | l'API de l'agent **et** le cockpit projet | `app/interface/web.py` + `assets/web/` |
| Miles Companion | `127.0.0.1:8787` | façade unique (DEC-014) : application de pilotage, et le cockpit sous `/cockpit/` | `app/interface/companion/` |

Règles appliquées :

- le **cockpit projet** (vues Projet / Conversation / Mémoire / Outils) a **une
  seule implémentation**, `assets/web/`, servie à l'identique par les deux
  serveurs (racine sur 8080, `/cockpit/` sur 8787) ;
- l'ancienne page `/projet` du Companion **redirige** vers `/cockpit/` : la
  copie divergente a été supprimée ;
- aucune page ne référence de ressource distante (polices, icônes, images,
  analyse d'audience) : tout est servi depuis le dépôt ;
- une mesure n'est affichée que si elle a été **réellement obtenue** ; sinon la
  page l'annonce indisponible avec sa raison.

---

## 6. `docs/coordination/` — le pilotage du projet

| Fichier | Rôle |
|---|---|
| `TASKS.md` | tableau des tâches (identifiant, état, agent responsable, fichiers autorisés, résultat attendu). Source de vérité des assignations. |
| `STATUS.md` | état instantané de chaque agent et du projet. |
| `DECISIONS.md` | journal **append-only** des décisions d'architecture validées. |
| `MESSAGES.md` | canal asynchrone entre agents (questions, réponses, alertes, demandes d'audit). |
| `HANDOFF.md` | comptes rendus officiels de transfert de tâche. |
| `MEMORY-BUFFY.md` | journal de session de l'agent : ce qui a été décidé, vérifié, et la prochaine action. |
| `WORKFLOW.md` | déroulé de travail attendu entre les deux agents. |
| `REPORT_TEMPLATE.md` | modèle de compte rendu. |

Le cockpit lit ces fichiers et n'en écrit **qu'un seul** : les statuts de
`TASKS.md`, avec transitions bornées, propriétaire vérifié, écriture atomique et
journal d'audit hors Git.

---

## 7. `docs/` — rapports, guides, références

| Dossier | Contenu | Nature |
|---|---|---|
| `docs/reports/` | comptes rendus datés par phase (`PHASE_*`, `MILESTONE-*`, audits) | **historique** : un rapport décrit l'état à sa date, il n'est pas réécrit |
| `docs/installation/` | `INSTALL.md`, `QUICKSTART.md` | référence d'installation |
| `docs/user_guide/` | plan de test utilisateur de la Phase 6 | guide |
| `docs/architecture/` | **réservé** (vide) | à remplir par les futures spécifications |
| `docs/security/` | **réservé** (vide) | à remplir par les synthèses de sécurité |

En cas de contradiction entre un rapport daté et ce document, **ce document et
les documents de coordination font référence**.

---

## 8. Données, journaux, secrets

| Chemin | Contenu | Règle |
|---|---|---|
| `.env` | configuration locale, clés de fournisseurs | **jamais committé** ; jamais affiché ; `.env.example` sert de modèle |
| `config/config.json` | configuration JSON optionnelle | facultative ; l'exemple `config/config.json.example` est versionné |
| `data/*.db` | mémoire persistante, missions, conversations | hors Git ; données utilisateur |
| `logs/*.log` | journaux d'exécution | hors Git |
| jeton d'accès web | affiché **une seule fois** au démarrage de `miles.py --web` | délibérément **écrit nulle part** : ni sur disque, ni dans un cookie |

Toute sortie de programme passe par `app/utilities/redaction.py` avant d'être
affichée : un secret ne doit pas apparaître dans un journal ou une réponse.

---

## 9. Emplacements réservés (présents, sans code)

Ces dossiers sont conservés parce qu'ils décrivent la structure visée ; ils
**ne contiennent aucun code** aujourd'hui :

`app/connectors/services/`, `app/connectors/smart_home/`,
`app/connectors/smartphone/`, `app/connectors/web/`,
`assets/icons/`, `assets/images/`, `assets/sounds/` (l'application utilise les
ressources de chaque interface), `docs/architecture/`, `docs/security/`,
`experiments/`, `hardware/diagrams/`, `hardware/prototypes/`, `scripts/`,
`tests/unit/`, `tests/integration/`, `tests/end_to_end/`.

Chacun est maintenu dans Git par un unique fichier marqueur `.gitkeep` : un
dossier vide n'existe pas dans Git, le marqueur est donc ce qui garde la place.
En revanche, un `.gitkeep` n'a aucun sens dans un dossier **déjà rempli** de
fichiers suivis : les douze qui s'y trouvaient encore ont été retirés (§11).

---

## 10. Lancer et vérifier

```bash
# Serveur MILES (API + cockpit). Le jeton d'accès s'affiche au démarrage.
python miles.py --web                 # 127.0.0.1:8080

# Site Miles Companion (coque React + cockpit sous /cockpit/).
# Premier lancement : créer l'administrateur sur la box (aucune inscription publique).
python -m app.interface.companion.auth add <identifiant> --role admin
python app/interface/companion/server.py --port 8787

# Après une modification de l'interface : reconstruire la coque servie.
cd app/interface/companion/frontend && npm ci && npm run build

# Tests : l'ensemble de la suite, sans réseau externe.
python -m unittest discover -s tests
```

Contrôles utiles :

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/cockpit/   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/device # 401 sans session
```

---

## 11. Ce qui a été supprimé (et pourquoi)

Le tri du 2026-10-27 a retiré ce qui n'était **référencé nulle part**, en
vérifiant chaque élément avant suppression :

| Élément supprimé | Poids | Preuve d'inutilité |
|---|---|---|
| `app/interface/companion/assets/fontawesome/` | 1,05 Mo (10 fichiers) | la feuille FontAwesome était liée par la page, mais aucune classe `fa-*` n'existait dans le HTML, le CSS ni le JS du build : l'application utilise RemixIcon (`ri-*`). Vérifié après suppression : aucune requête en échec. |
| `app/interface/companion/projet.html` | 517 lignes | seconde implémentation de la vue Projet, face au cockpit `assets/web/` déjà testé : `/projet` redirige désormais vers `/cockpit/`. |
| 12 fichiers `.gitkeep` | — | présents dans des dossiers qui contiennent déjà des fichiers suivis (`app/interface/`, `app/memory/`, `config/`…) : ils ne gardaient plus rien. Les 18 marqueurs des dossiers réservés (§9) sont **conservés**, eux. |

Le fichier `logs/companion.out` (sortie d'un lancement manuel) a également été
retiré : les journaux d'exécution n'ont pas leur place dans le dépôt.

Détail du tour précédent de ce tri (inventaire et identifiants) :
`docs/reports/REPO_TRIAGE_AGENT_A.md`.

---

## 12. Où regarder pour…

| Besoin | Fichiers |
|---|---|
| Ajouter une route HTTP | `app/interface/web.py` (route + contrôle), `assets/web/app.js` (client), `tests/test_web*.py` |
| Modifier le design du cockpit | `assets/web/index.html`, `assets/web/app.css`, `assets/web/app.js` |
| Modifier l'application Companion | `app/interface/companion/frontend/src/**` (React/TypeScript), puis `npm run build` ; serveur et API dans `server.py` |
| Comprendre les comptes, rôles et sessions | `app/interface/companion/auth.py`, `store.py` (base `data/companion.db`) |
| Ajouter un capteur réel | `app/interface/companion/sensors.py` (mesure ou indisponibilité motivée) |
| Ajouter ou typer une applet | `app/interface/companion/applets.py` (`system` / `render` / `action`) |
| Brancher les capteurs de la Miles Box | `app/interface/device_telemetry.py` (mesures et capteurs déclarés indisponibles) |
| Changer un statut de tâche | page Projet du cockpit (transitions validées par le serveur) — jamais à la main dans `TASKS.md` si le cockpit peut le faire |
| Comprendre une décision d'architecture | `docs/coordination/DECISIONS.md` |
| Reprendre le travail après une interruption | `docs/coordination/MEMORY-BUFFY.md` (journal de session et prochaine action) |
