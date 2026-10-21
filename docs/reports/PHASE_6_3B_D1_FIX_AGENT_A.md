# docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md — Correction D1 : autorisation des missions web

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Dépôt** : `C:\Users\StanC\Desktop\Milescorp` (remote `https://github.com/Miles-corp/Milescorp.git`)
- **SHA de base (vérifié)** : `fc179ca6671908990e1a6c042bd35108f285c498` (`fix/miles-mission-bounds` ; branche de documentation de la Phase 6.3)
- **Branche de correction** : `fix/miles-d1-web-authorization`
- **`main`** : `b9b7e7d` — **inchangée**
- **Branche d'intégration auditée par Agent B** : `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **inchangée**
- **Défaut corrigé** : D1 du rapport `PHASE_6_3_VALIDATION_UTILISATEUR_AGENT_A.md` (§4)

> **Aucune fusion n'a été effectuée.** Le correctif attend l'audit
> indépendant d'Agent B.

---

## 1. Diagnostic : pourquoi les deux identifiants diffèrent

### 1.1 Les deux emplacements de code

| Emplacement | Code avant | Rôle |
|-------------|-----------|------|
| `app/orchestration/runner.py:440-447` (`authorize`) | `session_id=requester_session_id or mission.session_id` | **ÉMISSION** du grant : pour la session du client qui a demandé l'autorisation |
| `app/orchestration/runner.py:853-855` (`_ensure_authorization`) | `self.grant_registry.authorize(step.tool_id, parameters, mission.mission_id, self.session_id)` | **VÉRIFICATION** du grant : avec la session de l'application |

Le quatrième argument de `GrantRegistry.authorize` est l'« acteur » : le
grant n'est accepté que si `grant.session_id == acteur` (voir
`app/tools/grants.py`, `GrantRegistry.authorize` et `GrantRegistry.covers`).

### 1.2 Pourquoi les deux sessions diffèrent

| Contexte | Session du runner (`self.session_id`) | Session de la mission (`mission.session_id`) | Égalité |
|----------|--------------------------------------|--------------------------------------------|---------|
| **Ligne de commande** | `session_id` de l'application (`miles.py:194`, `default_session_id("miles")`), identique à celui de la CLI (`miles.py:310`) | la CLI crée la mission avec `owner_session_id=self.session_id` → **la même session** | ✅ identiques |
| **Interface web** | la session **de l'application** (une seule pour tout le processus) | la session **du client**, créée par `POST /session` et passée par `WebApp.create_mission` (`owner_session_id=session.session_id`) | ❌ **différentes** |

Conséquence observée avant correctif : dans le web, le grant légitime était
refusé, une **nouvelle** demande d'autorisation était levée, et la mission
bouclait jusqu'à l'épuisement du budget d'échanges
(`interaction_budget_exceeded`). Le défaut était **invisible en ligne de
commande** (les deux sessions y coïncident), ce qui explique qu'il n'ait
pas été détecté par les tests d'audit existants.

### 1.3 Preuve directe

```
grant émis pour la session du CLIENT  -> accepté   : 3e62423fc5514d5b118777707b8dcb0
grant émis pour la session du CLIENT  -> refusé par la session du RUNNER : None
```

### 1.4 Cohérence avec le reste du code

L'exécuteur utilise **déjà** la bonne référence pour lier les jetons de
confirmation des outils (`app/orchestration/executor.py:221`) :

```python
actor_id=mission.session_id or self._session_id,
```

La vérification de l'autorisation était donc la **seule** incohérence du
circuit. Le correctif la met en conformité avec l'émission et avec
l'exécuteur, sans rien changer d'autre.

---

## 2. Correctif appliqué (minimal)

`app/orchestration/runner.py`, fonction `_ensure_authorization` :

```diff
         grant_id = self.grant_registry.authorize(
-            step.tool_id, parameters, mission.mission_id, self.session_id
+            step.tool_id,
+            parameters,
+            mission.mission_id,
+            mission.session_id or self.session_id,
         )
```

**Une seule ligne de code modifiée** (plus 13 lignes de commentaire
explicatif). Rien d'autre n'est touché : ni la politique de sécurité, ni D2,
ni D3, ni D4, ni le moteur d'outils, ni l'interface web.

**Pourquoi `mission.session_id or self.session_id`** : la mission appartient
au client qui l'a créée ; sa session est donc l'identité à vérifier. Le
repli sur la session du runner préserve le comportement des missions
historiques (CLI) dont la session de mission serait vide.

**Sécurité préservée** : le grant reste lié à **trois** éléments — la session
du client, l'identifiant de la mission, et le périmètre d'outils et de
racines. La vérification utilise désormais l'identité **réellement
détenue** par le client, ce qui est plus strict que la session de
l'application (partagée par tous les clients). Un grant web reste
inutilisable depuis une autre session (test dédié).

---

## 3. Tests ajoutés

`tests/test_mission_web_authorization.py` (nouveau, 6 tests) — le chemin web
réel est exercé (`WebApp.create_mission` puis `WebApp.authorize_mission`), avec
un runner dont la session **diffère** de celle du client (comme en production).

| # | Test exigé | Test | Résultat |
|---|-----------|------|----------|
| 1 | Test de régression reproduisant D1 | `test_mission_web_autorisee_se_termine` | ✅ la mission atteint `completed`/`partial`, **1 échange**, 2 étapes exécutées |
| 1bis | Pré-condition du défaut | `test_session_client_differente_de_la_session_application` | ✅ les deux sessions diffèrent bien |
| 2 | Une mission web autorisée continue et se termine | `test_mission_web_autorisee_se_termine` | ✅ |
| 3 | Une mission web sans autorisation valide ne peut pas continuer | `test_mission_web_sans_autorisation_valide_ne_continue_pas` | ✅ état `awaiting_authorization`, **0 étape** exécutée, **0 grant** émis (jeton forgé et jeton absent testés) |
| 4 | Une autorisation n'est pas réutilisable depuis une autre session | `test_autorisation_non_reutilisable_par_une_autre_session` | ✅ le grant est émis pour la session d'Alice, refusé pour la session de Bob, accepté pour Alice |
| 4bis | Un autre client ne peut pas agir sur la mission d'un client | `test_mission_d_un_autre_utilisateur_refusee` | ✅ refus explicite |
| — | Invariant du runner (indépendant de l'interface) | `test_la_verification_utilise_la_session_de_la_mission` | ✅ le grant est refusé pour la session de l'application et accepté pour la session du client |

### 3.1 Le test de régression échoue-t-il **avant** le correctif ?

Vérifié explicitement (correctif retiré temporairement, puis restauré) :

```
code sans correctif : FAIL: test_mission_web_autorisee_se_termine  (40,2 s)
code avec correctif : OK   (6 tests, 1,4 s)
```

Les 40 secondes correspondent au symptôme D1 : la mission reboucle jusqu'à
l'épuisement du budget d'échanges. Les autres tests passent dans les deux cas
(ils vérifient la propriété de sécurité, déjà correcte avant le correctif) —
c'est normal et assumé.

---

## 4. Commandes exécutées et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_mission_web_authorization` | **6 tests, 0 échec** (1,4 s) |
| `python -m unittest tests.test_mission_web_authorization` *(code sans correctif)* | **1 échec** (le test de régression D1) |
| `python -m unittest tests.test_mission_orchestrator` | **73 tests, 0 échec** (17,1 s) |
| `python -m unittest tests.test_mission_bounds` | **20 tests, 0 échec** (5,9 s) |
| `python -m unittest tests.test_web_security_phase6_1` | **35 tests, 0 échec** (10,6 s) |
| `python -m unittest discover -s tests` | **534 tests, 0 échec, 4 ignorés** (89,6 s) |
| Tests d'audit d'Agent B (rejoués tels quels, depuis `origin/audit/agent-b-phase6-1-web-security-review`) | **70 tests, 0 échec, 2 ignorés** (26,7 s) |

Les 4 + 2 tests ignorés sont des **limites de plateforme Windows** (3 liens
symboliques, 1 `/proc/self/fd`, 2 liens symboliques d'audit) ; ils
s'exécutent sous Debian 13.

---

## 5. Scénario web RÉEL exécuté

Le scénario n'est pas simulé : le **vrai serveur** (`python miles.py --web`)
a été démarré, une session a été ouverte, une mission créée, autorisée, et
l'état final observé.

```
=== 1. CONNEXION ===
  session : f5c4b7751def1714...  utilisateur : local
=== 2. CREATION DE LA MISSION ===
  mission : e24ace0f35d9  etat=created
=== 3. ATTENTE DE LA DEMANDE D AUTORISATION ===
  etat    : awaiting_authorization  demande=authorization
  question: Autoriser l'accès en lecture dans C:\Users\StanC\Desktop\Milescorp\docs
            pour les outils : action_list_files, action_read_file ?
=== 4. AUTORISATION ===
  reponse : 200 {'mission_id': 'e24ace0f35d9', 'approved': True, 'started': True}
=== 5. ETAT FINAL ===
  etat    : completed
  motif   : completed
  budget  : 5 etape(s), 5 appel(s), 1 echange(s)
  faits   : 7
     - Résultat de l'étape s1 : 32 caractère(s).
     - Analyse de C:\Users\StanC\Desktop\Milescorp\docs (profondeur 2) : 51 entrée(s) : 6 répertoire(s), 45 fichiers
     - Fichiers observés : .gitkeep, DECISIONS.md, HANDOFF.md, MESSAGES.md, ...
     - 4 fichier(s) non lus (binaire, hors texte ou sensible).

SCENARIO WEB : REUSSI
```

**Avant le correctif**, ce même scénario aboutissait à une boucle
d'autorisations puis à `interaction_budget_exceeded` (constaté lors de la
campagne de validation, §4 D1 du rapport Phase 6.3).

**Isolation** : les bases de la campagne ont été dirigées vers des fichiers
dédiés (`MILES_MISSION_DB_PATH`, `MILES_CONVERSATION_DB_PATH` →
`data/validation-d1-*.db`), supprimés à la fin. Les bases du développeur
(`data/missions.db`, `data/conversations.db`, `data/memory.db`) n'ont pas été
écrites.

---

## 6. Défaut connexe constaté (D1-bis) — **signalé, non corrigé**

Pendant la rédaction des tests, un défaut voisin a été mis au jour : quand
le jeton d'approbation est invalide, `POST /mission/<id>/authorize` renvoie
**tout de même** `{"approved": true, "started": true}`.

**Cause** : la validation du jeton d'approbation a lieu dans le **fil
d'exécution** de la mission (`WebApp.authorize_mission` →
`_start_mission_thread`), dont l'exception (`MissionAuthorizationError`) est
journalisée et non retournée au client ; le `try/except` qui jouait ce rôle
est placé autour du *démarrage* du fil, où l'exception ne peut pas
survenir.

**Portée réelle** : **aucune élévation de privilège** — l'autorisation n'est
pas accordée, la mission ne continue pas, aucun grant n'est émis (vérifié par
`test_mission_web_sans_autorisation_valide_ne_continue_pas`). Le défaut est
une **réponse HTTP trompeuse**.

**Non corrigé ici** : la mission porte sur le seul défaut D1, et ce point
touche la frontière d'autorisation de l'interface web. Il est proposé comme
correctif séparé : valider le jeton d'approbation **synchroniquement** dans
`WebApp.authorize_mission` (comparaison directe avec
`mission.pending.approval_token`) et ne démarrer le fil qu'ensuite.

---

## 7. Risques résiduels

| Risque | Statut |
|--------|--------|
| Le grant est désormais vérifié avec la session du client | **c'est l'objet du correctif** ; le lien session + mission + périmètre d'outils et de racines est inchangé et renforcé (la session de l'application était partagée par tous les clients) |
| D2 (lettre de lecteur) | non corrigé, hors périmètre |
| D3 (faux positifs de la politique sur les chemins) | non corrigé, hors périmètre (code de sécurité) |
| D4 (délai du fournisseur) | non corrigé, hors périmètre |
| D1-bis (réponse HTTP trompeuse sur jeton invalide) | signalé, non corrigé (§6) ; aucune élévation de privilège |
| Plateforme Debian 13 | non validée pour ce correctif (environnement indisponible) ; à rejouer par Agent B |
| Audit indépendant | **en attente** : le correctif n'est pas validé par Agent B |

---

## 8. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-d1-web-authorization` (poussée) |
| SHA de base | `fc179ca` (`fix/miles-mission-bounds`) |
| Fichiers modifiés | `app/orchestration/runner.py` (1 ligne de code + commentaire) |
| Fichiers ajoutés | `tests/test_mission_web_authorization.py` |
| `main` | `b9b7e7d` — **inchangée** |
| Branche auditée par Agent B | `69bf670` — **inchangée** |
| Artefact non suivi | `tatus --short --branch` — **préservé** |

---

## 9. Procédure de vérification indépendante

```bash
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-d1-web-authorization
git pull --ff-only

# Tests de régression D1
python -m unittest tests.test_mission_web_authorization -v

# Non-régression
python -m unittest tests.test_mission_orchestrator
python -m unittest tests.test_mission_bounds
python -m unittest tests.test_web_security_phase6_1
python -m unittest discover -s tests

# Scénario web réel
$env:MILES_WEB_AUTH_TOKEN = "jeton-de-validation"
$env:MILES_MISSION_DB_PATH = "data/validation-missions.db"
$env:MILES_CONVERSATION_DB_PATH = "data/validation-conversations.db"
python miles.py --web --web-port 8130
#   puis : POST /session -> POST /mission -> POST /mission/<id>/authorize
#   l état final attendu est « completed » avec 1 échange.
```

---

## 10. Prochaine action

1. **Audit indépendant par Agent B** du commit de correction (SHA de tête de
   `fix/miles-d1-web-authorization`), en particulier :
   - le lien grant ↔ session du client est bien respecté ;
   - un grant web reste inutilisable depuis une autre session ;
   - le scénario web complet aboutit à `completed` ;
   - les 70 tests d'audit existants restent verts.
2. **Ne pas fusionner** avant cet audit.
3. **D1-bis** : correction séparée à proposer (validation synchrone du jeton
   d'approbation dans `WebApp.authorize_mission`).
