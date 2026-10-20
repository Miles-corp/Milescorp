# docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_B_AUDIT.md — Audit indépendant Phase 6 (Agent B)

> **Révision 2 — réaudit du commit `0754032` (orchestrateur de missions publié).**
> Révision 1 : audit du commit `a11ab4a9`, où l'orchestrateur était absent → non-validé.

## 1. Verdict

# VALIDÉ SOUS RÉSERVES

**La Phase 6 est fonctionnellement livrée et vérifiée** : l'orchestrateur existe, fonctionne en lecture seule, respecte les bornes annoncées, persiste et se reprend. Le défaut P1-6-02 (jeton sans liaison de contexte) est **réellement corrigé au niveau du moteur**.

**En revanche, deux défauts P1 de sécurité exploitables subsistent sur la surface web** : aucun contrôle d'origine sur les routes modifiantes, et aucune identité humaine authentifiée sur l'autorisation de mission. Conformément à la consigne de ce mission, **je ne recommande aucune fusion** tant que ces deux points ne sont pas corrigés ou compensés de façon vérifiée.

| | |
|---|---|
| P0 | **0** (l'orchestrateur est publié et audité) |
| P1 | **2** (P1-6-03 contrôle d'accès web, P1-6-06 autorisation de mission sans identité) |
| P2 | **3** (fork() multi-thread, jeton renvoyé à l'appelant, bornes par passage de boucle) |
| P3 | **2** (documentation, table d'événements inutilisée) |

## 2. SHA audités, branches et base

| Rôle | SHA | Branche |
|------|-----|---------|
| **Code audité** | **`0754032e4933eba80a7fd22ed282bc0a930b3607`** (`feat: orchestrateur de missions (autonomie en lecture seule) - Phase 6`) | `origin/feature/miles-mission-orchestrator` |
| Base réelle (parent) | `a11ab4a9af9aff1e4f357ec060a24ebc5aedc717` — **conforme à l'annonce** | `origin/feature/miles-tool-engine-integration` |
| Branche d'audit d'Agent B (révision 1) | `2ffea1382d94a5d411e7749591dd446dff9564ed` | `origin/audit/agent-b-phase6-orchestrator-review` |
| Branche d'audit d'Agent B (révision 2) | `64cbf5ebcc1955e812b5d53366a4c01b34a1967b` | `origin/audit/agent-b-phase6-orchestrator-review-v2` |
| `main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` — **inchangée par Agent B** | `origin/main` |

Diff audité : 25 fichiers, +5866/−42. 7 nouveaux modules dans `app/orchestration/` (2 862 lignes), nouveau `app/tools/grants.py` (351 lignes), 1 457 lignes de tests (`tests/test_mission_orchestrator.py`).

## 3. Environnement et commandes

| | Windows | Debian 13 |
|---|---|---|
| Système | Windows | **Debian GNU/Linux 13 (trixie)**, noyau `6.12.113+deb13-amd64` |
| Python | 3.14.7 | **3.13.5** |
| Accès | poste de l'agent | `ssh -p 2222 miles@127.0.0.1` → `su` root, worktree isolé `/root/miles-audit` |
| Dépendances | stdlib | stdlib |

```bash
# Debian 13
git fetch origin
git worktree add --detach /root/miles-audit 0754032e4933eba80a7fd22ed282bc0a930b3607
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_audit_phase6_agent_b tests.test_audit_phase6_v2_agent_b -v
```

## 4. Tests exécutés

| Exécution | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Attendus en échec | Durée |
|---|---|---|---|---|---|---|---|
| **Debian 13** (code audité + 47 tests d'audit) | **498** | **498** | 0 | 0 | **0** | 6 | 69,8 s |
| Windows (code audité + 47 tests d'audit) | 498 | 498 | 0 | 0 | 6 | 6 | 62,9 s |

**Sous Debian 13, aucun test n'est ignoré** : les tests de liens symboliques (S-005), de fuite de descripteurs (S-006) et de lecture de fichier s'exécutent réellement.

**Les 6 « expected failures »** sont mes tests d'audit qui expriment le comportement *souhaité* pour 6 défauts constatés. Ils basculeront en « unexpected success » à la correction.

### 4.1 Les 24 tests d'audit de la révision 1, adaptés

| Test d'audit | Adaptation | Résultat |
|---|---|---|
| `test_audit_defaut_confirmation_non_liee_a_une_identite` | **Réécrit** : le moteur lie désormais le jeton à `actor_id`/`context_id`. Le test cible désormais le **cas résiduel réel** (session web unique partagée par tous les clients) | reste `expectedFailure` → **P1-6-02 partiel** |
| `test_aucun_outil_ecriture_dans_le_registre` | Liste complétée avec `action_read_file` | passe |
| `test_audit_defaut_requete_cross_origin_refusee` | inchangé | reste `expectedFailure` → **P1-6-03** |
| `test_audit_defaut_content_type_non_json_refuse` | inchangé | reste `expectedFailure` → **P1-6-03** |
| `test_lecture_hors_repertoire_autorise_refusee` | inchangé | passe |
| `test_lien_symbolique_sortant_refuse` | inchangé | passe (exécuté sous Debian 13) |
| 18 autres | inchangés | passent |

### 4.2 Les 23 tests d'audit ajoutés (révision 2)

| Domaine | Tests | Résultat |
|---|---|---|
| **A. Grants** | autre session refusée · autre mission refusée · outil non couvert refusé · expiration · révocation · révocation par mission · non-rejeu au-delà de `max_uses` · chemin hors racine non couvert · **session = identité technique, non humaine** | **10/10 passent** |
| **B. Web** | `/tool` cross-origin · `/remember` cross-origin · `/forget` cross-origin · autorisation de mission sans identification | 3 `expectedFailure` (**P1-6-03**, **P1-6-06**), 1 passe |
| **C. Lecture de fichiers** | hors racines refusé · nom sensible `.env` refusé · nom sensible `id_rsa*` refusé · lien symbolique sortant refusé · taille bornée · lecture ne modifie pas le fichier | **6/6 passent** |
| **D. Contenu non fiable** | instructions dans un fichier n'élargissent pas les permissions · erreur fournisseur sans fuite de secret | **2/2 passent** |

## 5. Audit fonctionnel — vérification des affirmations d'Agent A

| Fonctionnalité annoncée | Vérification dans le code | Verdict |
|---|---|---|
| Planification | `runner.py:371-408` (`_build_plan`) ; `planner.py:327-413` (déterministe) et `planner.py:438-501` (IA avec repli tracé) | ✅ |
| Validation du plan avant exécution | `planner.py:204-312` (`validate_plan_payload`) : objet JSON, liste, non vide, ≤12 étapes, objectif/outil non vides, outil enregistré **et autorisé**, paramètres déclarés, types contrôlés, blacklist de commandes | ✅ |
| Exécution multi-étapes ordonnée | `models.py:221-226` (`next_pending` → première étape PENDING) ; boucle `runner.py:422-505` | ✅ |
| Utilisation de ToolService/ToolEngine | `executor.py:213-218` → `service.py:118-125` → `engine.py:329` : **chemin unique**, l'exécuteur n'a pas d'accès direct au moteur | ✅ |
| Limite 12 étapes | `models.py:264` + `settings.py:76` ; appliquée par `runner.py:439-444` **et** `planner.py:231-235` | ⚠️ voir P2-6-07 |
| Limite 2 tentatives/étape | `models.py:265` ; `runner.py:451` (`attempts += 1`), `runner.py:482-485` (reprise si `TRANSIENT` et `attempts < max`) — seuls les échecs transitoires sont rejoués | ✅ |
| Limite 120 secondes | `models.py:266` ; échéance absolue `runner.py:413`, test `runner.py:427-433` | ⚠️ voir P2-6-07 |
| Limite 5 échanges | **CLI uniquement** : `cli.py:407-414`. **Aucun équivalent web, aucune borne dans `app/orchestration/`** | ⚠️ voir P2-6-08 |
| Persistance SQLite + reprise | `store.py:35-352` (`data/missions.db`), `runner.py:313-342` (`resume`) | ✅ avec réserves (P2-6-09) |
| Pas de rejeu automatique d'une étape incertaine | `models.py:221-226` : `next_pending` ne sélectionne que `PENDING` ; `resume` passe `FAILED`/`UNCERTAIN` en `UNCERTAIN` (`runner.py:329-334`) | ✅ (trou complementaire : étape restée `RUNNING`, P2-6-10) |
| Mission pilote en lecture seule | Registre : 5 outils, **aucun en écriture** (`builtin.py:39-150`) ; liste blanche `READ_ONLY_TOOLS` (`builtin.py:157-163`) + double refus `executor.py:189-198` | ✅ |
| Intégration CLI et web | CLI : 6 commandes (`cli.py:382-527`). Web : 7 routes (`web.py:577-610`) | ⚠️ le web n'est **pas lancable** par `miles.py` (P3-6-12) |
| Résultats non fiables | Contenu de fichier **jamais injecté** dans une consigne IA (`observer.py:128-133` ne compte que caractères/lignes) ; sortie du modèle = donnée validée ; `sanitize_text` avant écriture | ✅ |

## 6. Défauts P0 / P1 / P2 / P3

### P1-6-03 — Aucun contrôle d'accès sur les routes web modifiantes (persiste)

| Élément | Valeur |
|---|---|
| **Priorité** | **P1 — élevé, exploitable** |
| **Fichiers / fonctions** | `app/interface/web.py` : `_read_body` (aucune validation du `Content-Type` de la requête), `_handle_run_tool` (route `/tool`, `web.py:432`), routes `/remember` et `/forget`, routes `/mission/<id>/authorize`, `/answer`, `/cancel`. **Aucune occurrence de `Origin`, `Referer`, `CSRF` ou `X-Requested-With` dans tout le fichier.** |
| **Étapes reproductibles** | `POST http://127.0.0.1:<port>/tool` avec `Content-Type: text/plain` et `Origin: http://site-malveillant.example` → **HTTP 200, outil exécuté**. Idem sur `/remember` (écriture) et `/forget` (suppression). Vérifié sous Debian 13. |
| **Résultat observé** | Le serveur est lié à `127.0.0.1` mais n'exige aucun en-tête d'origine : la protection repose **uniquement** sur le bind. Un site tiers ouvert dans le navigateur de l'utilisateur peut émettre des requêtes « simples » (type `text/plain`, sans préflight CORS) vers les routes locales. |
| **Résultat attendu** | Refus des requêtes dont l'`Origin` n'est pas local ; validation du `Content-Type` ; jeton CSRF sur les routes modifiantes. |
| **Preuve** | 3 tests d'audit `expectedFailure` : `test_audit_defaut_requete_cross_origin_refusee`, `test_audit_defaut_remember_accepte_une_requete_cross_origin`, `test_audit_defaut_forget_accepte_une_requete_cross_origin`. |
| **Correction recommandée** | Valider `Origin`/`Referer` (n'accepter que `http://127.0.0.1:<port>` et `http://localhost:<port>`), refuser toute origine absente sur `/remember`, `/forget` et les routes de mission, exiger `Content-Type: application/json`, ajouter un jeton CSRF à double soumission. |

### P1-6-06 — L'autorisation de mission ne requiert aucune identité

| Élément | Valeur |
|---|---|
| **Priorité** | **P1 — élevé, exploitable** |
| **Fichiers / fonctions** | `app/interface/web.py` : `WebApp.authorize_mission` (≈l.235-249) et `_handle_mission_authorize` (≈l.900-907) ; `app/orchestration/runner.py:280-311` (`authorize`) |
| **Étapes reproductibles** | `POST /mission/<id>/authorize` avec `{"approved": true}` — sans jeton, sans session, sans contrôle d'origine. L'endpoint accorde l'autorisation et émet un grant (`runner.py:300-307`). |
| **Résultat observé** | La « confirmation humaine » est en réalité **une confirmation par n'importe quel client HTTP**. Le grant émis est lié à `self.session_id` du runner — **une session technique par processus**, pas à une personne. L'identifiant de mission est un UUID, mais il est lisible via `GET /missions`. |
| **Résultat attendu** | Une autorisation d'action sensible doit émaner d'un utilisateur authentifié, pas d'un client quelconque. |
| **Preuve** | Test d'audit `test_autorisation_de_mission_sans_identification` : analyse de la source de `authorize_mission`, absence de `session_id`/`token`/`authenticate`/`Origin`/`csrf`. |
| **Correction recommandée** | Exiger une session web par client (cookie `HttpOnly` + `SameSite=Strict`, ou jeton opaque par client) et faire porter ce session_id par `authorize_mission` ; à défaut, désactiver l'endpoint d'autorisation tant que l'interface web n'est pas multi-utilisateur. |

### P1-6-02 (partiellement corrigé) — Jeton lié à une session technique, pas à une identité humaine

| Élément | Valeur |
|---|---|
| **Priorité** | **P1 — élevé (résiduel)** |
| **Fichiers / fonctions** | `app/tools/engine.py:66-79` (`_PendingConfirmation` enrichi de `context_id`/`actor_id`), `:536-565` (`_find_pending_confirmation` : contrôle désormais `context_id` **et** `actor_id`), `:276-330` (voie « grant » , `:508-530` (`_create_pending_confirmation`) ; `app/tools/grants.py:326-334` (`default_session_id`) |
| **Ce qui est corrigé** | Le jeton n'est plus réutilisable **ni dans une autre mission** **ni dans une autre session** : vérifié sous Debian 13 — « accepté par une AUTRE session : False ». C'est une amélioration réelle par rapport à `a11ab4a9`. |
| **Ce qui subsiste** | La session du serveur web est créée **au démarrage de l'application** (`web.py:145-147`, `default_session_id("web")`) : **tous les clients HTTP partagent le même `actor_id`**. Un jeton obtenu par un client reste utilisable par un autre client du même serveur. Vérifié sous Debian 13 — « accepté par un autre client de la MÊME session : True ». |
| **Distinction exigée** | `default_session_id` est explicitement documenté comme « un jeton aléatoire créé au démarrage de l'application » et « **n'est pas une identité humaine** » (`grants.py:329-332`). Lier un jeton à une session technique **ne vaut pas** authentification d'une personne : il n'existe aucun compte, mot de passe ni mécanisme d'authentification dans le dépôt (vérifié : `grants.py` ne contient ni `password` ni `authenticate`). |
| **Correction recommandée** | Session **par client** (cookie `HttpOnly`/`SameSite=Strict` ou jeton opaque par client) et non par processus ; à défaut, un jeton d'autorisation à usage unique hors bande (affiché à l'écran, saisi par l'utilisateur). |

### P2-6-04 — `fork()` dans un processus multi-thread

| Élément | Valeur |
|---|---|
| **Priorité** | P2 — moyen |
| **Fichiers** | `app/tools/engine.py` (`_execute_tool` → `multiprocessing.Process`) ; interaction avec `ThreadingHTTPServer` |
| **Reproduction** | `python3 -W all -m unittest tests.test_tool_integration` sous Debian 13 → `DeprecationWarning: This process (pid=…) is multi-threaded, use of fork() may lead to deadlocks in the child.` |
| **Correction recommandée** | `multiprocessing.get_context("forkserver")` (Linux) / `spawn` (Windows), explicite et documenté ; Python 3.14 changera le défaut. |

### P2-6-05 — Le jeton est renvoyé à l'appelant

| Élément | Valeur |
|---|---|
| **Priorité** | P2 — moyen |
| **Fichiers** | `app/tools/service.py:127` (`describe_result` expose `confirmation_token`) ; `app/interface/web.py` |
| **Observation** | Le client reçoit le jeton ; la décision humaine n'est attestée que **côté client** (`window.confirm()` / `input("Confirmer ? (o/N)")`). Un orchestrateur piloté par un modèle pourrait rejouer le jeton. Aggravé par P1-6-02 : la session est partagée. |
| **Correction recommandée** | Résolu par P1-6-02 (session par client) ; ne pas exposer les outils au modèle avant. |

### P2-6-07 — Les bornes (12 étapes, 120 s) sont par passage de boucle, pas par mission

| Élément | Valeur |
|---|---|
| **Priorité** | P2 — moyen |
| **Fichiers** | `app/orchestration/runner.py:413-417` (`executed`, `deadline`, `identical` sont des variables **locales** à `_execute_loop`) ; `runner.py:261` (`answer`), `:311` (`authorize`), `:313-342` (`resume`) relancent `run()` → nouvelle boucle → compteurs réinitialisés |
| **Observation** | Une mission alternant question/réponse peut dépasser 12 étapes et 120 s **au total**. La borne de 5 interactions (CLI) limite partiellement ce cas ; **le web n'a aucune borne équivalente**. |
| **Correction recommandée** | Porter les compteurs et l'échéance sur l'objet `mission` (persisté), pas sur la boucle. |

### P2-6-08 — La borne « 5 échanges » n'existe qu'en CLI

| Élément | Valeur |
|---|---|
| **Priorité** | P2 — moyen |
| **Fichiers** | `app/interface/cli.py:407-414` (unique occurrence) ; **absent** de `app/orchestration/` et de l'interface web |
| **Correction recommandée** | Porter la borne dans l'orchestrateur (compteur persisté), comme pour P2-6-07. |

### P3-6-11 — Table `mission_events` inutilisée ; `record_event()` jamais appelé

| Élément | Valeur |
|---|---|
| **Priorité** | P3 — faible |
| **Fichiers** | `app/orchestration/store.py:336-352` (définition) — aucun appel dans le dépôt |
| **Correction recommandée** | Appeler `record_event()` aux transitions d'état, ou retirer la table. |

### P3-6-12 — L'interface web des missions n'est pas joignable

| Élément | Valeur |
|---|---|
| **Priorité** | P3 — faible |
| **Fichiers** | `miles.py:229-237` ne construit que la `CLI` ; aucun lanceur `MilesWebServer` (`web.py:973-1019`) ; aucune UI mission dans le HTML servi |
| **Observation** | Les routes de mission ne sont atteignables que par usage programmatique. **Facteur atténuant** pour P1-6-03 et P1-6-06 : l'exposition suppose qu'un intégrateur lance le serveur web. Ce n'est pas une mesure compensatoire vérifiée (ni `Origin` ni CSRF ne sont en place). |
| **Correction recommandée** | Fournir un lanceur explicite (`--web`) **et** corriger P1-6-03 / P1-6-06 avant de l'exposer. |

## 7. Protections effectivement vérifiées (sans réserve)

| Protection | Preuve |
|---|---|
| Chemin unique d'exécution (`ToolService` → `ToolEngine`) | `executor.py:213-218`, `service.py:118-125`, `engine.py:329` ; CLI et web partagent le même service (`test_cli_et_web_utilisent_le_meme_service`) |
| Un plan n'est jamais une autorisation | `planner.py:204-312` valide ; `grants.py:17-19` : « le modèle ne fournit jamais un grant » ; `runner.py:300-307` : seul `authorize()` émet un grant |
| Outil inconnu ou interdit rejeté | `test_outil_inconnu_refuse`, `test_cle_interdite_refusee_par_la_politique` |
| Sorties d'outils et contenus de fichiers = données non fiables | Contenu **jamais** injecté dans une consigne IA (`observer.py:128-133`) ; plan IA sans `source`/`target_parameter` (`planner.py:303-310`) ; `test_contenu_de_fichier_ne_contourne_pas_la_politique` |
| Chemins confinés, liens symboliques compris | `resolve_authorized_path` (résolution canonique) ; `test_lien_symbolique_sortant_refuse` (exécuté sous Debian 13) ; `test_lecture_hors_repertoires_autorise_refusee` |
| Fichiers sensibles refusés | `.env`, `.netrc`, `id_rsa*`, `*.pem`, `*.key`… (`local_actions.py:44-91`) ; `test_lecture_d_un_fichier_sensible_refusee`, `test_lecture_d_un_fichier_cle_privee_refusee` |
| Bornes de lecture | `max_bytes` plafonné à 64 Kio (`HARD_MAX_READ_BYTES`), profondeur ≤ 3, ≤ 500 entrées ; `test_taille_de_lecture_bornee` |
| Aucune écriture pendant la mission pilote | Registre sans outil d'écriture (`builtin.py:39-150`) ; `open(target, "r")` ; `test_lecture_ne_modifie_pas_le_fichier` |
| Confirmation non contournable sans jeton | `user_confirmed=True` sans jeton valide → refusé |
| Confirmation expirée / rejouée / hors session / hors mission | 4 tests d'audit passent |
| L-007 → L-010 préservés | `engine.py` : seules les adjonctions `context_id`/`actor_id`/grant ; `terminate()`/`kill()`/`PRAGMA`/`expires_at` intacts |
| Erreurs signalées sans faux succès | `test_exception_du_handler_non_presentee_comme_succes` ; pas de rejeu automatique d'étape incertaine (`models.py:221-226`) |

## 8. Limites de la revue

- **Aucune identité humaine authentifiée** n'existe dans le dépôt : l'audit ne peut que constater l'absence de mécanisme, pas en évaluer la correction.
- Les endpoints web ont été testés en local via socket ; **aucun test depuis un vrai navigateur tiers** n'a été réalisé. L'absence de contrôle d'origine est démontrée par l'absence de code **et** par l'acceptation d'une requête portant un en-tête `Origin` tiers.
- Le budget de 120 s exclut le temps de planification IA (`runner.py:364-367`) et l'appel d'analyse finale (`runner.py:519`, `:678`) : non mesuré, déduit du code.
- `MissionStore.list_missions()` n'étant jamais appelé (`runner.py:166-180` vs `store.py:295-314`), la persistance n'a été validée que via `resume()`.
- Aucun appel à un fournisseur payant, aucun modèle téléchargé, aucune dépense ; le test d'inférence réelle reste non autorisé.
- La branche V1 (`bccdc1c`) et `main` (`b9b7e7d`) n'ont pas été ré-auditées : l'audit porte sur `0754032`.

## 9. Recommandations

| # | Action | Responsable | Priorité |
|---|--------|--------------|----------|
| 1 | **Ne pas fusionner** `0754032` dans `main` tant que P1-6-03 et P1-6-06 ne sont pas corrigés ou compensés de façon vérifiée | Utilisateur | **P1** |
| 2 | Contrôle `Origin`/`Referer` + `Content-Type` + jeton CSRF sur `/tool`, `/remember`, `/forget` et les routes de mission | Agent A | **P1** |
| 3 | Exiger une identité (session **par client**) pour autoriser une mission ; ne pas appeler « confirmation humaine » une validation par n'importe quel client | Agent A | **P1** |
| 4 | Session web **par client** et non par processus (corrige le résiduel de P1-6-02) | Agent A | **P1** |
| 5 | Porter les compteurs de bornes (étapes, durée, échanges) sur la mission persistée | Agent A | P2 |
| 6 | `forkserver`/`spawn` explicite pour `multiprocessing` | Agent A | P2 |
| 7 | Persister `results` et l'état `RUNNING` ; appeler `record_event()` | Agent A | P2/P3 |
| 8 | Ne pas exposer les outils au modèle avant traitement de P1-6-02 et P1-6-05 | Tous | P1 |

---

*Réaudit réalisé par Agent B le 2026-10-20. Commit audité : `0754032e4933eba80a7fd22ed282bc0a930b3607` (base `a11ab4a9af9aff1e4f357ec060a24ebc5aedc717`). Branche d'audit : `audit/agent-b-phase6-orchestrator-review-v2`. Environnements : Windows (Python 3.14.7) et Debian GNU/Linux 13 trixie (Python 3.13.5, accès SSH autorisé). 498 tests exécutés dans chaque environnement, 0 échec. Aucun appel payant, aucun téléchargement de modèle, aucune modification de la production d'Agent A, `main` intacte, aucune fusion, aucune réécriture d'historique partagé.*
