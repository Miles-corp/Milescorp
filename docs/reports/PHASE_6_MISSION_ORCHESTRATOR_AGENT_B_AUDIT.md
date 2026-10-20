# docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_B_AUDIT.md — Audit indépendant Phase 6 (Agent B)

## 1. Conclusion

# NON VALIDÉ

**L'orchestrateur de missions annoncé par la Phase 6 n'existe pas dans le dépôt.** La branche attendue `feature/miles-mission-orchestrator` n'est pas publiée, et aucune des 7 branches distantes ne contient de module d'orchestrateur (`app/orchestration/` ne contient qu'un `.gitkeep`). Il est donc **impossible de valider la Phase 6** : aucune des fonctionnalités demandées (réception d'un objectif, demande de clarification, plan explicite, validation du plan, exécution multi-étapes, arrêt d'une mission bloquée, compte rendu fidèle, reprise de mission) ne peut être vérifiée ni testée.

Ce qui **est** publié et a donc été audité : l'intégration du moteur d'outils dans le CLI et l'interface web (branche `feature/miles-tool-engine-integration`, commit `a11ab4a9`), brique sur laquelle l'orchestrateur reposera. Sur cette brique, l'audit relève **un P1 persistant** (jeton de confirmation non lié à une identité), **un second P1** (aucun contrôle d'accès sur les endpoints web) et **deux P2** (`fork()` en contexte multi-thread ; confirmation retournée à l'appelant).

**Recommandation : ne pas approuver la Phase 6, ne pas exposer les outils à un modèle et ne pas utiliser l'orchestrateur pour des actions sensibles tant que les P1 ne sont pas traités.**

## 2. SHA exacts, branches et base

| Rôle | SHA | Branche |
|------|-----|---------|
| **Code audité** | **`a11ab4a9af9aff1e4f357ec060a24ebc5aedc717`** (`feat: integration du moteur d'outils dans le CLI et l'interface web`) | `origin/feature/miles-tool-engine-integration` |
| Branche d'audit d'Agent B | `b9899c4987f8d01d72598eaefd87c733e4fbf209` | `origin/audit/agent-b-phase6-orchestrator-review` |
| Base de `a11ab4a9` | `bccdc1c3b85aa311b97c233dafc7ef6d43925fb5` | `origin/feature/miles-v1-conversation-persistence` |
| `main` | `b9b7e7d3d1400a515a2f0d9c4c76d6b628861527` | `origin/main` — **inchangée par Agent B** |
| Branche attendue (Phase 6) | **INEXISTANTE** | `feature/miles-mission-orchestrator` |

Recherche exhaustive sur les 7 branches distantes : aucun fichier `orchestrat*` ni `mission*` dans `app/`. Seul `app/orchestration/.gitkeep` est présent. La branche V1 est par ailleurs passée de `9a53652` à `bccdc1c` entre deux sessions.

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
git worktree add --detach /root/miles-audit a11ab4a9af9aff1e4f357ec060a24ebc5aedc717
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_audit_phase6_agent_b -v
```

## 4. Résultats des tests

| Exécution | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Attendus en échec | Durée |
|---|---|---|---|---|---|---|---|
| **Debian 13** (code audité + tests d'audit) | **402** | **402** | 0 | 0 | **0** | 3 | 55,1 s |
| Windows (code audité + tests d'audit) | 402 | 402 | 0 | 0 | 5 | 3 | 47,4 s |

Les 5 skips Windows (3 liens symboliques + 1 comptage de FD + 1 lien symbolique d'audit) sont des limites de plateforme : **sous Debian 13, aucun test n'est ignoré**.

Les **3 « expected failures »** sont mes tests d'audit qui expriment le comportement *souhaité* pour 3 défauts constatés (§6). Ils deviendront « unexpected success » le jour où le défaut sera corrigé : c'est le signal de retrait de `expectedFailure`.

## 5. Vérifications effectuées

### 5.1 Propriétés validées (sans réserve)

| Propriété | Preuve |
|---|---|
| Aucun contournement du moteur | CLI et web partagent **le même** `ToolService` → le même `ToolEngine` (`test_cli_et_web_utilisent_le_meme_service`) |
| Outils interdits rejetés | Clés `shell`, `code`, `api_key` → refusées par la politique (`test_cle_interdite_refusee_par_la_politique`) |
| Outil inconnu refusé | `test_outil_inconnu_refuse` ; via HTTP → 400 (`test_outil_inconnu_refuse_par_la_route`) |
| Chemins confinés | `/etc` refusé ; **lien symbolique sortant réellement créé → refusé** (`test_lien_symbolique_sortant_refuse`, exécuté sous Debian 13) |
| Aucune écriture via un outil | Le registre ne contient que 4 outils en lecture seule (`test_aucun_outil_ecriture_dans_le_registre`) |
| Confirmation : expiration | TTL respecté, jeton expiré refusé (`test_audit_confirmation_expiree_refusee`) |
| Confirmation : usage unique | Jeton consommé, rejeu refusé (`test_audit_confirmation_non_rejouable`) |
| Confirmation : liaison outil + paramètres | Jeton invalide pour un autre outil ou d'autres paramètres → refusé |
| Confirmation non contournable sans jeton | `user_confirmed=True` sans jeton valide → rien n'est exécuté |
| Pas de faux succès | Exception du handler → `success=False` + message ; résultat vide → `success=True` mais `data=""` (distingué) |
| Délai d'exécution | Timeout → `success=False`, message « dépassé » |
| Erreurs journalisées | Le refus est inscrit à l'audit (`test_echec_audit_est_journalise`) |
| L-007 → L-010 préservés | `app/tools/engine.py` **inchangé** depuis `9a53652` |
| Aucun appel payant | Aucun appel Groq, aucun modèle téléchargé ou installé |

### 5.2 Scénarios non testés (et pourquoi)

| Scénario demandé | Statut | Raison |
|---|---|---|
| Réception d'un objectif | ❌ Non testable | Aucun orchestrateur dans le dépôt |
| Demande de clarification | ❌ Non testable | idem |
| Plan explicite + validation du plan | ❌ Non testable | idem |
| Plan mal formé / outil interdit dans un plan | ❌ Non testable | idem (le rejet d'un outil interdit **direct** est testé) |
| Exécution multi-étapes dans le bon ordre | ❌ Non testable | idem |
| Erreur d'outil suivie d'une tentative de reprise | ⚠️ Partiel | Testé au niveau moteur (jeton absent/périmé → refus). Le rejeu d'étape n'existe pas sans orchestrateur. |
| Réponse IA vide ou incohérente | ❌ Non testable | idem |
| Arrêt d'une mission bloquée ou trop longue | ❌ Non testable | idem (le délai d'un **outil** est testé) |
| Annulation pendant léxécution | ⚠️ Partiel | Annulation **humaine** testée côté CLI/web ; annulation de mission inexistante |
| Reprise d'une mission après interruption | ❌ Non testable | idem |
| Double lancement d'une mission | ❌ Non testable | idem |
| Contenu malveillant dans un fichier analysé | ❌ Non testable | Aucun outil d'analyse de fichier n'existe |
| Persistance d'une autorisation périmée | ⚠️ Partiel | Jeton **d'outil** : expiration + usage unique testés. Aucune persistance d'autorisation n'existe (confirmations en mémoire vive). |
| Confirmation expirée / rejouée / invalide | ✅ Testé | 3 tests dédiés |
| Lecture hors répertoire autorisé | ✅ Testé | y compris lien symbolique sortant |

## 6. Défauts classés par priorité

### P0-6-01 — L'orchestrateur de missions n'est pas publié : la Phase 6 est invérifiable

| Élément | Valeur |
|---|---|
| **Priorité** | **P0 — bloquant pour la validation** |
| **Fichier / fonction** | Aucun : le code attendu (`app/orchestration/…`) est absent ; seul `app/orchestration/.gitkeep` existe |
| **Étapes reproductibles** | `git ls-remote --heads origin` → 7 branches, aucune `feature/miles-mission-orchestrator`. Sur chacune : `git ls-tree -r --name-only <branche> \| grep -E 'orchestrat\|mission'` → seul `app/orchestration/.gitkeep` |
| **Résultat observé** | Aucune fonctionnalité d'orchestrateur (objectif, plan, validation, exécution multi-étapes, arrêt, compte rendu, reprise) n'existe |
| **Résultat attendu** | Branche `feature/miles-mission-orchestrator` publiée, avec module d'orchestrateur et tests associés |
| **Test démontrant le problème** | `tests/test_audit_phase6_agent_b.py::TestAuditOrchestratorPresence::test_orchestrateur_de_missions_present_dans_le_depot` — passe **aujourd'hui** (constat de l'absence) et **échouera** dès qu'un orchestrateur sera ajouté : c'est le détecteur de livraison |
| **Correction recommandée** | Publier l'implémentation de l'orchestrateur, puis relancer l'audit. Aucun correctif applicable côté Agent B. |

### P1-6-02 — Le jeton de confirmation n'est lié à aucune identité

| Élément | Valeur |
|---|---|
| **Priorité** | **P1 — élevé** |
| **Fichier / fonction** | `app/tools/engine.py:66` (`_PendingConfirmation`), `:467` (`_create_pending_confirmation`), `:481` (`_find_pending_confirmation`) ; `app/tools/service.py:127` (le jeton est renvoyé à l'appelant) ; `app/interface/web.py:679` (`_handle_run_tool`) |
| **Étapes reproductibles** | `ToolService()` → `request_tool("action_list_files", {"path":"data"})` → jeton `T`. Puis **le même service** (cas du serveur web : un `ToolService` partagé par tous les clients HTTP) → `request_tool(..., user_confirmed=True, confirmation_token=T)` → **exécuté** |
| **Résultat observé** | Le jeton n'est lié qu'à `tool_id` + `parameters_hash` + `expires_at`. Aucune session, aucun utilisateur, aucune origine. **Vérifié sous Debian 13** : « accepté par un autre client du MÊME service : True » |
| **Résultat attendu** | Un jeton doit être lié à une session humaine identifiée ; un client sans cette session doit être refusé |
| **Preuve disponible** | Test d'audit `test_audit_defaut_confirmation_non_liee_a_une_identite` (marqué `expectedFailure` : exprime le comportement *souhaité*, échoue donc aujourd'hui). Le rapport de Phase 5 d'Agent A reconnaît le risque : « Confirmation non liée à une identité … À traiter avant toute exposition des outils au modèle » |
| **Correction recommandée** | Ajouter un identifiant de session (cookie `HttpOnly` + `SameSite=Strict`, ou jeton opaque par session) et le lier à `_PendingConfirmation` ; vérifier ce lien dans `_find_pending_confirmation`. Tant que ce n'est pas fait, **ne pas exposer les outils à un modèle** : celui-ci recevrait le jeton dans la réponse de la première requête et pourrait le rejouer sans intervention humaine. |

### P1-6-03 — Aucun contrôle d'accès sur les endpoints web (CSRF local)

| Élément | Valeur |
|---|---|
| **Priorité** | **P1 — élevé** |
| **Fichier / fonction** | `app/interface/web.py:333` (`_read_body` — `Content-Type` de requête jamais validé), `:432` (route `/tool`), `:679` (`_handle_run_tool`) ; **aucun** contrôle `Origin`/`Referer` dans tout le fichier |
| **Étapes reproductibles** | `POST http://127.0.0.1:<port>/tool` avec `Content-Type: text/plain` et `Origin: http://site-malveillant.example` → **HTTP 200, outil exécuté** (vérifié sous Debian 13) |
| **Résultat observé** | Un site tiers ouvert dans le navigateur de l'utilisateur peut envoyer une requête « simple » (type `text/plain`, sans préflight CORS) vers le serveur local. Le serveur est lié à `127.0.0.1` mais n'exige aucun en-tête d'origine : la protection repose **uniquement** sur le bind. Les outils enregistrés étant en lecture seule, l'impact direct est limité (lecture de l'arborescence, divulgation du répertoire courant) — **mais `/forget` (suppression d'un souvenir) et `/remember` sont exposés par la même surface** |
| **Résultat attendu** | Refus des requêtes dont l'`Origin` n'est pas local/autorisé ; validation du `Content-Type` de la requête ; protection prioritaire des méthodes mutantes `/remember`, `/forget`, `/tool` |
| **Preuve disponible** | Tests d'audit `test_audit_defaut_requete_cross_origin_refusee` (attente 403) et `test_audit_defaut_content_type_non_json_refuse` (attente 415), tous deux `expectedFailure` |
| **Correction recommandée** | Valider `Origin`/`Referer` (accepter uniquement `http://127.0.0.1:<port>` et `http://localhost:<port>`), refuser toute origine absente sur les méthodes mutantes, exiger `Content-Type: application/json`, et ajouter un jeton CSRF à double soumission. |

### P2-6-04 — `fork()` dans un processus multi-thread (avertissement Python)

| Élément | Valeur |
|---|---|
| **Priorité** | **P2 — moyen** |
| **Fichier / fonction** | `app/tools/engine.py` (`_execute_tool` → `multiprocessing.Process`) ; interaction avec `ThreadingHTTPServer` (`app/interface/web.py`) |
| **Étapes reproductibles** | `python3 -W all -m unittest tests.test_tool_integration` sous Debian 13 → `DeprecationWarning: This process (pid=…) is multi-threaded, use of fork() may lead to deadlocks in the child.` |
| **Résultat observé** | Le serveur web est multi-thread ; le moteur fork un processus par appel d'outil. Avertissement dès Python 3.12 ; **Python 3.14 changera le défaut de `fork` vers `forkserver`**, ce qui modifie la sérialisation exigée des handlers |
| **Résultat attendu** | Plus de `fork` en contexte multi-thread, ou adoption explicite de `forkserver`/`spawn` |
| **Preuve disponible** | `DeprecationWarning` reproduit sur Debian 13 (Python 3.13.5) pendant la suite de tests |
| **Correction recommandée** | Fixer explicitement la méthode de démarrage (`multiprocessing.get_context("forkserver")` sous Linux, `spawn` sous Windows) et l'annoncer dans la documentation ; à traiter avant le passage à Python 3.14 |

### P2-6-05 — La confirmation est retournée à l'appelant (surface de contournement par le modèle)

| Élément | Valeur |
|---|---|
| **Priorité** | **P2 — moyen** (dépend de P1-6-02) |
| **Fichier / fonction** | `app/tools/service.py:127` (`describe_result` expose `confirmation_token`) ; `app/interface/web.py:679` ; JS `runTool` ; `app/interface/cli.py` (`_handle_tool_command`) |
| **Étapes reproductibles** | 1ᵉʳ appel `POST /tool` → réponse contenant `confirmation_token` ; 2ᵉ appel avec `user_confirmed=true` + ce jeton → exécution |
| **Résultat observé** | Le client reçoit le jeton ; la décision humaine n'est vérifiée que **côté client** (`window.confirm()` en JS, `input("Confirmer ? (o/N)")` en CLI). Un orchestrateur piloté par un modèle pourrait rejouer le jeton sans demande humaine |
| **Résultat attendu** | La décision humaine doit être attestée par le serveur (session liée), pas seulement par le client |
| **Preuve disponible** | `app/tools/service.py:127`, `app/interface/web.py` (JS), `app/interface/cli.py` |
| **Correction recommandée** | Résolu par la correction de P1-6-02 ; ne pas exposer les outils au modèle avant. |

### Note d'audit — défaut dans mon propre test (corrigé, sans impact produit)

Ma première version de `test_audit_defaut_confirmation_non_liee_a_une_identite` s'appelait `audit_defaut_…` (sans préfixe `test_`) : unittest ne la collectait pas, le test passait donc « sans rien prouver ». Je l'ai renommée, marquée `expectedFailure`, et **reformulée pour utiliser le service partagé** (le cas réel du serveur web) — une première version utilisait un second `ToolService`, dont le moteur distinct rejetait le jeton pour la mauvaise raison. La version finale démontre réellement le défaut (vérifié sous Debian 13). Aucun fichier de production d'Agent A n'a été modifié : le seul fichier ajouté est un fichier de **test** d'audit.

## 7. Statut du problème de confirmation (point de vigilance prioritaire)

| Question | Réponse vérifiée |
|---|---|
| Le défaut « jeton non lié à l'identité » existe-t-il encore ? | **OUI** — `_PendingConfirmation` ne contient que `tool_id`, `parameters_hash`, `token`, `expires_at` (`engine.py:66-79`). Aucun champ session/utilisateur. |
| Les confirmations sont-elles expirables ? | **OUI** — TTL 300 s (L-009), contrôle `self._clock() > pending.expires_at` (`engine.py:497`), suppression du jeton expiré. Testé (`test_audit_confirmation_expiree_refusee`). |
| Sont-elles protégées contre le rejeu ? | **OUI** — `self._pending_confirmations.pop(pending.token, None)` (`engine.py:283`) après usage. Testé (`test_audit_confirmation_non_rejouable`) : le rejeu est refusé. |
| Le modèle peut-il contourner la confirmation ? | **Pas via le moteur** : `user_confirmed=True` sans jeton valide → refusé. **Mais il peut la court-circuiter** : le jeton est renvoyé à l'appelant (`service.py:127`), qui peut le rejouer immédiatement sans demande humaine (P2-6-05). |
| Conséquence à retenir | **Ne pas exposer les outils à un modèle tant que P1-6-02 n'est pas corrigé.** |

## 8. Limites de la revue

- La Phase 6 proprement dite (orchestrateur de missions) **n'a pas pu être auditée** : le code n'existe pas dans le dépôt.
- Aucun appel à un fournisseur payant, aucun modèle téléchargé, aucune dépense.
- L'audit porte sur le commit `a11ab4a9` ; la branche V1 a avancé depuis (`bccdc1c`) sans que cela concerne le moteur d'outils.
- Les endpoints web ont été testés en local (127.0.0.1) ; aucun test depuis un vrai navigateur tiers n'a été réalisé (le contrôle d'absence d'`Origin` est démontré par l'absence de code et par l'acceptation d'une requête portant un en-tête `Origin` tiers).
- `app/tools/engine.py` n'a pas été modifié depuis `9a53652` : les conclusions sur L-007→L-010 sont reportées telles quelles.

## 9. Recommandations

| # | Action | Responsable | Priorité |
|---|--------|--------------|----------|
| 1 | Publier l'orchestrateur de missions sur `feature/miles-mission-orchestrator`, puis relancer l'audit | Agent A | **P0** |
| 2 | Lier le jeton de confirmation à une session humaine identifiée | Agent A | **P1** |
| 3 | Ajouter validation `Origin`/`Referer` + `Content-Type` + jeton CSRF sur `/tool`, `/remember`, `/forget` | Agent A | **P1** |
| 4 | Fixer la méthode de démarrage multiprocessing (`forkserver`/`spawn`) avant Python 3.14 | Agent A | P2 |
| 5 | Ne pas exposer les outils au modèle avant le traitement du P1-6-02 | Tous | P1 |
| 6 | Fusionner `a11ab4a9` et `bccdc1c` dans `main` après traitement des P1 | Utilisateur | — |

---

*Audit réalisé par Agent B le 2026-10-20. Commit audité : `a11ab4a9af9aff1e4f357ec060a24ebc5aedc717`. Branche d'audit : `audit/agent-b-phase6-orchestrator-review`. Environnements : Windows (Python 3.14.7) et Debian GNU/Linux 13 trixie (Python 3.13.5, accès SSH autorisé). Aucun appel payant, aucun téléchargement de modèle, aucune modification de `main`, aucune fusion, aucune réécriture d'historique.*
