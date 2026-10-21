# docs/reports/PHASE_6_3G_INVESTIGATION_D1TER_ANSWER_AGENT_A.md — Investigation D1-ter et parcours `/answer`

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Nature** : **INVESTIGATION** — **aucune modification du code de production**
- **Branche d'investigation** : `investigation/d1ter-and-answer-path` (tests d'observation et rapport uniquement)
- **Base examinée** : `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` (`fix/miles-policy-path-typing`, qui porte D1 + D2 + D1-bis + D3)
- **Comparaison** : `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` (`fix/miles-d1-web-authorization`, sans D1-bis)

> Ce rapport **ne corrige rien**. Les correctifs minimaux sont décrits au §6
> et soumis à l'arbitrage d'Agent B. Les tests ajoutés sont **descriptifs** :
> ils fixent le comportement observé, y compris ses écarts, et serviront de
> base de régression si un correctif est décidé.

---

## 1. Préalables Git

| Référence annoncée | SHA annoncé | SHA réel vérifié | Conforme |
|--------------------|--------------|------------------|----------|
| D1 `fix/miles-d1-web-authorization` | `3a59dae` | `3a59daebf74bf63fd173ccda2b8b8372c4d51a6e` | ✔ |
| D2 `fix/miles-windows-paths` | `d3240d2` | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` | ✔ |
| D1-bis `fix/miles-d1bis-authorization-response` | `1ef4878` | `1ef48780ea8548f44db33bfc9e4c9fbc911e286f` | ✔ |
| D3 `fix/miles-policy-path-typing` | `0be08cd` | `0be08cd5bb0a70eac3d165a605fc79ec72bb0e4f` | ✔ |
| `main` | `b9b7e7d` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | ✔ |
| Intégration | `69bf670` | `69bf67060cdbc6155cb632fba92d7a1c13a9262d` | ✔ |

**Base retenue** : `0be08cd` (tête la plus récente). Les deux risques
étudiés concernent `app/interface/web.py` et `app/orchestration/runner.py`,
qui sont **identiques** sur `1ef4878` et `0be08cd` (vérification par
empreinte d'objet) : les conclusions valent pour D1-bis comme pour D3.

**Isolation** : worktree dédié
`C:\Users\StanC\AppData\Local\Temp\miles-invest` ; aucune branche existante
modifiée, aucune fusion ; le checkout principal, son artefact non suivi
`tatus --short--branch` et les bases du développeur sont intacts.

---

## 2. Risque A — le parcours `/answer`

### 2.1 Chaîne d'exécution relevée

```
POST /mission/<id>/answer
  └─ WebApp.answer_mission (web.py)          : mission existante + proprietaire + réponse non vide
     └─ _start_mission_thread(...)            : l'action part dans un FIL
        └─ MissionRunner.answer (runner.py:298)
           ├─ contrôle du propriétaire (requester_user_id)
           ├─ contrôle du budget d'interactions
           └─ si pending.kind == "authorization" :
              approved = texte in ("o", "oui", "y", "yes", "ok", "autorise")
              └─ MissionRunner.authorize(..., approval_token=mission.pending.approval_token)
                 └─ check_authorization : contrôle le jeton, l'expiration, la session
```

**Point clé** : `MissionRunner.answer` utilise **en interne** le jeton de la
demande en attente (`approval_token=mission.pending.approval_token`). Le
client n'a donc **pas** à présenter de jeton pour approuver par `/answer`,
alors que `/authorize` l'exige.

### 2.2 A-1 — Une mission peut être approuvée sans jeton valide

**Constat (mesuré)** : `POST /mission/<id>/answer` avec le corps
`{"answer": "o"}` approuve la mission **sans aucun jeton** : le grant est
émis, les étapes s'exécutent, la mission aboutit.

```
=== A1 : /answer avec « o » approuve SANS jeton d'approbation ===
   reponse   : {'mission_id': ..., 'answered': True, 'started': True}
   etat final: completed
   budget    : 2 étapes, 2 appels d'outils, 1 échange
   grants    : 1
```

**Asymétrie mesurée entre les deux routes** (même mission) :

| Route | Jeton exigé ? | Résultat |
|-------|---------------|----------|
| `POST /mission/<id>/authorize` | **oui** | sans jeton → `403 missing_approval_token` |
| `POST /mission/<id>/answer` | **non** | sans jeton → **approuvé** |

**Interprétation** : le jeton d'approbation (correction P1-6-06 de la
Phase 6.1) lie la décision à **une demande précise** (mission, périmètre,
expiration). Il n'a jamais été un second facteur *contre le propriétaire* de
la mission : le client reçoit le jeton dans la charge utile de la mission et
peut donc approuver avec `/authorize`. Le propriétaire qui utilise `/answer`
contourne simplement la présentation du jeton.

**Gravité : MINEURE.** Ce n'est **pas** une élévation de privilège : le
propriétaire est le seul à pouvoir approuver, et il le pourrait de toute
façon. C'est une **incohérence entre deux routes** et un affaiblissement
d'une défense en profondeur (le jeton n'est pas vérifié sur ce chemin).

### 2.3 A-2 — La réponse de `/answer` est une réponse positive mensongère

**Constat (mesuré)** : lorsqu'une action échoue **dans le fil**
(refus de session, budget d'interactions épuisé), l'exception est absorbée
par le fil et la route répond malgré tout `{"answered": true}`.

C'est **exactement la famille de D1-bis**, mais sur la route `/answer` : le
correctif D1-bis n'a traité que `/authorize`.

```
=== A4 : /answer depuis une AUTRE session (même utilisateur) ===
   reponse : {'mission_id': ..., 'answered': True, 'started': True}   <- mensonger
   etat de la mission : awaiting_authorization                        <- refus réel
   grants emis        : 0
```

**Gravité : MINEURE.** L'action est réellement refusée (aucun grant, aucune
étape sensible) ; c'est la **réponse** qui ment. Un client automatisé peut
croire avoir répondu.

### 2.4 A-3 — Une autre session peut-elle affecter la mission ?

Comparaison **mesurée** entre les deux bases :

| Base | Réponse | Grant émis | Étapes | Interactions | État |
|------|---------|------------|--------|--------------|------|
| D1 (`3a59dae`, sans D1-bis) | `answered: true` | **1** (inutilisable) | 0 | **1 → 2** | `awaiting_authorization` |
| D3 (`0be08cd`, avec D1-bis) | `answered: true` | **0** | 0 | 1 (inchangé) | `awaiting_authorization` |

Sur la base **D1**, l'approbation venue d'une autre session :

- émettait un grant lié à la session de l'autre client, donc **inutilisable**
  (le grant est vérifié avec la session de la mission) ;
- **consommait un échange** du budget d'interactions : la mission redemandait
  une autorisation, et le cycle pouvait aller jusqu'à l'épuisement du budget
  (`interaction_budget_exceeded`), c'est-à-dire une mission **bloquée**.

Sur la base **D3**, le contrôle de session ajouté par D1-bis
(`check_authorization`) empêche l'émission du grant et ne consomme pas
d'échange : le risque est **atténué** (mais la réponse reste mensongère,
cf. A-2).

Un **autre utilisateur** ne peut rien faire : la mission lui est invisible
(`mission_detail` → « Mission inconnue ») et `/answer` est refusé ✓.

### 2.5 Comportement CLI vs Web

Le CLI (`app/interface/cli.py::_drive_mission`) n'appelle pas `answer` pour
une autorisation : il appelle directement
`runner.authorize(..., approval_token=pending.approval_token)` — c'est-à-dire
**le même mécanisme interne** (le jeton de la demande en attente). Le
comportement est donc **cohérent** entre CLI et web : dans les deux cas,
l'approbation ne passe pas par une présentation de jeton par le client.

La différence est l'**exposition** : la CLI est une console locale à une
seule session ; le web est multi-clients, où la session et le propriétaire
sont vérifiés. Le contrôle de session de D1-bis ne s'applique qu'au web
(la CLI utilise la session de l'application).

### 2.6 Synthèse du risque A

| # | Constat | Élévation de privilège ? | Gravité |
|---|---------|--------------------------|---------|
| A-1 | `/answer` approuve sans présenter le jeton | **Non** (le propriétaire peut de toute façon approuver) | **Mineure** (incohérence + défense en profondeur affaiblie) |
| A-2 | `/answer` répond « answered: true » alors que l'action a échoué | **Non** (l'action est refusée) | **Mineure** (réponse mensongère, famille D1-bis) |
| A-3 | Sur la base D1 : approbation cross-session → grant inutilisable + échange consommé | **Non** | **Mineure** (atténuée sur D3 par le contrôle de session) |

**Conclusion : le risque A n'est pas exploitable pour obtenir un accès non
autorisé.** Il porte sur la *cohérence* et sur la *qualité de la réponse*.

---

## 3. Risque B — D1-ter : l'autorisation reçue pendant la génération du rapport

### 3.1 États et transitions

```
created ──run()──► running ──étape sensible──► awaiting_authorization
   ▲                    │                                │
   │                    └─étape LOW : fait observé      │ /authorize (jeton valide)
   │                                                     │   ou /answer
   │                                    409 mission_busy │   (fenêtre)
   │                                                     ▼
   └──────────── reprise ◄── running ◄── grant émis ── completed / partial
```

| État | Signification | Sortie possible |
|-------|---------------|------------------|
| `created` | mission créée, plan à construire | `running`, `needs_clarification` |
| `running` | exécution en cours | `awaiting_authorization`, `completed`, `partial`, `failed`, `limit_reached` |
| `awaiting_authorization` | **une demande d'autorisation est en attente** (`mission.pending`) | `running` (autorisation accordée), `failed` (refus), `limit_reached` (budget) |
| `completed` / `partial` / `failed` / `cancelled` / `limit_reached` | états terminaux (`is_terminal`) | — |

### 3.2 Pourquoi la demande d'autorisation est ignorée

`WebApp._start_mission_thread` refuse de lancer une action si un fil est
déjà vivant pour cette mission (« une mission déjà en cours d'exécution n'est
pas relancée ») :

```python
existing = self._mission_threads.get(mission_id)
if existing is not None and existing.is_alive():
    return False      # <- l'action est IGNORÉE
```

Or le fil de la mission **reste vivant après avoir levé la demande
d'autorisation** : il termine son travail en construisant le compte rendu
(`runner.py::_execute_loop`, l. 832-836), et cette construction **demande
l'analyse qualitative au fournisseur IA** — y compris pour une mission qui
attend encore.

**Cause racine reproduite de façon déterministe** (fournisseur **simulé**,
aucun appel réseau, aucun coût) :

```
=== B3 : la mission en attente demande-t-elle une analyse ? ===
   etat      : awaiting_authorization
   faits     : ["Résultat de l'étape s1 : 2 caractère(s)."]
   appels au fournisseur : 2
      - Tu proposes un plan d'observation pour MILES. …
      - Tu analyses les faits observés par une mission MILES. …   <- l'analyse
   rapport contient 'Analyse qualitative' : True
```

La fenêtre dure donc le temps de l'appel au fournisseur (jusqu'à une
dizaine de secondes, cf. D4). Pendant cette fenêtre, toute autorisation
reçue est **ignorée**.

### 3.3 Le 409 reflète-t-il un état temporaire ou définitif ?

**Temporaire** — démontré par `B2`/`B5` : dès que le fil se termine, le
**réessai** de la même requête réussit (HTTP 200) et la mission aboutit.

| Propriété | Mesuré |
|-----------|--------|
| Le 409 est-il définitif ? | **Non** — le réessai réussit après la fenêtre |
| Le jeton est-il consommé par l.Authorization ignorée ? | **Non** — `pending.approval_token` est inchangé, la demande en attente est intacte |
| Le budget d'interactions est-il consommé ? | **Non** — `interactions` reste à 1 |
| Des étapes sont-elles rejouées ? | **Non** — `steps_executed == 2`, `tool_calls == 2` après le réessai (aucune double exécution) |
| La mission reste-t-elle cohérente ? | **Oui** — elle reprend exactement où elle s'était arrêtée |

### 3.4 Une mission bloquée ou une nouvelle exécution indue ?

- **Sans réessai du client** : la mission reste en `awaiting_authorization`.
  Le budget d'interactions n'étant pas consommé, elle attend **indéfiniment**
  (elle n'est ni en échec, ni en `limit_reached`) → c'est une **attente sans
  issue** pour l'utilisateur, pas un blocage du service. C'est le coût réel du
  défaut.
- **Avec réessai** : la mission se termine normalement ✓ (mesuré).
- **Nouvelle exécution indue** : **non** — le réessai ne rejoue aucune étape
  déjà exécutée (B4) et n'émet qu'un seul grant.

### 3.5 Synthèse du risque B

| # | Constat | Élévation de privilège ? | Gravité |
|---|---------|--------------------------|---------|
| B-1 | L'autorisation reçue pendant la génération du rapport est ignorée | **Non** (aucun accès obtenu ; la réponse 409 est honnête) | **Mineure** — mais l'attente sans issue est un coût utilisateur réel |
| B-2 | La cause racine : le compte rendu (et l'analyse IA) est construit pour une mission **en attente** | — | Cause à traiter (1 ligne) |

---

## 4. Tests d'observation livrés

`tests/test_investigation_d1ter_answer_path.py` — **13 tests**, non
destructifs (outils simulés, répertoires temporaires, aucun fournisseur
distant, aucune donnée réelle).

| # | Test | Ce qu'il fixe |
|---|------|----------------|
| A1 | `test_answer_approuve_sans_jeton` | l'approbation sans jeton fonctionne (constat) |
| A2 | `test_answer_refuse_sans_jeton_arrete_la_mission` | une réponse non-approbative arrête la mission |
| A3 | `test_les_deux_parcours_ont_un_comportement_different` | l'asymétrie `/authorize` (jeton exigé) vs `/answer` (jeton non exigé) |
| A4 | `test_answer_depuis_une_autre_session_refuse_effectivement` | l'action est refusée (0 grant) **mais** la réponse ment |
| A5 | `test_answer_par_un_autre_utilisateur_refuse` | un autre utilisateur ne voit pas la mission |
| A6 | `test_answer_repond_a_une_clarification` | l'usage légitime de `/answer` fonctionne |
| A7 | `test_le_grant_emis_par_answer_est_lie_a_la_session` | le grant n'est pas plus permissif qu'un grant obtenu par `/authorize` |
| B1 | `test_autorisation_ignoree_pendant_la_fenetre` | l'autorisation est ignorée, le jeton et la demande restent intacts, le budget n'est pas consommé |
| B2 | `test_reessai_apres_la_fenetre_reussit` | le 409 est temporaire, le réessai réussit, pas de double exécution |
| B3 | `test_le_rapport_demande_une_analyse_pendant_l_attente` | **cause racine** : l'analyse IA est demandée pendant l'attente (fournisseur simulé) |
| B3b | `test_le_rapport_interroge_le_fournisseur_meme_en_attente` | le compte rendu d'une mission en attente contient la section d'analyse |
| B4 | `test_le_reessai_ne_rexecute_pas_les_etapes_faites` | aucune étape rejouée |
| B5 | `test_le_409_est_bien_un_conflit_temporaire` | au niveau HTTP : 409 puis 200 après la fenêtre |

**Ces tests décrivent le comportement actuel.** Ils échoueront si un
correctif est appliqué (c'est voulu : ils jouent le rôle de tests de
régression à inverser au moment du correctif).

---

## 5. Commandes, résultats et limites

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_investigation_d1ter_answer_path` | **13 tests, 0 échec** (5,0 s) |
| `python -m unittest tests.test_web_security_phase6_1` | 35 tests, 0 échec |
| `python -m unittest tests.test_web_security` | 33 tests, 0 échec |
| `python -m unittest tests.test_mission_authorize_response` (D1-bis) | 20 tests, 0 échec |
| `python -m unittest tests.test_mission_web_authorization` (D1) | 6 tests, 0 échec |
| `python -m unittest tests.test_mission_orchestrator` | 73 tests, 0 échec |
| `python -m unittest tests.test_mission_bounds` | 20 tests, 0 échec |
| `python -m unittest tests.test_tool_policy` | 11 tests, 0 échec |
| `python -m unittest tests.test_path_security` | 21 tests, 0 échec, 3 ignorés |
| `python -m unittest discover -s tests` | **628 tests, 0 échec, 4 ignorés** (96,4 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (28,2 s) |

**Limites d'environnement** :

- aucune validation sous **Debian 13** (environnement indisponible) ;
- les 4 + 2 + 3 tests ignorés sont des **limites de plateforme Windows**
  (liens symboliques, `/proc/self/fd`) ;
- **aucun appel API payant** : le fournisseur est simulé dans le test de la
  cause racine ; aucun appel réseau dans l'ensemble de l'investigation ;
- **aucune donnée réelle** lue ou écrite : seuls des outils de test
  simulés et des répertoires temporaires (supprimés par `addCleanup`) ;
- la durée réelle de la fenêtre D1-ter **en production** n'a pas été mesurée
  (elle dépend du délai du fournisseur, cf. D4) ; la cause racine est en
  revanche reproduite de façon déterministe.

---

## 6. Correctifs minimaux proposés (NON APPLIQUÉS)

### 6.1 Risque A

| Option | Correctif | Volume | Effet | Appréciation |
|--------|-----------|--------|-------|--------------|
| **A-α** | Rendre la réponse de `/answer` **honnête** : valider **synchroniquement** (comme D1-bis sur `/authorize`) la demande en attente avant de lancer le fil ; renvoyer `403` + `reason` en cas de refus (session, budget, mission terminée) | `app/interface/web.py` : ~15 lignes, même mécanisme que `authorize_mission` | corrige **A-2** (la réponse mensongère) | **Recommandé** — même correctif que D1-bis, même schéma de code, risque minimal |
| **A-β** | Exiger le jeton d'approbation sur `/answer` quand la demande en attente est une autorisation | `app/interface/web.py` + `app/orchestration/runner.py` (~10 lignes) ; le client web doit envoyer `approval_token` | corrige **A-1** (asymétrie) | À arbitrer : le jeton n'est pas un second facteur contre le propriétaire ; l'exiger change le contrat de l'API web |
| **A-γ** | Documenter `/answer` comme un chemin d'approbation « de convenance » (le propriétaire, pas un tiers) | documentation seule | clarifie A-1 | Recommandé **en complément** de A-α |

**Proposition d'Agent A : A-α + A-γ.** A-β relève d'un choix de contrat
d'API (à trancher par Agent B).

### 6.2 Risque B

| Option | Correctif | Volume | Effet | Appréciation |
|--------|-----------|--------|-------|--------------|
| **B-α** | **Ne pas demander l'analyse qualitative tant que la mission n'est pas dans un état terminal** : `analyste = self._analyze if mission.state.is_terminal else None` | `app/orchestration/runner.py` : **1 ligne** | **supprime la fenêtre** (le fil se termine dès la demande d'autorisation) ; le compte rendu final (mission terminée) conserve l'analyse | **Recommandé** — minimal ; effet secondaire assumé : le compte rendu d'une mission **en attente** n'a plus de section « Analyse qualitative » (c'est le rapport *provisoire* ; le rapport *définitif*, produit à la fin, l'a) |
| **B-β** | Attendre (join borné) la fin du fil avant de lancer l'action | `app/interface/web.py` : ~8 lignes | la requête HTTP est bloquée pendant la fenêtre (jusqu'à ~15 s) | moins bon : latence utilisateur |
| **B-γ** | Sérialiser les actions par mission (file d'attente) | refonte du fil d'exécution | plus robuste | hors proportion |
| **B-δ** | Laisser le 409 tel quel (déjà honnête) | rien | le client doit réessayer | **à conserver comme filet de sécurité** dans tous les cas |

**Proposition d'Agent A : B-α (+ conserver le 409 comme filet).**

### 6.3 Tests de régression à ajouter avec les correctifs

Si A-α est retenu : `test_answer_refuse_une_requete_refusee` (réponse
explicite), `test_answer_session_mismatch_refuse`, `test_answer_budget_epuise_refuse`.
Si A-β est retenu : `test_answer_sans_jeton_refuse` (l'inverse du test A1
actuel).
Si B-α est retenu : `test_pas_d_analyse_pour_une_mission_en_attente`
(l'inverse du test B3 actuel) et `test_autorisation_acceptee_sans_fenetre`
(aucun 409 nécessaire).

---

## 7. Risques résiduels

| # | Risque | Statut |
|---|--------|--------|
| 1 | Le 409 reste possible si une autre action est en cours pour la mission (même cause, autre manifestation) | le client doit réessayer ; le filet reste nécessaire |
| 2 | Après A-α, `/answer` refusera proprement au lieu de mentir, mais le propriétaire pourra toujours approuver sans jeton (sauf si A-β est retenu) | arbitrage Agent B |
| 3 | La fenêtre D1-ter survit tant que B-α n'est pas appliqué (elle se reproduit avec tout fournisseur dont l'appel dure) | signalée |
| 4 | Sur la base D1 (non D1-bis), l'approbation cross-session consomme un échange et peut mener à `interaction_budget_exceeded` | **atténué** par D1-bis (base de l'investigation) ; à vérifier que la fusion conserve ce contrôle |
| 5 | Le jeton d'approbation reste contournable par le propriétaire via `/answer` (A-1) | documenté ; arbitrage A-β |
| 6 | Le mécanisme de fil de `WebApp` reste « une mission = une action à la fois » : toute nouvelle route d'action hätte le même piège | à garder en tête |

---

## 8. Recommandation explicite pour Agent B

1. **Ne pas traiter le risque A comme une vulnérabilité d'accès** : aucune
   élévation de privilège n'a été démontrée ; le propriétaire est le seul à
   pouvoir agir, et il le peut légitimement. Le signalement porte sur la
   **cohérence des réponses** et sur une **défense en profondeur affaiblie**.
2. **Appliquer A-α** (réponse honnête sur `/answer`, même mécanisme que
   D1-bis) : c'est le seul correctif qui supprime une réponse mensongère
   sans changer le contrat de l'API. Décider ensuite de A-β (exiger le
   jeton) : c'est un choix de contrat, pas un correctif de sécurité.
3. **Appliquer B-α** (1 ligne) : la fenêtre D1-ter n'a aucune raison
   d'exister, et le 409 doit rester comme filet de sécurité.
4. **Ne pas modifier la politique D3** dans ce lot : les deux risques
   étudiés sont hors de son périmètre.
5. **Ne pas traiter D4** dans ce lot.
6. **Vérifier la fusion** : la correction D1-bis (contrôle de session) est ce
   qui atténue A-3 ; s'il était écarté, l'impact de A-3 reviendrait (grant
   inutilisable + échange consommé).
7. **Ordre de fusion suggéré** : D1 → D2 → D1-bis → D3, puis A-α et B-α
   (qui dépendent de D1-bis pour le contrôle de session).

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `investigation/d1ter-and-answer-path` (poussée sur `origin`) |
| Base | `0be08cd` (`fix/miles-policy-path-typing`) |
| Fichiers modifiés | **aucun fichier de production** |
| Fichiers ajoutés | `tests/test_investigation_d1ter_answer_path.py` (tests d'observation), ce rapport |
| `main` | `b9b7e7d` — **inchangée** |
| Intégration | `69bf670` — **inchangée** |
| D1 / D2 / D1-bis / D3 | `3a59dae` / `d3240d2` / `1ef4878` / `0be08cd` — **inchangées** |
| Artefact non suivi du checkout principal | `tatus --short--branch` — **préservé** |
