# docs/reports/PHASE_6_3I_MISSION_PERSISTENCE_AGENT_A.md — D-B05 (persistance des missions) et validation D-B01

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Base de travail** : `25baa60e2691f54900111a11194cf7e186419050` (`fix/miles-answer-d1ter` : D1 + D2 + D1-bis + D3 + A-α/B-α)
- **Branche de correction** : `fix/miles-mission-persistence-owner`
- **Rapport d'audit examiné** : `docs/reports/AUDIT_MILES_PHASE5_6_61_AGENT_B.md` (Agent B, `origin/audit/agent-b-phase6-1-web-security-review` = `fd25a26`)
- **`main`** : `b9b7e7d` — **inchangée**
- **Intégration** : `69bf670` — **inchangée**

> **Aucune fusion.** Les audits D1, D2, D1-bis, D3 et A-α/B-α sont **en
> cours** : ce correctif n'est pas validé et ne doit pas être fusionné sans
> décision explicite.

---

## 1. Préalables Git — l'état réel, sans supposition

Le contrôle demandé (« ne pas supposer que les branches mentionnées dans les
anciens rapports sont toujours à leur SHA annoncé ») porte **attention** :

| Branche | SHA réel relevé | Observation |
|---------|-----------------|-------------|
| `origin/fix/miles-answer-d1ter` | `25baa60e2691f54900111a11194cf7e186419050` | ✔ conforme à l'annonce |
| `origin/fix/miles-policy-path-typing` (D3) | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` | inchangé |
| `origin/fix/miles-d1bis-authorization-response` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | inchangé |
| `origin/fix/miles-windows-paths` (D2) | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` | inchangé |
| `origin/fix/miles-d1-web-authorization` (D1) | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` | inchangé |
| `origin/main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | inchangé |
| `origin/integration/miles-phases-5-6-6-1` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` | inchangé |
| **`origin/audit/agent-b-phase6-1-web-security-review`** | **`fd25a26d291e58d93c621a1668a51cd8988b02ea`** | **⚠️ la branche d'audit a BOUGE** (elle était à `ac627df` lors de mes travaux précédents) : nouveau commit « audit contradictoire (Agent B) » |

**Point d'attention (conformité à la consigne) :** le rapport d'audit cité
par ce document est le **dernier** commit de la branche d'audit (`fd25a26`).
Il porte sur l'arbre **Phase 5/6/6.1** (`a11ab4a` → `0754032` → `c0cb01b`),
c'est-à-dire **en amont** de mes correctifs : il ne contredit aucun de mes
constats et ne signale aucune régression sur D1, D2, D1-bis, D3 ou A-α/B-α.
Il **confirme** en revanche D-B01 (voir §3). Aucun de mes constats n'est
contredit ; je n'ai donc pas de suspension à appliquer.

**État des worktrees** : 6 worktrees actifs (principal + D1bis, D2, D3,
investigation, answer) ; le travail présent a été fait dans un **septième**
worktree dédié (`Temp/miles-persist`). Le checkout principal reste sur
`fix/miles-d1-web-authorization` avec son artefact non suivi
`tatus --short--branch` **préservé** ; aucune base de données du développeur
n'a été écrite.

---

## 2. Les défauts D-B01 à D-B06 examinés sur la base de travail

Vérification faite **sur le code réel** de la base `25baa60` (et non sur le
rapport) :

| Défaut | Constat Agent B | État sur la base de travail | Preuve |
|--------|-----------------|------------------------------|---------|
| **D-B01** | La politique refuse les chemins légitimes contenant « code », « shell », « token », « password » (P2) | **CORRIGÉ** par le correctif de typage explicite (branche D3, `0be08cd`) | `ToolParameter.is_path` déclaré ; la politique valide structurellement les valeurs de chemin ; **reproduction exacte en §4** |
| **D-B02** | Le `session_id` est un jeton porteur non lié au navigateur (P2, réserve de conception) | **inchangé — réserve assumée** | Agent B : « Non applicable (réserve assumée et documentée par Agent A dans `web_auth.py`) ». Le modifier touchera l'authentification : **hors périmètre** (composant de sécurité en audit) |
| **D-B03** | Bornes de mission par passage de boucle, non par mission (P2) | **CORRIGÉ** (Phase 6.2) | `MissionBudget` porte désormais `executed_seconds`, `steps_executed`, `tool_calls`, `interactions`, `identical_results` : les compteurs sont sur la mission **persistée** |
| **D-B04** | Borne « 5 échanges » présente en CLI uniquement (P2) | **CORRIGÉ** (Phase 6.2) | `ExecutionLimits.max_interactions = 5` est appliqué par l'orchestrateur (CLI **et** web) |
| **D-B05** | `results` non persistés, `list_missions` ignore la base, `record_event` jamais appelé, étape `RUNNING` non reprise (P2) | **partiellement corrigé** : `record_event` est appelé (7 occurrences) ; **la liste ignore toujours la base** ; `results` reste local ; l'étape `RUNNING` n'est pas reprise → **2 points ouverts, traités ci-dessous** | voir §3 |
| **D-B06** | L'interface web des missions n'est pas lançable par `miles.py` (P3) | **CORRIGÉ** (Phase 6.1) | `miles.py --web` existe et lance `MilesWebServer` (utilisé dans toutes mes validations) |

**Choix de la tâche** : D-B05 est le seul défaut encore ouvert, et il est
**indépendant** des branches d'autorisation et de sécurité en audit : il
porte sur la **persistance** (`app/orchestration/store.py`) et sur la
**liste** des missions (`app/orchestration/runner.py::list_missions`) — ni la
politique de sécurité, ni les permissions, ni le confinement des chemins, ni
les routes d'autorisation ne sont touchés.

---

## 3. D-B05 — Le défaut et son impact

### 3.1 La liste des missions ignore la base

`MissionRunner.list_missions` ne listait que les missions **en mémoire** :

```python
with self._lock:
    missions = list(self._missions.values())
```

`MissionStore.list_missions` existait mais **n'était jamais appelé** (le
magasin ne persistait qu'à la demande, jamais en lecture pour la liste).

**Impact** : après un redémarrage du programme, toutes les missions
enregistrées disparaissent de la liste (`/missions` en console, `GET
/missions` dans l'interface web) ; seule la mission dont on connaît
l'identifiant reste consultable. L'historique des missions est perdu pour
l'utilisateur.

### 3.2 Constat complémentaire : le propriétaire n'était pas persisté

En cherchant la cause du point précédent, un défaut plus grave est apparu :
`Mission.owner_user_id` est bien sérialisé par le modèle
(`to_dict`/`from_dict`), mais la table `missions` **ne possédait pas cette
colonne** et `MissionStore.save` ne l'écrivait pas.

**Impact** : au rechargement d'une mission, `owner_user_id` valait `""`. Or
l'interface web fonde la séparation entre utilisateurs sur ce champ
(`MissionRunner.get(..., owner_user_id=...)` et `WebApp.answer_mission`) :

```python
if mission.owner_user_id and str(requester_user_id) != mission.owner_user_id:
    ...  # refus
```

Un propriétaire **inconnu** fait échouer la condition de garde : la
séparation entre utilisateurs **ne tient plus** pour les missions rechargées
(la lecture du détail d'une mission, `/mission/<id>/answer`,
`/mission/<id>/cancel`). L'identifiant de mission étant aléatoire
(48 bits), l'exploitation n'est pas directe ; la **gravité** reste faible
(les identifiants de mission ne sont pas devinables), mais c'est une
**défense qui s'éteint silencieusement** au redémarrage — exactement le
type de constat que l'audit d'Agent B formule pour D-B05.

### 3.3 Le correctif

**`app/orchestration/store.py`**

1. `SCHEMA_VERSION` passe de 2 à 3 ;
2. la table `missions` comporte la colonne `owner_user_id TEXT NOT NULL
   DEFAULT ''` ;
3. **migration** : une base existante (sans la colonne) est mise à jour par
   `ALTER TABLE` — même mécanisme que la migration `budget_json` existante ;
4. `save()` écrit le propriétaire (INSERT et `ON CONFLICT DO UPDATE`) ;
5. `load()` le relit ;
6. `list_missions(limit, *, owner_user_id=None)` filtre désormais sur le
   propriétaire lorsqu'il est fourni.

**`app/orchestration/runner.py::list_missions`**

Les missions en mémoire et les missions **persistées** sont combinées,
dédupliquées par identifiant, triées par date de création décroissante et
tronquées à la limite. Le filtre par propriétaire est appliqué aux deux
sources.

---

## 4. D-B01 — Validation du correctif de typage (reproduction exacte)

L'audit d'Agent B demande explicitement un test de non-régression nommé
`test_chemin_legitime_contenant_code_accepte` et signale que son propre
clon, placé dans `.../Temp/opencode/merged_tree`, faisait **échouer 2
tests**.

**Reproduction, faite dans les conditions décrites par l'audit** (dépôt
placé dans un répertoire dont le chemin contient `code`) :

| Base | Emplacement | Résultat |
|------|-------------|----------|
| `1ef4878` (D1-bis, **avant** D3) | `...\Temp\opencode\miles-pre-d3` | **575 tests — 2 échecs** : `test_lecture_d_un_fichier_volumineux` et `test_resultat_volumineux_au_dela_du_tampon` — **les deux tests exactements cités par l'audit** |
| `0be08cd` (**avec** D3) | `...\Temp\opencode\miles-d3` | **615 tests — 0 échec, 4 ignorés** |

Le constat d'Agent B est donc **confirmé** (reproduction à l'identique) et le
correctif de typage le **résout**. Le test de non-régression demandé
(`test_chemin_legitime_contenant_code_accepte`) est ajouté dans
`tests/test_mission_persistence_owner.py` : il **ne dépend pas** de
l'emplacement du dépôt (il construit lui-même les chemins litigieux), afin
d'être fiable sur toutes les machines.

---

## 5. Tests

Fichier ajouté : `tests/test_mission_persistence_owner.py` — **9 tests**.

| # | Test | Ce qu'il fixe |
|---|------|----------------|
| 1 | `test_le_proprietaire_est_persiste` | le propriétaire survit au rechargement |
| 2 | `test_la_liste_inclut_les_missions_persistees` | une mission enregistrée et rechargée apparaît dans la liste |
| 3 | `test_la_liste_ne_melange_pas_les_utilisateurs` | la liste filtrée ne montre que les missions de son utilisateur (**test d'isolation**) |
| 4 | `test_une_mission_n_est_pas_listee_deux_fois` | pas de doublon mémoire/base |
| 5 | `test_la_liste_est_triee_du_plus_recent_au_plus_ancien` | tri décroissant conservé |
| 6 | `test_la_liste_respecte_la_limite` | la limite de taille est respectée |
| 7 | `test_une_base_ancienne_sans_proprietaire_reste_lisible` | une base antérieure à la migration reste lisible (les missions sans propriétaire connu ne sont pas proposées dans une liste filtrée, mais restent visibles dans la liste non filtrée) |
| 8 | `test_chemin_legitime_contenant_code_accepte` | **test de non-régression D-B01 demandé par l'audit** |
| 9 | `test_une_valeur_libre_contenant_code_reste_refusee` | le correctif D-B01 n'affaiblit pas le contrôle des valeurs libres |

### 5.1 Les tests échouent-ils sans le correctif ?

| Situation | Résultat |
|-----------|----------|
| Correctifs appliqués | `Ran 9 tests — OK` |
| **Revert de `app/orchestration/store.py` + `app/orchestration/runner.py`** | **`FAILED (failures=3)`** : `test_le_proprietaire_est_persiste`, `test_la_liste_inclut_les_missions_persistees`, `test_la_liste_ne_melange_pas_les_utilisateurs` |

Les 3 tests qui échouent sont exactement ceux qui décrivent le défaut ; les
6 autres vérifient des propriétés déjà acquises (tri, limite, déduplication,
migration, D-B01) et restent verts.

### 5.2 Commandes et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_mission_persistence_owner` | **9 tests, 0 échec** (1,8 s) |
| `python -m unittest tests.test_mission_persistence_owner` *(revert)* | **3 échecs** |
| `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_web_authorization` (D1) | 6 tests, 0 échec |
| `python -m unittest tests.test_windows_paths` (D2) | 21 tests, 0 échec |
| `python -m unittest tests.test_policy_path_typing` (D3) | 40 tests, 0 échec |
| `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| `python -m unittest discover -s tests` | **642 tests, 0 échec, 4 ignorés** (91,1 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (22,1 s) |

Les tests ignorés (4 + 2) sont des **limites de plateforme Windows** (liens
symboliques, `/proc/self/fd`) ; ils s'exécutent sous Debian 13. **Aucune
validation Debian 13 n'a été possible ici** (environnement indisponible),
comme pour les missions précédentes.

---

## 6. Diff complet

### `app/orchestration/store.py` (+55 / −22)

- `SCHEMA_VERSION` : 2 → 3 ;
- colonne `owner_user_id` dans le schéma + migration `ALTER TABLE` pour les
  bases existantes ;
- écriture du propriétaire dans `save()` (INSERT + `ON CONFLICT DO UPDATE`) ;
- lecture du propriétaire dans `load()` ;
- `list_missions(limit, *, owner_user_id=None)` : filtrage par propriétaire.

### `app/orchestration/runner.py` (+38 / −6)

- `list_missions` combine les missions en mémoire et les missions
  persistées, déduplique, trie et applique le filtre de propriétaire.

### `tests/test_mission_persistence_owner.py` (nouveau)

9 tests (voir §5).

**Aucun autre fichier n'est modifié** : ni la politique de sécurité
(`app/tools/policy.py`), ni les permissions, ni le confinement des chemins
(`app/security/paths.py`), ni les routes d'autorisation, ni le
planificateur, ni les outils.

---

## 7. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | Les missions enregistrées **avant** la migration n'ont pas de propriétaire : elles n'apparaissent pas dans la liste filtrée par utilisateur (elles restent visibles dans la liste non filtrée, propre à la console locale) | choix **sûr** : ne pas attribuer un propriétaire inconnu à quelqu'un. Documenté et testé (test 7) |
| 2 | La migration ajoute une colonne à une base existante : elle est idempotente (`PRAGMA table_info` avant `ALTER TABLE`) et suit le mécanisme déjà en place pour `budget_json` | vérifié par le test 7 (base créée avant la migration) |
| 3 | `results` (résultats d'étapes) et l'étape `RUNNING` ne sont toujours pas persistés / repris | **points D-B05 restants**, non traités ici (ils touchent le modèle d'exécution des missions, plus large) ; à traiter dans un lot dédié |
| 4 | D-B02 (le `session_id` est un jeton porteur) | réserve de conception assumée ; **non touchée** (composant d'authentification en audit) |
| 5 | La liste combine désormais mémoire et base : une mission supprimée de la base mais encore en mémoire reste listée | comportement cohérent (l'instance en mémoire fait foi) ; le `delete()` du magasin n'est pas exposé à l'interface |
| 6 | La fenêtre entre la validation synchrone et l'action reste inchangée (même résidualité que sur `/authorize`) | inchangé, documenté dans le rapport A-α/B-α |
| 7 | Aucune validation Debian 13 | environnement indisponible |

---

## 8. Interactions avec les audits Agent B en cours

| Branche en audit | Interaction |
|------------------|-------------|
| **D1** (`3a59dae`) | aucun fichier commun avec le présent correctif (`runner.py` : le hunk touché est `list_missions`, l. ~205-250, distinct de `_ensure_authorization`) → pas de conflit |
| **D2** (`d3240d2`) | aucun fichier commun (`planner.py`) → pas de conflit |
| **D1-bis** (`1ef4878`) | aucun fichier commun avec `store.py` ; sur `runner.py`, le hunk touché est distinct de `check_authorization` → pas de conflit |
| **D3** (`0be08cd`) | aucun fichier commun (`app/tools/*`) → pas de conflit. La base retenue **contient** D3 (donc le correctif D-B01) |
| **A-α/B-α** (`25baa60`) | la base retenue **contient** A-α/B-α ; le hunk touché (`list_missions`) est distinct de `check_answer` et de `answer` → pas de conflit |
| **Audit contradictoire** (`fd25a26`) | ne porte que sur l'arbre Phase 5/6/6.1 ; **confirme D-B01** (cf. §4) ; ne contredit aucun constat |

Le présent correctif est donc **fusionnable sans conflit de code** avec
l'ensemble des branches en cours, mais **ne doit pas être fusionné sans
décision** (les audits ne sont pas terminés).

---

## 9. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-mission-persistence-owner
git pull --ff-only

# D-B05 : propriétaire persisté et liste complète
python -m unittest tests.test_mission_persistence_owner -v

# D-B01 : test de non-régression demandé par l'audit
python -m unittest tests.test_mission_persistence_owner.TestCheminsLegitimesContenantCode -v

# Reproduction de l'audit : dépôt dans un chemin contenant « code »
New-Item -ItemType Directory -Force -Path C:\Temp\opencode | Out-Null
git clone . C:\Temp\opencode\Milescorp
cd C:\Temp\opencode\Milescorp
python -m unittest discover -s tests     # attendu : 0 échec

# non-régression
python -m unittest tests.test_mission_orchestrator tests.test_mission_bounds
python -m unittest discover -s tests
```

---

## 10. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-mission-persistence-owner` (poussée sur `origin`) |
| SHA de base | `25baa60` (`fix/miles-answer-d1ter`) |
| Fichiers modifiés | `app/orchestration/store.py`, `app/orchestration/runner.py` |
| Fichiers ajoutés | `tests/test_mission_persistence_owner.py`, ce rapport |
| `main` | `b9b7e7d` — **inchangée** |
| Intégration | `69bf670` — **inchangée** |
| D1 / D2 / D1-bis / D3 / A-α-B-α | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` / `25baa60` — **inchangées** |
| Branche d'audit | `fd25a26` — **inchangée** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |

---

## 11. Prochaine action

1. **Audit indépendant d'Agent B** de la branche
   `fix/miles-mission-persistence-owner`, portant sur :
   - la correction de la perte du propriétaire (et son impact sur la
     séparation entre utilisateurs) ;
   - la complétude et le filtrage de la liste des missions ;
   - la migration de schéma (idempotence, base existante) ;
   - l'exécution sous Debian 13.
2. **D-B05 — points restants** (`results` non persistés, étape `RUNNING` non
   reprise) : à traiter dans un lot dédié si Agent B le juge utile.
3. **D-B01** : le correctif existe et est vérifié (§4) ; la branche D3 reste
   soumise à audit, et le test demandé par l'audit est désormais présent.
4. **Ne pas fusionner** sans décision explicite.
