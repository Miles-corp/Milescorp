# docs/reports/PHASE_6_3D_D1BIS_AGENT_A.md — Correction D1-bis : réponse HTTP honnête de l'autorisation

- **Auteur** : Agent A
- **Date** : 2026-10-21
- **Dépôt** : `C:\Users\StanC\Desktop\Milescorp` (remote `https://github.com/Miles-corp/Milescorp.git`)
- **SHA de base (vérifié)** : `d3240d2ecce9847cdcc13b49769f482d9c5a1956` (`fix/miles-windows-paths`, qui porte les correctifs D1 `6b736d7` et D2 `d3240d2`)
- **Branche de correction** : `fix/miles-d1bis-authorization-response`
- **`main`** : `b9b7e7d` — **inchangée**
- **Branche auditée par Agent B** : `origin/integration/miles-phases-5-6-6-1` = `69bf670` — **inchangée**
- **Branche D1** : `fix/miles-d1-web-authorization` = `3a59dae` — **inchangée**
- **Branche D2** : `fix/miles-windows-paths` = `d3240d2` — **inchangée** (c'est la base)
- **Défaut corrigé** : D1-bis (rapport de validation Phase 6.3, §4) et sa variante « mission en cours » (§6 ci-dessous)

> **Aucune fusion n'a été effectuée.** Le correctif attend l'audit
> indépendant d'Agent B.

---

## 1. Vérifications préalables

| Vérification | Résultat |
|--------------|----------|
| État Git avant intervention | checkout principal sur `fix/miles-d1-web-authorization`, artefact non suivi `tatus --short--branch` **préservé** |
| SHA de base | `d3240d2ecce9847cdcc13b49769f482d9c5a1956` ✔ (branche D2, qui inclut D1) |
| `origin/fix/miles-d1-web-authorization` | `3a59dae` (ne pas modifier) |
| `origin/fix/miles-windows-paths` | `d3240d2` (ne pas modifier) |
| `origin/main` | `b9b7e7d` (ne pas modifier) |
| `origin/integration/miles-phases-5-6-6-1` | `69bf670` (ne pas modifier) |
| Isolation | **worktree Git dédié** : `C:\Users\StanC\AppData\Local\Temp\miles-d1bis` ; le checkout principal n'a pas été touché |

Branche créée : `git worktree add Temp\miles-d1bis -b fix/miles-d1bis-authorization-response d3240d2`.

---

## 2. Implémentation réelle lue

`app/interface/web.py::WebApp.authorize_mission` (avant correctif) :

```python
approved = bool(data.get("approved", False))
try:
    self._start_mission_thread(
        mission_id,
        lambda mid: self.mission_runner.authorize(...approval_token=approval_token...),
    )
except MissionAuthorizationError as exc:
    return {"error": str(exc)}
return {"mission_id": mission_id, "approved": approved, "started": True}
```

`app/interface/web.py::WebApp._start_mission_thread` lance un **démon** et
exécute l'action **dans le fil** :

```python
def _target() -> None:
    try:
        action(mission_id)
    except Exception:
        logger.error("Erreur interne pendant l'execution de la mission %s.", mission_id)
```

**Cause du défaut D1-bis** : la validation du jeton d'approbation a lieu dans
`MissionRunner.authorize` (l. 416-419 de `runner.py`, comparaison en temps
constant avec `hmac.compare_digest`), donc **dans le fil d'exécution**. Le
`try/except MissionAuthorizationError` placé autour du *démarrage* du fil ne
pouvait donc jamais rien intercepter : l'exception était journalisée (et
absorbée par un `NullHandler`) sans être retournée au client. La réponse
positive était **inconditionnelle**.

Les contrôles que le serveur *pouvait* faire de façon synchrone étaient déjà
corrects : mission inconnue, mission sans demande en attente, propriétaire
différent, jeton absent.

---

## 3. Reproduction (avant correctif), sur le vrai serveur HTTP

Commande : `POST /mission/<id>/authorize` avec un jeton fabriqué, sur le
serveur réel `python miles.py --web` (base isolée, supprimée après) :

```
=== 3. POST /mission/<id>/authorize avec un JETON INVALIDE ===
   CODE HTTP : 200
   CORPS     : {"mission_id": "bb5d348f9f07", "approved": true, "started": true}

=== 4. Etat reel de la mission apres la reponse ===
   etat      : awaiting_authorization
   pending   : authorization
   interactions : 1
   steps_executed : 0
   grants actifs  : 0
```

Constats factuels :

| Élément | Valeur mesurée |
|---------|-----------------|
| Code HTTP | **200** |
| Corps | `{"mission_id": …, "approved": true, "started": true}` |
| État réel de la mission | `awaiting_authorization` (inchangé) |
| Étapes exécutées | **0** |
| Grants émis | **0** |
| Jeton vide / absent | 403 `{"error": "Jeton d'autorisation manquant."}` (déjà correct) |

**La propriété de sécurité n'était pas violée** (aucune élévation de
privilège : aucun grant, aucune étape sensible exécutée) ; c'est la
**réponse HTTP** qui était mensongère : un client automatisé croyait avoir
autorisé la mission.

---

## 4. Correctif

### 4.1 Principe

> La réponse n'est positive que si l'autorisation a **réellement** été
> acceptée : le jeton, l'expiration et la session sont validés de façon
> **synchrone**, avant le lancement du fil.

### 4.2 Fichiers modifiés (2)

**`app/orchestration/runner.py`**

1. `MissionAuthorizationError` porte désormais un attribut `reason` : un code
   de refus **stable et non sensible** (jamais de jeton, de session ni
   d'identifiant d'utilisateur). 8 constantes sont définies à côté :
   `REASON_MISSION_NOT_FOUND`, `REASON_MISSION_FINISHED`,
   `REASON_NO_PENDING_AUTHORIZATION`, `REASON_MISSION_NOT_OWNED`,
   `REASON_MISSING_APPROVAL_TOKEN`, `REASON_INVALID_APPROVAL_TOKEN`,
   `REASON_EXPIRED_APPROVAL_TOKEN`, `REASON_SESSION_MISMATCH`.
2. Nouvelle méthode **`check_authorization(...)`** : elle factorise tous les
   contrôles d'`authorize` **sans accorder l'autorisation**. `authorize()`
   l'appelle désormais (source de vérité unique : aucun risque de divergence
   entre la validation et l'octroi).
3. Contrôle supplémentaire : **la demande doit provenir de la session qui
   porte la mission**. Ce contrôle ne concerne que les missions créées par un
   *client* (une mission créée par l'application, en ligne de commande, n'est
   pas liée à une session cliente) : il est nécessaire car, avec le correctif
   D1, le grant d'autorisation est vérifié avec `mission.session_id` — une
   autorisation venue d'une autre session n'aurait donc jamais pu être
   honorée.

**`app/interface/web.py`**

4. `authorize_mission` : les refus préexistants portent désormais un `reason` ;
   la validation synchrone (`check_authorization`) précède le lancement du
   fil ; un refus renvoie `{"error": …, "reason": …}`.
5. `_start_mission_thread` **renvoie un booléen** : `False` si une autre
   action est déjà en cours pour cette mission (l'action aurait été
   silencieusement ignorée). `authorize_mission` et `answer_mission` traitent
   alors ce cas explicitement (§6).
6. `_handle_mission_authorize` / `_handle_mission_answer` : **409 Conflict**
   pour le cas « mission en cours », **403 Forbidden** pour les autres refus,
   **200** pour la réussite.

### 4.3 Codes HTTP et corps retenus

| Cas | HTTP | Corps |
|-----|------|-------|
| Autorisation acceptée | **200** | `{"mission_id": …, "approved": true, "started": true}` |
| Jeton invalide | **403** | `{"error": "Jeton d'autorisation invalide.", "reason": "invalid_approval_token"}` |
| Jeton expiré | **403** | `{"error": "La demande d'autorisation est expiree.", "reason": "expired_approval_token"}` |
| Jeton d'une autre mission | **403** | `{"error": "Jeton d'autorisation invalide.", "reason": "invalid_approval_token"}` |
| Jeton absent / vide | **403** | `{"error": "Jeton d'autorisation manquant.", "reason": "missing_approval_token"}` |
| Autre session (même utilisateur) | **403** | `{"error": "Cette mission est liee a une autre session.", "reason": "session_mismatch"}` |
| Autre utilisateur | **403** | `{"error": "Cette mission appartient a un autre utilisateur.", "reason": "mission_not_owned"}` |
| Mission déjà terminée | **403** | `{"error": "La mission est deja terminee.", "reason": "mission_finished"}` |
| Aucune autorisation en attente | **403** | `{"error": "Aucune autorisation en attente pour cette mission.", "reason": "no_pending_authorization"}` |
| Mission inconnue | **403** | `{"error": "Mission inconnue : …", "reason": "mission_not_found"}` |
| Mission encore en cours de traitement | **409** | `{"error": "La mission est encore en cours de traitement : …", "reason": "mission_busy"}` |

**Choix de 403 pour les refus d'autorisation** : cohérent avec la convention
déjà appliquée à cette route (`403` pour « mission d'un autre utilisateur »,
« CSRF invalide ») et avec les attentes des tests d'audit d'Agent B
(`test_autorisation_sans_csrf_refusee`, `test_7_utilisateur_a_ne_peut_pas_...`
attendent 403). **409** est réservé au cas « action non appliquée, à
réessayer » : la ressource existe et l'état du client entre en conflit avec
l'état courant de la mission.

**Aucune information divulguée** : les messages ne contiennent ni le jeton
d'approbation, ni l'identifiant de session, ni le jeton CSRF, ni
d'identifiant d'utilisateur. Les codes `reason` sont des énumérations stables
et non sensibles.

---

## 5. Tests

Fichier nouveau : `tests/test_mission_authorize_response.py` (**20 tests**).

| # | Exigence de la mission | Test | Résultat |
|---|------------------------|------|----------|
| 1 | Autorisation valide | `test_autorisation_valide_acceptee` (la mission va jusqu'à `completed`) · `test_autorisation_valide_refus_explicite_du_client` · `test_jeton_valide_repond_200` | ✅ |
| 2 | Jeton invalide | `test_jeton_invalide_refuse_avec_raison_explicite` · `test_jeton_invalide_n_accorde_aucune_autorisation` (propriété de sécurité) · `test_jeton_invalide_repond_403` | ✅ |
| 3 | Jeton expiré | `test_jeton_expire_refuse_avec_raison_explicite` · `test_jeton_expire_repond_403` | ✅ |
| 4 | Autre session | `test_autre_session_refusee_avec_raison_explicite` · `test_autre_utilisateur_refuse_avec_raison_explicite` | ✅ |
| 5 | Mission déjà terminée | `test_mission_deja_terminee_refusee` · `test_mission_terminee_repond_403` · `test_mission_inconnue_refusee` · `test_autorisation_non_en_attente_refusee` | ✅ |
| 6 | Aucune divulgation | `test_les_erreurs_ne_divulguent_ni_jeton_ni_session` · `test_les_reponses_erreur_ne_divulguent_pas_de_jeton` | ✅ |
| 7 | Jeton d'une autre mission | `test_jeton_dune_autre_mission_refuse` | ✅ |
| 8 | Jeton absent | `test_jeton_absent_refuse` (None, "", 123) | ✅ |
| 9 | Mission en cours (§6) | `test_mission_en_cours_refuse_le_lancement_de_laction` · `test_mission_en_cours_repond_409` | ✅ |

Les tests couvrent **les deux niveaux** : appel direct de
`WebApp.authorize_mission` et **vraies requêtes HTTP** (serveur local,
`WebTestServer`).

### 5.1 Le test échoue-t-il avant le correctif ?

Vérifié explicitement (`git stash push app/interface/web.py`, puis restauré) :

```
sans le correctif web : Ran 20 tests — FAILED (failures=15)
avec le correctif     : Ran 20 tests — OK
```

Les 15 échecs portent sur les refus explicites (jeton invalide, expiré, autre
session, mission terminée, mission inconnue, pas d'autorisation en attente) et
sur la divulgation. Les 5 tests qui passent dans les deux cas vérifient des
propriétés déjà correctes (l'autorisation valide fonctionne, la propriété de
sécurité « rien n'est accordé »).

### 5.2 Commandes et résultats exacts

| Commande | Résultat |
|----------|----------|
| `python -m unittest tests.test_mission_authorize_response` | **20 tests, 0 échec** (9,5 s) |
| `python -m unittest tests.test_mission_authorize_response` *(sans le correctif web)* | **15 échecs** |
| `python -m unittest tests.test_mission_web_authorization` (D1) | **6 tests, 0 échec** |
| `python -m unittest tests.test_web_security_phase6_1` | **35 tests, 0 échec** |
| `python -m unittest tests.test_mission_orchestrator` | **73 tests, 0 échec** |
| `python -m unittest tests.test_mission_bounds` | **20 tests, 0 échec** |
| `python -m unittest tests.test_web_security` | **33 tests, 0 échec** |
| `python -m unittest tests.test_windows_paths` (D2) | **21 tests, 0 échec** |
| `python -m unittest discover -s tests` | **575 tests, 0 échec, 4 ignorés** (101,5 s) |
| Tests d'audit d'Agent B (rejoués tels quels) | **70 tests, 0 échec, 2 ignorés** (25,3 s) |

Les 4 + 2 tests ignorés sont des **limites de plateforme Windows** (3 liens
symboliques, 1 `/proc/self/fd`, 2 liens symboliques d'audit) ; ils
s'exécutent sous Debian 13.

> Le test d'audit d'Agent B qui **inspecte le code source** de
> `WebApp.authorize_mission` (`test_autorisation_de_mission_exige_identite_et_jeton`
> — il exige la présence de `session`, `owner_user_id` et `approval_token`)
> reste **vert** : les trois éléments sont conservés dans la méthode.

---

## 6. Variante du même défaut : « mission en cours de traitement » (nouvelle)

En vérifiant le correctif sur le **vrai serveur**, un second cas de réponse
positive mensongère a été trouvé — **préexistant** (présent à l'identique
sur les branches D1 et D2, sans le correctif D1-bis).

**Mécanisme** : `WebApp._start_mission_thread` ignore l'action demandée si un
fil est déjà vivant pour cette mission (« une mission déjà en cours
d'exécution n'est pas relancée »). Or le fil de la mission **reste vivant**
après avoir levé la demande d'autorisation : il termine son travail en
construisant le rapport, ce qui **appelle le fournisseur IA** (jusqu'à une
dizaine de secondes). Une autorisation reçue pendant cette fenêtre était
donc **silencieusement perdue**, et la réponse HTTP annonçait malgré tout
`"approved": true, "started": true`.

**Preuve** (serveur réel, même mission, seule la temporisation change) :

```
sans attendre :   HTTP 200 {"approved": true}   -> mission figée, s2 'pending'
après 20 s :      HTTP 200 {"approved": true}   -> s2, s3 'succeeded', la mission avance
```

**Correctif appliqué** : `_start_mission_thread` renvoie désormais `False`
quand l'action est ignorée ; l'interface web répond alors
**409 `mission_busy`** (« la mission est encore en cours de traitement,
l'autorisation n'a pas été appliquée, réessayez ») au lieu d'un faux succès.
Le client peut réessayer : le jeton est toujours valide et la demande en
attente n'a pas été consommée.

**Vérification sur le vrai serveur** (avec réessai) :

```
=== 2. JETON INVALIDE ===
   HTTP 403 | {"error": "Jeton d'autorisation invalide.", "reason": "invalid_approval_token"}
=== 3. JETON VALIDE (avec reessai si 409) ===
   essai 1 : HTTP 409 | {"error": "La mission est encore en cours de traitement : …", "reason": "mission_busy"}
   essai 2 : HTTP 409 | {"error": "La mission est encore en cours de traitement : …", "reason": "mission_busy"}
   essai 3 : HTTP 200 | {"mission_id": "e470e2107b33", "approved": true, "started": true}
=== 4. Etat final ===
   etat : completed | motif : completed
=== 5. Re-autorisation d'une mission terminee ===
   HTTP 403 | {"error": "La mission est deja terminee.", "reason": "mission_finished"}
```

### 6.1 Cause racine — **proposée, NON appliquée** (hors périmètre)

`app/orchestration/report.py::ReportBuilder.build` appelle **toujours** la
fonction d'analyse, y compris pour une mission **en attente** : le fil de la
mission reste donc occupé le temps de l'appel au fournisseur IA, et la
fenêtre « mission occupée » est ouverte.

Correctif proposé (une ligne, à valider par Agent B — il change le contenu
du rapport des missions en attente) :

```python
# app/orchestration/runner.py::_execute_loop
analyste = self._analyze if mission.state.is_terminal else None
mission.report = self._report_builder.build(mission, analyste)
```

Effet attendu : le fil se termine dès la demande d'autorisation, la fenêtre
« mission occupée » disparaît, et le client n'a plus à réessayer.

**Non appliqué ici** : ce correctif touche l'orchestrateur et la sémantique du
compte rendu (une mission en attente n'aurait plus de section « Analyse
qualitative »), ce qui dépasse le périmètre de D1-bis. Il est soumis à
Agent B avec la mesure ci-dessus.

### 6.2 Point de vigilance pour l'interface web

Le client doit **réessayer** sur `409`. Le guide utilisateur (§5.2) le
mentionne ; le tableau de correspondance des codes est documenté dans le
rapport ci-dessus.

---

## 7. Limites et risques résiduels

| Limite | Statut |
|--------|--------|
| `POST /mission/<id>/answer` répond aussi honnêtement (409) | corrigé dans le même lot (même cause) |
| `POST /mission` (création) : le garde « mission déjà en cours » reste un refus silencieux du fil | non modifié : le contrôle `find_running` couvre le cas réaliste (double clic) et la mission existe en base, reprenable via `/mission-resume`. **À signaler** si Agent B le juge insuffisant. |
| Le jeton d'approbation peut être contourné par le **propriétaire** via `/mission/<id>/answer` (réponse « o ») | comportement préexistant : le chemin `/answer` utilise le jeton de la demande en attente. Ce n'est pas une élévation de privilège (le propriétaire peut de toute façon approuver via `/authorize`), mais le jeton n'est pas un second facteur indépendant. **Non modifié** (hors périmètre). |
| Fenêtre « mission occupée » de quelques secondes | décrite §6 ; correctif racine proposé, non appliqué |
| Aucune validation sous Debian 13 | environnement indisponible ; les 6 tests ignorés sont des limites Windows |
| Le correctif D1 reste intact | oui : `tests.test_mission_web_authorization` (6 tests) est vert, et `_ensure_authorization` n'a pas été touché |

---

## 8. Vérification manuelle (reproductible)

```powershell
cd C:\Users\StanC\Desktop\Milescorp
git fetch origin
git checkout fix/miles-d1bis-authorization-response
git pull --ff-only

$env:MILES_WEB_AUTH_TOKEN = "jeton-de-validation"
$env:MILES_REMOTE_TIMEOUT = "1"
$env:MILES_MISSION_DB_PATH = "data/validation-d1bis.db"
$env:MILES_CONVERSATION_DB_PATH = "data/validation-d1bis-conv.db"
python miles.py --web --web-port 8141

# dans un autre terminal :
curl.exe -X POST http://127.0.0.1:8141/session -H "Content-Type: application/json" `
  -d "{\"token\":\"jeton-de-validation\"}"
# puis, avec les en-tetes de session et de CSRF :
#   1. POST /mission                    {"objective":"Analyse docs/"}
#   2. POST /mission/<id>/authorize     {"approved":true,"approval_token":"JETON_FABRIQUE"}
#      attendu : HTTP 403 {"error":"Jeton d'autorisation invalide.","reason":"invalid_approval_token"}
#   3. POST /mission/<id>/authorize     {"approved":true,"approval_token":"<jeton_valide>"}
#      attendu : HTTP 409 {"reason":"mission_busy"} puis HTTP 200 apres reessai
#      attendu : la mission aboutit a « completed »
```

---

## 9. État Git

| Élément | Valeur |
|---------|--------|
| Branche | `fix/miles-d1bis-authorization-response` (poussée sur `origin`) |
| SHA de base | `d3240d2` (branche D2, inclut D1) |
| Fichiers modifiés | `app/interface/web.py`, `app/orchestration/runner.py` |
| Fichiers ajoutés | `tests/test_mission_authorize_response.py`, ce rapport, le rapport D3 |
| `main` | `b9b7e7d` — **inchangée** |
| Branche auditée par Agent B | `69bf670` — **inchangée** |
| Branche D1 | `3a59dae` — **inchangée** |
| Branche D2 | `d3240d2` — **inchangée** (base) |
| Artefact non suivi | `tatus --short--branch` — **préservé, hors du commit** |

**Conflits avec l'audit D1 en cours ?** Aucun conflit de code : D1-bis touche
`app/interface/web.py` et `app/orchestration/runner.py` (méthode
`check_authorization`, nouvelle) ; le correctif D1 avait touché
`runner.py::_ensure_authorization` (l. ~853-868) — **hunks distincts**, donc
fusion sans conflit. Seule entorse : le guide utilisateur est modifié par les
trois branches → résolution manuelle des lignes §1, §3, §5.2, §6 et §7.1 à la
fusion (contexte, pas de contenu contradictoire).

---

## 10. Prochaine action

1. **Audit indépendant par Agent B** du commit de correction D1-bis :
   - la validation est-elle réellement synchrone et sans effet de bord ?
   - les codes HTTP et les corps sont-ils explicites et non divulguants ?
   - le contrôle de session (`session_mismatch`) est-il correctement borné aux
     missions créées par un client ?
   - la variante « mission en cours » (409) est-elle acceptable, et le
     correctif racine proposé (§6.1) doit-il être appliqué ?
2. **Ne pas fusionner** avant cet audit.
