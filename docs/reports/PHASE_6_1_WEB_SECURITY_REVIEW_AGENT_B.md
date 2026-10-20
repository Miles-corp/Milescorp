# docs/reports/PHASE_6_1_WEB_SECURITY_REVIEW_AGENT_B.md — Réaudit Phase 6.1 : sécurité web (Agent B)

> **Réaudit du commit `c0cb01b` (corrections P1-6-03 et P1-6-06 publiées par Agent A).**
> Complémentaire à `docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_B_AUDIT.md` (révision 2, sur `0754032`).

## 1. Verdict

# VALIDÉ SOUS RÉSERVES

**Les deux P1 de sécurité web sont corrigés et le sont pour de bonnes raisons** : j'ai rejoué les attaques de la révision 2 et **aucune n'aboutit**, et j'ai vérifié à chaque fois l'**absence d'effet de bord**, pas seulement le code HTTP.

**Réserve principale : la validation Debian 13 n'a pas pu être rejouée** — la VM était injoignable pendant cette session (port 2222 fermé, `TcpTestSucceeded : False`). Les tests spécifiques à Linux (liens symboliques, fuite de descripteurs) restent donc à confirmer sur la VM. **Réserve secondaire :** la session web reste un jeton porteur (détournement de session si le `session_id` fuite) et l'authentification repose sur un secret partagé, sans mot de passe ni rotation.

| | |
|---|---|
| P0 | **0** |
| P1 | **0** (P1-6-03 et P1-6-06 corrigés et vérifiés) |
| P2 | **3** (inchangés, non traités par cette mission) |
| P3 | **1** (inchangé) |

## 2. Git — SHA audité, branches, base

| Rôle | SHA | Branche |
|------|-----|---------|
| **Code audité** | **`c0cb01bd049ef009cc143212951d8359dd9dd0e8`** (`fix(security): correction des P1 de securite web de la Phase 6 (P1-6-03, P1-6-06)`) | `origin/fix/miles-web-authorization-security` |
| Base (parent) | `0754032e4933eba80a7fd22ed282bc0a930b3607` — **conforme à l'attente** | `origin/feature/miles-mission-orchestrator` |
| Audit précédent (rév. 2) | `16b521153a5d61f51605bc658cf5131d7fa946d4` | `origin/audit/agent-b-phase6-orchestrator-review-v2` |
| Branche d'audit (cette mission) | `dbf468d17d77e6b6e7a1f12871f379a141c35afc` | `origin/audit/agent-b-phase6-1-web-security-review` |
| `main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` — **inchangée** | `origin/main` |

Diff audité : 23 fichiers, +2860/−201. Nouveau module `app/interface/web_auth.py` (498 lignes), nouveau `tests/web_test_support.py`, nouveau `tests/test_web_security_phase6_1.py` (648 lignes).

**Aucun SHA de correction n'était fourni dans la mission** : j'ai identifié `c0cb01b` par `git ls-remote`, vérifié sa base, et audité **le code réel**, pas le rapport d'Agent A.

## 3. Environnement et limite Debian 13

| | Windows | Debian 13 |
|---|---|---|
| Système | Windows | **Debian GNU/Linux 13 (trixie)** *(session précédente)* |
| Python | 3.14.7 | 3.13.5 *(session précédente)* |
| **Accès à la VM pendant CETTE session** | poste de l'agent | ❌ **INDISPONIBLE** — `Test-NetConnection 127.0.0.1 -Port 2222` → `TcpTestSucceeded : False` ; 2 tentatives de connexion SSH → `Connection refused` |

**Aucune validation Debian 13 n'est revendiquée pour cette révision.** Les résultats ci-dessous sont exclusivement Windows. La validation Debian 13 reste à effectuer dès que la VM sera de nouveau joignable.

## 4. Tests exécutés

| Exécution | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Durée |
|---|---|---|---|---|---|---|
| Suite complète (code audité + 64 tests d'audit) | **558** | **558** | 0 | 0 | 6 | 87,1 s |

Les 6 skips sont des **limites de plateforme Windows**, toutes justifiées et toutes déjà exécutées sous Debian 13 lors de la rérevision 2 :
- 3 tests de liens symboliques (privilège « Développeur » requis sous Windows) ;
- 1 test de fuite de descripteurs (`/proc/self/fd` absent) ;
- 2 tests de lien symbolique de mon audit (même raison).

### 4.1 Tests d'audit d'Agent B

| Module | Tests | Rôle |
|---|---|---|
| `tests/test_audit_phase6_agent_b.py` | 24 | Révision 1, **adaptés** au code corrigé |
| `tests/test_audit_phase6_v2_agent_b.py` | 20 | Révision 2, **adaptés** |
| `tests/test_audit_phase6_1_agent_b.py` | 20 | **Nouveau** — 20 scénarios d'attaque Phase 6.1 |

**Mécanisme de détection utilisé.** Mes 6 tests documentant les défauts de la révision 2 étaient marqués `@unittest.expectedFailure` (ils exprimaient le comportement *souhaité*). Après correction d'Agent A, ils sont devenus **`UNEXPECTED SUCCESS`** : c'est la preuve mécanique que les défauts sont bien levés. J'ai retiré les décorateurs et figé le comportement correct dans des tests ordinaires.

## 5. P1-6-03 — Contrôle d'origine / CSRF / Content-Type : RÉSOLU

**Mécanisme implémenté par Agent A** (`app/interface/web_auth.py` + `app/interface/web.py`) :
- `OriginPolicy` : origine non autorisée → refus ; `Referer` non autorisé → refus ; origine absente → la requête passe ce stade mais **doit** satisfaire session + CSRF ;
- `WebAuthenticator` : session par client, jeton CSRF distinct, expiration, révocation, verrouillage après 5 échecs de connexion ;
- `_check_origin` → `_check_content_type` → `_read_body` → `POST /session` → `_require_session` → `_check_csrf` → action (`web.py:683-724`). **Les contrôles précèdent toute lecture de corps et toute action** : une requête refusée n'a aucun effet.

### 5.1 Scénarios reproduits et résultats

| # | Scénario | Code HTTP | Effet de bord vérifié |
|---|----------|-----------|----------------------|
| 1 | `POST /tool`, `Origin: http://site-malveillant.example`, `Content-Type: text/plain` | **403** | aucun outil exécuté |
| 2 | `POST /remember`, origine étrangère | **403** | **0 souvenir créé** (mémoire vérifiée avant/après) |
| 3 | `POST /forget`, origine étrangère | **403** | **souvenir intact** (1/1, `get_memory` non nul) |
| 4 | `Origin` absent, sans session | **401** | aucune action |
| 5 | `Origin` absent, session valide, **CSRF absent** | **403** | aucune action |
| 6 | **CSRF falsifié** | **403** | aucune action |
| 7 | **CSRF d'une autre session** | **403** | aucune action |
| 8 | `Origin: null` | **403** | aucune action |
| 9 | `Origin: http://127.0.0.1.evil.example` (falsification) | **403** | aucune action |
| 10 | `Origin: https://127.0.0.1` (schéma non local) | **403** | aucune action |
| 11 | `Origin: http://127.0.0.1@evil.example` (injection userinfo) | **403** | aucune action |
| 12 | `Origin: javascript:alert(1)` | **403** | aucune action |
| 13 | `Origin` absent, `Referer: http://site-malveillant.example/page.html` | **403** | aucune action |
| 14 | `Content-Type: text/plain` avec session + CSRF **valides** | **415** | aucune action |
| 15 | Client **sans authentification** (aucun en-tête de session) | **401** | aucune action |
| 16 | **5 soumissions répétées** avec origine étrangère | 403 ×5 | **0 souvenir créé** (pas d'effet cumulatif) |
| 17 | Requête légitime (contrôle de non-régression) | **200** | 1 souvenir créé (comportement préservé) |
| 18 | **Aucun identifiant configuré** → `POST /session` | 401/403 | **interface fermée par défaut** |

**Route `/forget` et `/remember` : le contrôle d'origine s'applique bien** (scénarios 2 et 3) — j'ai vérifié l'absence de suppression et de création.

**Note sur CORS.** Je n'ai pas considéré CORS comme une protection : le serveur ne renvoie aucun en-tête `Access-Control-*`, et mon analyse porte sur le refus effectif côté serveur (`Origin`/`Referer`/CSRF/`Content-Type`), pas sur la politique du navigateur.

## 6. P1-6-06 — Autorisation de mission : RÉSOLU

**Mécanisme implémenté** (`app/interface/web.py`, `WebApp.authorize_mission`) : la signature est désormais `authorize_mission(self, mission_id, data, session: WebSession)` et le contrôle est **triple** :

```python
if mission.owner_user_id and mission.owner_user_id != session.user_id:
    return {"error": "Cette mission appartient a un autre utilisateur."}
approval_token = data.get("approval_token")
if not isinstance(approval_token, str) or not approval_token:
    return {"error": "Jeton d'autorisation manquant."}
```

### 6.1 Scénarios reproduits et résultats

| # | Scénario | Code HTTP | Effet de bord vérifié |
|---|----------|-----------|----------------------|
| 19 | `POST /mission/<id>/authorize` **sans session** | **401** | aucune mission autorisée |
| 20 | Session valide, **CSRF absent** | **403** | aucune mission autorisée |
| 21 | **Identifiant de session deviné** (`session-fabriquee-0000`) | **401** | aucune mission autorisée |
| 22 | **Session révoquée** | **401** | aucune mission autorisée |
| 23 | **Session expirée** (TTL 10 s, horloge injectée) | **401** | aucune mission autorisée |
| 24 | **Utilisateur B** tente d'autoriser une mission de l'utilisateur A | **403/404** | refus explicite (« appartient à un autre utilisateur ») |
| 25 | **Client B vole le `session_id` du client A** | refus | la session est **liée à l'identité** ; le jeton de confirmation du client A est refusé chez le client B |
| 26 | Jeton de confirmation lié à la mission A, **rejoué sur la mission B** | refus | usage unique + liaison mission conservées |
| 27 | **Le modèle IA ne peut pas produire d'approbation** | — | le magasin d'identifiants n'accepte que des jetons **explicitement configurés** ; aucune sortie de fournisseur n'en crée un |

**Correction de P1-6-02 (résiduel) confirmée.** La session web est désormais **créée par connexion** (et non au démarrage du processus) : deux clients obtiennent deux `session_id` distincts (vérifié), et un jeton de confirmation obtenu par un client est **refusé** chez un autre.

**Identité humaine ou session technique ?** La distinction demandée est respectée et documentée par Agent A lui-même (`web_auth.py:329-332`) : la session est « un jeton aléatoire créé au démarrage de l'application » et « **n'est pas une identité humaine** ». Le mécanisme retenu est une **authentification minimale mais réelle** : possession d'un secret exigée, secret non devinable (32 octets d'entropie), révocable, expirant, et **fermeture par défaut** si aucun secret n'est configuré. La session **sert désormais d'identité** et est liée aux confirmations et aux autorisations.

## 7. Non-régression

| Vérification | Résultat |
|---|---|
| Le chemin `ToolService` → `ToolEngine` n'est pas contourné | ✅ inchangé (`executor.py:213-218`, `service.py:118-125`) |
| Validations non affaiblies | ✅ `assertEqual(413)` / `assertEqual(400)` stricts ; `_assert_refused` (qui acceptait un reset TCP) toujours absent |
| Aucune écriture possible pendant la mission pilote | ✅ registre sans outil d'écriture ; `open(target, "r")` |
| Tests existants d'Agent A | ✅ tous passent (558/558) |
| Tests de sécurité non supprimés ni relâchés | ✅ mes 64 tests d'audit sont conservés ; 3 ont été **adaptés** à la nouvelle API web (authentification obligatoire) et 2 **réécrits** en tests positifs |

**Point d'attention :** 3 de mes tests de la révision 1 échouaient après le correctif (`403` au lieu de `400`) — non parce que le code était fautif, mais parce que ces tests n'authentifiaient pas. Ils ont été adaptés (ils ouvrent désormais une session). Aucun test de sécurité n'a été supprimé ni affaibli pour obtenir une suite verte.

## 8. P2 et P3 encore présents (non traités par cette mission)

| ID | Prio | Défaut | Inchangé ? |
|----|------|--------|-------------|
| P2-6-04 | P2 | `fork()` dans un processus multi-thread (`DeprecationWarning`) | ✅ inchangé |
| P2-6-05 | P2 | Le jeton de confirmation est renvoyé à l'appelant | ✅ inchangé (mais P1-6-02 corrigé : la session est désormais par client) |
| P2-6-07 | P2 | Bornes (12 étapes, 120 s) par passage de boucle, pas par mission | ✅ inchangé |
| P2-6-08 | P2 | Borne « 5 échanges » en CLI uniquement, absente du web | ✅ inchangé |
| P2-6-09 | P2 | `results` non persistés ; `list_missions` ignore la base ; `record_event` jamais appelé | ✅ inchangé |
| P2-6-10 | P2 | Une étape restée `RUNNING` n'est ni reprise ni rejouée | ✅ inchangé |
| P3-6-12 | P3 | L'interface web n'est pas lancable par `miles.py` | ✅ inchangé (mais voir §9) |

**Nouveau risque résiduel (P2) — détournement de session.** Le `session_id` est un **jeton porteur** : quiconque l'obtient (XSS local, extension navigateur, journal, capture) peut agir au nom de l'utilisateur jusqu'à son expiration (1 800 s par défaut). Le jeton CSRF limite les requêtes *modifiantes* mais pas la lecture (`GET /status`, `/memory`, `/missions`, `/mission/<id>`). Recommandation : réduire la durée de vie de la session, lier le `session_id` à l'agent utilisateur du navigateur, et considérer une rotation.

## 9. Limites de la revue

- **Validation Debian 13 impossible pendant cette session** (VM injoignable, port 2222 fermé). Les 6 tests ignorés sous Windows n'ont pas été rejoués sur la VM dans cette révision ; ils l'avaient été, avec succès, lors de la révision 2 sur le commit `0754032`. **À rejouer sur `c0cb01b`.**
- Les endpoints ont été testés via socket HTTP en Python, **sans navigateur réel** : le comportement d'un navigateur (politique CORS, `SameSite`, requêtes à preflight) n'est pas observé. La protection testée est **côté serveur**, ce qui est la bonne cible.
- Le mécanisme d'authentification par secret partagé n'a pas été évalué en profondeur (rotation, stockage du secret, gestion de la fuite du `MILES_WEB_AUTH_TOKEN`).
- `origin/main` et la branche V1 n'ont pas été ré-auditées : l'audit porte sur `c0cb01b`.
- Aucun appel à un fournisseur payant, aucun modèle téléchargé, aucune dépense.

## 10. Recommandations

| # | Action | Responsable | Priorité |
|---|--------|--------------|----------|
| 1 | **Rejouer la suite complète sur Debian 13** quand la VM sera joignable (6 tests ignorés sous Windows) | Agent B | **Haute** |
| 2 | Fusionner `c0cb01b` (et `0754032`) dans `main` — **plus aucun P1 exploitable identifié** | Utilisateur | P1 |
| 3 | Réduire la durée de vie de session et lier la session à l'agent utilisateur (détournement de session) | Agent A | P2 |
| 4 | Fournir le lanceur web `--web` : tant que le serveur n'est pas lancé, le risque web est théorique, mais le jour où il le sera, les contrôles doivent rester en place | Agent A | P3 |
| 5 | Poursuivre les P2-6-04 à P2-6-10 (bornes par mission, `results` persistés, `record_event`, `forkserver`) | Agent A | P2 |

---

*Réaudit réalisé par Agent B le 2026-10-20. Commit audité : `c0cb01bd049ef009cc143212951d8359dd9dd0e8` (base `0754032e4933eba80a7fd22ed282bc0a930b3607`). Branche d'audit : `audit/agent-b-phase6-1-web-security-review`. 558 tests exécutés sous Windows (Python 3.14.7), 0 échec. **Validation Debian 13 non effectuée dans cette session (VM injoignable) — aucune revendication Debian n'est faite.** Aucun appel payant, aucun téléchargement de modèle, aucun fichier de production d'Agent A modifié, `main` intacte, aucune fusion, aucune réécriture d'historique partagé.*
