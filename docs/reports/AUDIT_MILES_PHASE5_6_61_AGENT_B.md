# docs/reports/AUDIT_MILES_PHASE5_6_61_AGENT_B.md — Audit contradictoire MILES Phases 5 / 6 / 6.1 (Agent B)

> Audit contradictoire indépendant, demandé par le responsable de projet.
> Complète `PHASE_6_1_WEB_SECURITY_REVIEW_AGENT_B.md` (audit technique du correctif de sécurité).

## 1. Identité

| Élément | Valeur |
|---|---|
| Dépôt | `https://github.com/Miles-corp/Milescorp.git` |
| Chemin local | `C:\Users\iopjk\Documents\GitHub\Milescorp` |
| Branche de développement (Phase 5) | `origin/feature/miles-tool-engine-integration` = `a11ab4a9af9aff1e4f357ec060a24ebc5aedc717` |
| Branche de développement (Phase 6) | `origin/feature/miles-mission-orchestrator` = `0754032e4933eba80a7fd22ed282bc0a930b3607` |
| Correctif de sécurité (Phase 6.1) | `origin/fix/miles-web-authorization-security` = `c0cb01bd049ef009cc143212951d8359dd9dd0e8` |
| `origin/main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` |
| Audit précédent annoncé | `origin/audit/agent-b-phase6-1-web-security-review` = `ac627dfe703f2827347023dd2e11ec3b9bba3318` — **confirmé identique** |
| **SHA audité** | `c0cb01bd049ef009cc143212951d8359dd9dd0e8` (base `0754032`, base `a11ab4a9`) |
| **SHA proposé à l'intégration** | `c0cb01bd049ef009cc143212951d8359dd9dd0e8` — identique au SHA audité ✅ |

**Tous les SHA annoncés sont réels et inchangés.** Aucun commit n'est apparu depuis l'audit précédent.

### Ascendance et ordre de dépendance

| Relation | Résultat |
|---|---|
| `a11ab4a9` (Phase 5) est ancêtre de `0754032` (Phase 6) | ✅ OUI |
| `0754032` (Phase 6) est ancêtre de `c0cb01b` (Phase 6.1) | ✅ OUI |
| `c0cb01b` est ancêtre de `ac627df` (audit précédent) | ✅ OUI |
| **`b9b7e7d` (`main`) est ancêtre de `a11ab4a9`** | ❌ **NON** |
| **`b9b7e7d` (`main`) est ancêtre de `c0cb01b`** | ❌ **NON** |
| Point de divergence | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` (`fix: address Phase 4 security review findings`) |
| Commits de `main` absents du candidat | 2 (`4b6f515` = base, et `928410c` = mon rapport de revue Phase 4) |
| Commits du candidat absents de `main` | 19 |
| Fichiers modifiés des **deux** côtés depuis `4b6f515` | **aucun** (seul `docs/reports/PHASE_4_REVIEW_AGENT_B.md` est ajouté par `main`, et n'est pas touché par le candidat) |

## 2. Reproduction

### 2.1 Commandes réellement exécutées

```bash
git fetch origin --prune
git ls-remote --heads origin
git merge-base --is-ancestor <a> <b>
git merge-base origin/main origin/fix/miles-web-authorization-security
git diff --name-only 4b6f515..origin/main
git diff --name-only 4b6f515..origin/fix/miles-web-authorization-security
git merge-tree --write-tree --name-only origin/main origin/fix/miles-web-authorization-security
git archive --format=zip -o merged.zip 082acd9d   # export de l'arbre fusionné, sans commit
python -m unittest discover -s tests
python3 -m unittest discover -s tests
```

### 2.2 Environnement

| | Windows | Debian 13 (VM autorisée) |
|---|---|---|
| Système | Windows | **Debian GNU/Linux 13 (trixie)**, noyau `6.12.113+deb13-amd64` |
| Python | 3.14.7 | 3.13.5 |
| Accès | poste de l'agent | `ssh -p 2222 miles@127.0.0.1` → `su` root |

### 2.3 Résultats chiffrés

| Exécution | Arb tested | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Durée |
|---|---|---|---|---|---|---|---|
| Windows | **arbre fusionné `082acd9`** | 558 | 558 | 0 | 0 | 6 | 87,3 s |
| Debian 13 | **arbre fusionné `082acd9`** | 558 | 558 | 0 | 0 | **0** | 120,6 s |
| Debian 13 | candidat `c0cb01b` | 558 | 558 | 0 | 0 | 0 | 128,7 s |
| Debian 13 | tests d'attaque Phase 6.1 | 23 | 23 | 0 | 0 | 0 | 21,7 s |

Les 6 tests ignorés sous Windows sont des **limites de plateforme** (3 liens symboliques exigeant le privilège « Développeur », 1 comptage de descripteurs `/proc/self/fd`, 2 liens symboliques d'audit) : **ils s'exécutent et passent sous Debian 13** (`test_pas_de_fuite_de_descripteurs ... ok`).

### 2.4 Attaques reproduites sur l'arbre fusionné (Debian 13)

| # | Requête | HTTP attendu | HTTP obtenu | Effet de bord vérifié |
|---|---------|--------------|------------|----------------------|
| 1 | `POST /tool`, `Origin: http://site-malveillant.example`, `Content-Type: text/plain` | 403 | **403** « Origine non autorisee. » | aucun outil exécuté |
| 2 | `POST /remember`, origine étrangère | 403 | **403** | **0 souvenir créé** |
| 3 | `POST /forget`, origine étrangère | 403 | **403** | **0 souvenir supprimé** (mémoire vide après 2 attaques) |
| 4 | `POST /tool` sans session | 401 | **401** | aucune action |
| 5 | `POST /tool` session sans CSRF | 403 | **403** | aucune action |
| 6 | `POST /tool` CSRF falsifié | 403 | **403** | aucune action |
| 7 | `POST /tool` `Content-Type: text/plain` (session+CSRF valides) | 415 | **415** | aucune action |
| 8 | `POST /mission/<id>/authorize` sans session | 401 | **401** | aucune mission autorisée |
| 9 | `POST /tool` requête légitime | 200 | **200** | non-régression OK |
| 10 | CSRF d'une autre session | 403 | **403** | aucune action |
| 11 | Session expirée / révoquée / devinée | 401 | **401** | aucune action |
| 12 | Autorisation d'une mission d'un autre utilisateur | 403/404 | **403/404** | refus explicite |
| 13 | Confirmation rejouée sur une autre mission | refus | **refus** | usage unique conservé |
| 14 | Origines falsifiées (`null`, `127.0.0.1.evil`, `https://127.0.0.1`, `127.0.0.1@evil`, `javascript:`) | 403 | **403** | aucune action |
| 15 | `Referer` étranger | 403 | **403** | aucune action |
| 16 | 5 soumissions répétées | refus | **refus ×5** | pas d'effet cumulatif |
| 17 | Chemins hors racines, liens symboliques sortants, fichiers sensibles (`.env`, `id_rsa*`), bornes de lecture (64 Kio, profondeur 3) | refus/ok | **ok** | aucune écriture |

### 2.5 Éléments impossibles à vérifier

| Élément | Raison |
|---|---|
| Comportement dans un **navigateur réel** | Les tests sont hechos en Python (socket). La politique CORS du navigateur n'est pas simulée ; le serveur n'émet **aucun** en-tête `Access-Control-Allow-Origin`, ce qui est vérifié par code HTTP direct. |
| Rotation / stockage du secret `MILES_WEB_AUTH_TOKEN` | Hors du code audité (gestion deSecrets applicative). |
| Tests avec un vrai fournisseur IA | Non autorisé (coût API). Aucun appel payant effectué. |

## 3. Défauts

### D-B01 — La politique de sécurité refuse des chemins légitimes contenant « code », « shell », « token », « password »

| | |
|---|---|
| **Gravité** | **P2** (fonctionnel, conditionné à l'environnement) |
| **Preuve reproductible** | Dépôt du projet dans un répertoire dont le chemin contient `code` (ex. `C:\Users\X\opencode\Milescorp`) → `action_read_file` sur un chemin valide de ce répertoire : `success = False`, message « Action refusée par la politique de sécurité. » ; le même chemin sans `code` passe la politique. Le clone placé dans `.../Temp/opencode/merged_tree` fait **échouer 2 tests d'Agent A** (`test_lecture_d_un_fichier_volumineux`, `test_resultat_volumineux_au_dela_du_tampon`). Testé sur l'arbre fusionné : 558/558 en chemin neutre, **556/558** en chemin contenant `code`. |
| **Impact** | Sur une installation dont le chemin contient `code` (ex. `opencode`, `vscode`, `decode`, `mycode`), **toute** lecture de fichier de la mission est refusée : la couche d'outils est inopérante. |
| **Correction nécessaire** | La politique compare les **valeurs** aux motifs d'interdits ; un chemin de fichier n'est pas une commande. Exclure le paramètre `path` de la vérification par valeur, ou n'appliquer le contrôle qu'aux valeurs qui ressemblent à des commandes. |
| **Résultat du nouveau test** | Non appliqué (correction sous la responsabilité d'Agent A). Test de non-régression à créer : `test_chemin_legitime_contenant_code_accepte`. |
| **Bloque-t-il la fusion ?** | **Non** (P2, pas P1). Mais il doit être corrigé : le défaut se manifeste dès que le chemin du projet contient `code`. |

### D-B02 — Réserve de conception : le `session_id` est un jeton porteur, non lié au navigateur

| | |
|---|---|
| **Gravité** | **P2 — réserve de conception documentée** (pas une vulnérabilité exploitable à distance) |
| **Preuve reproductible** | `DEFAULT_SESSION_TTL_SECONDS = 1800` (30 min) ; `SESSION_HEADER = X-MILES-Session` ; la session est un `secrets.token_hex(32)` créé à la connexion. Routes de lecture : `/status`, `/memory`, `/missions`, `/tools` → **401 sans session, 200 avec session seule (sans CSRF)** : le CSRF ne protège que les requêtes modifiantes. Aucun `Access-Control-Allow-Origin` n'est émis (`(absent)` vérifié), et une requête cross-origin portant un en-tête personnalisé déclenche un préflight que le serveur ne traite pas → **le navigateur bloque la lecture cross-origin**. |
| **Impact** | Une fuite du `session_id` (XSS, extension navigateur, processus local, journal) donne l'impersonation de l'utilisateur pendant 30 min, y compris en lecture. Ce n'est **pas** exploitable par un site tiers : pas de CORS, préflight bloqué, serveur lié à `127.0.0.1` uniquement. |
| **Correction nécessaire** | Recommandée, non bloquante : (1) réduire la durée de vie de session (300 s comme l'approbation) ; (2) lier la session à un secret persistant côté navigateur ; (3) exiger le CSRF sur les routes de lecture également. |
| **Résultat du nouveau test** | Non applicable (réserve assumée et documentée par Agent A dans `web_auth.py`). |
| **Bloque-t-il la fusion ?** | **Non**, à condition que l'équipe accepte explicitement cette réserve. |

### D-B03 — Bornes de mission par passage de boucle, non par mission (inchangé)

| | |
|---|---|
| **Gravité** | **P2** |
| **Preuve** | `runner.py:413-417` : `executed`, `deadline`, `identical` sont des variables locales à `_execute_loop`, réinitialisées à chaque `run()` (`answer` `:261`, `authorize` `:311`, `resume` `:313`). |
| **Correction** | Porter les compteurs sur l'objet `mission` persisté. Non traitée par Agent A dans `c0cb01b`. |
| **Bloque la fusion ?** | Non. |

### D-B04 — Borne « 5 échanges » présente en CLI uniquement (inchangé)

| | |
|---|---|
| **Gravité** | **P2** |
| **Preuve** | `cli.py:407-414` seule occurrence ; absent de `app/orchestration/` et de l'interface web. |
| **Correction** | Porter la borne dans l'orchestrateur. |
| **Bloque la fusion ?** | Non. |

### D-B05 — `results` non persistés, `list_missions` ignore la base, `record_event` jamais appelé, étape `RUNNING` non reprise (inchangé)

| | |
|---|---|
| **Gravité** | **P2** |
| **Preuve** | `runner.py:414` (`results` local), `runner.py:166-180` vs `store.py:295-314`, `store.py:336-352` (jamais appelé), `runner.py:329-334` (seuls `FAILED`/`UNCERTAIN` traités). |
| **Correction** | Persister `results` et l'état `RUNNING` ; appeler `record_event()`. |
| **Bloque la fusion ?** | Non. |

### D-B06 — L'interface web des missions n'est pas lançable par `miles.py` (inchangé)

| | |
|---|---|
| **Gravité** | **P3** |
| **Preuve** | `miles.py:229-237` ne construit que la `CLI` ; aucun lanceur `MilesWebServer`. |
| **Correction** | Fournir un lanceur explicite (`--web`) — en conservant les contrôles d'origine et de CSRF. |
| **Bloque la fusion ?** | Non. |

### Points positivement vérifiés (aucun défaut)

| Contrôle | Preuve |
|---|---|
| Chemin d'exécution unique `ToolService` → `ToolEngine` | `executor.py:213-218`, `service.py:118-125`, `engine.py:329` |
| Un plan n'est jamais une autorisation | `grants.py:17-19` ; `runner.py:300-307` (seul `authorize()` émet un grant) |
| L-007 arrêt effectif | `process.terminate()` / `process.kill()` présents dans l'arbre fusionné |
| L-008 politique appliquée | 3 appels `validate_no_*` présents dans l'arbre fusionné |
| L-009 expiration des confirmations | `expires_at` + `context_id`/`actor_id` présents |
| L-010 audit sans secret brut | message générique « Erreur d'exécution. » |
| S-001 / S-003 préservés | import `PersistentMemoryError` ; `sanitize_text` / `public_provider_error` |
| S-006 files fermées | `_close_queues` présent |
| P2-6-04 `fork()` multi-thread | **CORRIGÉ** : contexte explicite `forkserver` (Linux/macOS) / `spawn` (Windows) (`engine.py:88-110`) ; plus aucun `DeprecationWarning` observé |
| Aucun secret dans l'arbre fusionné | scan de motifs sur le diff : aucun |

## 4. Intégration

| Contrôle | Résultat |
|---|---|
| SHA de la branche candidate | `c0cb01bd049ef009cc143212951d8359dd9dd0e8` — audité |
| SHA proposé à la fusion | **identique** au SHA audité ✅ |
| Différences entre `main` réel et le candidat | 2 commits de `main` absents du candidat, 19 du candidat absents de `main`, **aucun fichier modifié des deux côtés** |
| Conflits de fusion | **aucun** : `git merge-tree --write-tree` → code de sortie **0**, arbre `082acd9d1c97dd172162ee141d75a782333992d3` |
| Contenu de l'arbre fusionné vs candidat | **1 seul fichier** de différence : `docs/reports/PHASE_4_REVIEW_AGENT_B.md` (documentation) — **code identique** |
| L-007→L-010, S-001, S-003, S-006, P1-6-03, P1-6-06 dans l'arbre fusionné | ✅ tous présents (vérifiés par extraction depuis `082acd9`) |
| Suite complète sur l'arbre fusionné | ✅ 558/558 (Windows) et 558/558 **0 ignoré** (Debian 13) |
| Modifications non commitées | `git diff HEAD` : **aucune** modification de contenu (les marqueurs `M` observés sont des artefacts de cache d'index, vérifiés par `git diff --summary` vide) |
| PC Monitor | sans incidence sur MILES |

## 5. Décision finale — MILES

# AUTORISÉ À FUSIONNER

**SHA exact audité : `c0cb01bd049ef009cc143212951d8359dd9dd0e8`** (fusion avec `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` → arbre `082acd9d1c97dd172162ee141d75a782333992d3`, **sans conflit**).

**Conditions réunies :**
- Contrôles requis rejoués sur l'arbre **réellement fusionné** : 558/558 sous Debian 13 (**0 ignoré**) et sous Windows (6 ignorés justifiés), 23 scénarios d'attaque Phase 6.1, 17 reproductions d'attaques directes, effets de bord vérifiés à chaque fois.
- **Aucun P1 exploitable** identifié sur les routes sensibles : origine, CSRF, `Content-Type`, session, expiration, révocation, réinjection, propriété de mission, jeton d'approbation.
- Fusion **sans conflit**, code de l'arbre fusionné identique au SHA audité.
- L-007→L-010, S-001, S-003, S-006 préservés ; P2-6-04 corrigé par Agent A.

**Réserves non bloquantes** (P2, à planifier, **ne bloquent pas la fusion**) :
1. **D-B01 (P2)** — la politique refuse les chemins légitimes contenant `code`/`shell`/`token`/`password` → couche d'outils inopérante si le projet est installé sous un tel chemin. **À corriger rapidement** : c'est le défaut le plus gênant du lot.
2. **D-B02 (P2, réserve de conception documentée)** — `session_id` = jeton porteur 30 min, non lié au navigateur, CSRF absent des routes de lecture. Non exploitable à distance (pas de CORS, préflight bloqué, bind local) ; exploitable seulement en cas de fuite du jeton. **Décision d'acceptation à acter explicitement** par le responsable de projet, avec les 3 recommandations de durcissement.

**Si l'équipe classe D-B02 en P1** (par exemple parce qu'une extension navigateur non approuvée est installée), la fusion doit être bloquée jusqu'à réduction de la durée de vie des sessions.

## 6. Actions manuelles exactes restantes

1. **Fusion** (par le responsable de projet) :
   ```bash
   git checkout main
   git merge --no-ff c0cb01bd049ef009cc143212951d8359dd9dd0e8
   python -m unittest discover -s tests
   git push origin main
   ```
   Attendu : fusion sans conflit, 558/558.
2. **Décision explicite** sur D-B02 (accepter la réserve du jeton porteur, ou exiger un durcissement avant fusion).
3. **Ouvrir un ticket** pour D-B01 (politique : ne pas appliquer le contrôle par valeur aux chemins de fichiers) — à traiter par Agent A, avec le test de non-régression `test_chemin_legitime_contenant_code_accepte`.
4. **Planifier** D-B03 à D-B05 (bornes par mission, `results` persistés, `record_event`, étape `RUNNING`).
5. **Ne pas oublier** l'étape 3 de la mission : vérifier que le SHA de `main` n'a pas changé depuis `b9b7e7d` au moment de la fusion ; sinon, ré-auditer le nouveau SHA.

---

*Audit réalisé par Agent B le 2026-10-20. Commandes, chiffres et reproductions exécutés sur le poste Windows (Python 3.14.7) et sur la VM Debian GNU/Linux 13 (Python 3.13.5) autorisée. Aucun appel payant, aucun téléchargement de modèle, aucune fusion, aucun push sur `main`, aucune modification de la production d'Agent A, aucune réécriture d'historique partagé.*
