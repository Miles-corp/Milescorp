# docs/reports/PHASE_6_1_WEB_SECURITY_FIX_AGENT_A.md — Correction des P1 de sécurité web (Agent A)

- **Auteur** : Agent A
- **Date** : 2026-10-20
- **Branche** : `fix/miles-web-authorization-security`
- **Base de départ** : `0754032` (Phase 6 — `feature/miles-mission-orchestrator`, auditée par Agent B)
- **Tâche** : TASK-DEV-015
- **Environnement de validation** : Windows, Python 3.12.10 (Debian 13 non disponible depuis ce poste)

---

## 1. Résumé exécutif

Le réaudit d'Agent B de la Phase 6 a confirmé **deux P1 exploitables** sur la
surface web. Les deux sont corrigés, avec des tests reproductibles :

| Défaut | Constat d'Agent B | État | Preuve |
|--------|--------------------|-------|--------|
| **P1-6-03** | Aucune protection Origin/Referer/Content-Type/CSRF sur les routes modifiantes | **CORRIGÉ** | 5 tests d'audit d'Agent B passent désormais (« unexpected success ») ; 35 nouveaux tests |
| **P1-6-06** | `POST /mission/<id>/authorize` n'exigeait aucune identité | **CORRIGÉ** | 12 nouveaux tests d'autorisation ; identité authentifiée + jeton d'approbation à usage unique |
| P1-6-02 (résiduel) | La session web était partagée par **tous** les clients | **CORRIGÉ** | Session par client ; jetons de confirmation non rejouables entre clients |
| P2-6-04 | `fork()` en contexte multi-thread | **CORRIGÉ** | Contexte multiprocessing explicite (`forkserver`/`spawn`) |
| P3-6-11 | Table `mission_events` inutilisée | **CORRIGÉ** | Transitions de mission tracées |
| P3-6-12 | L'interface web n'était pas lançable par `miles.py` | **CORRIGÉ** | `python miles.py --web` (affiche le jeton d'accès) |

**488 tests OK** sur Windows (451 antérieurs + 35 de sécurité web + 2 de
non-régression « résultat volumineux »), 0 échec, 4 ignorés (limites
plateforme connues).

Un défaut fonctionnel préexistant a été découvert et corrigé au passage
(section 8) : tout résultat d'outil supérieur à 8 Kio expiraient à tort.

---

## 2. Synchronisation préalable

| Contrôle | Résultat |
|----------|----------|
| Dépôt distant | `https://github.com/Miles-corp/Milescorp.git` (correct) |
| `git fetch origin --prune` | nouvelle branche distante `audit/agent-b-phase6-orchestrator-review-v2` |
| Phase 6 | `0754032` vérifié, identique en local et sur `origin/feature/miles-mission-orchestrator` |
| `main` | `b9b7e7d` — **inchangée** |
| Artefact local | `tatus --short --branch` **préservé**, hors commit |
| Branche de travail | `fix/miles-web-authorization-security`, créée depuis `0754032` |

Le réaudit d'Agent B (`docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_B_AUDIT.md`,
branche `audit/agent-b-phase6-orchestrator-review-v2`) a été lu intégralement
avant implémentation ; les 47 tests d'audit ont été exécutés **tels quels**
contre ce correctif (section 7).

---

## 3. Architecture d'authentification retenue

MILES n'a **pas** de comptes utilisateurs avec mot de passe. Le mécanisme
retenu est une authentification **par jeton porteur** (bearer token),
explicite et minimale mais réelle :

| Élément | Choix |
|---------|-------|
| Source des identifiants | `MILES_WEB_AUTH_TOKEN` (utilisateur « local ») **ou** `MILES_WEB_USERS_FILE` (JSON `{"utilisateur": "jeton"}`, plusieurs utilisateurs distincts) |
| À défaut | `python miles.py --web` génère un jeton et l'**affiche une seule fois** dans le terminal |
| Échange | `POST /session` avec le jeton → session par client |
| Session | identifiant opaque de 32 octets (256 bits), **distinct par client**, expiration 30 min, révocable |
| Jeton CSRF | 32 octets, **distinct par session**, jamais partagé entre clients |
| Transport | en-têtes `X-MILES-Session` et `X-MILES-CSRF` (jamais en cookie, jamais dans le stockage local du navigateur) |
| Comparaison | `hmac.compare_digest` (temps constant) ; les jetons ne sont stockés qu'empreintés (SHA-256 + sel aléatoire par processus) |
| Force brute | 5 échecs par adresse client → blocage temporaire de 60 s |
| Fichier d'utilisateurs | confiné aux racines autorisées (projet, `data/`) |

**Ce qui n'est pas fait, et pourquoi** : il n'existe toujours pas de mot de
passe, de rotation de secret ni d'authentification multi-facteur. La
protection repose sur la possession d'un jeton à forte entropie, distribué par
le canal local (console). C'est une authentification **réelle** (la possession
du secret est nécessaire, le secret n'est pas devinable, il expire, il est
révocable), mais **pas** une authentification multi-utilisateur complète :
c'est documenté explicitement, y compris dans la documentation
d'installation.

**Le contrôle d'origine n'est pas présenté comme une protection CSRF** : il
s'agit d'une défense complémentaire. La protection principale est le jeton
CSRF lié à une session authentifiée, qu'un site tiers ne peut pas obtenir.

---

## 4. Routes protégées

### 4.1 Refus avant toute action (P1-6-03)

Ordre de vérification appliqué à **toute** requête POST :

| Étape | Contrôle | Refus |
|-------|----------|-------|
| 1 | `Origin` (ou `Referer` à défaut) dans la liste des origines autorisées | **403** |
| 2 | `Content-Type: application/json` | **415** |
| 3 | Session authentifiée valide | **401** |
| 4 | Jeton CSRF valide | **403** |

Les étapes 1 et 2 interviennent **avant** la lecture du corps et avant toute
action : une requête refusée n'a **aucun effet de bord** (test : le journal
d'audit du moteur reste vide, aucun souvenir n'est écrit).

Le corps est néanmoins **consommé et jeté** (dans la limite de 64 Kio) lors
d'un refus, afin que le client puisse lire la réponse de refus au lieu de voir
sa connexion réinitialisée.

### 4.2 Politique d'origine

- Origines autorisées : liste explicite (`MILES_WEB_ALLOWED_ORIGINS`) **plus**
  les origines « même origine » déduites de l'en-tête `Host`, **à condition
  que cet hôte soit local** (le serveur n'écoute que sur `127.0.0.1`) : un
  en-tête `Host` non local ne permet donc pas de forger une origine.
- `Origin` présent et non autorisé → refus systématique (403), même avec une
  session valide.
- `Origin` absent et `Referer` présent et non autorisé → refus (403).
- `Origin` **et** `Referer` absents → la requête est admise à ce stade, mais
  elle doit alors satisfaire les contrôles de session **et** de jeton CSRF,
  qu'un site tiers ne peut pas obtenir. C'est la politique documentée.
- Aucun en-tête CORS n'est envoyé : le navigateur interdit la lecture des
  réponses cross-origin.

### 4.3 Routes concernées

| Route | Avant | Après |
|-------|-------|-------|
| `GET /` | public | public (coque de l'interface + formulaire de connexion, aucune donnée) |
| `POST /session` | inexistant | **public** : échange du jeton contre une session |
| `GET /status`, `/memory`, `/tools`, `/missions`, `/mission/<id>` | public | **401** sans session ; contenu filtré par utilisateur pour les missions |
| `POST /message`, `/remember`, `/forget`, `/tool`, `/mission`, `/mission/<id>/authorize`, `/mission/<id>/answer`, `/mission/<id>/cancel` | public | **401/403/415** selon le cas ; exécution uniquement pour une requête authentifiée, d'origine autorisée, en JSON, avec jeton CSRF valide |

**Sans identifiant configuré, l'interface web est fermée** : les routes
sensibles répondent `403` (« Authentification non configurée »). C'est le
comportement « fermé par défaut » exigé.

---

## 5. Autorisation des missions (P1-6-06)

L'autorisation d'une mission n'est plus une valeur booléenne fournie par le
client :

1. **Identité** : la mission porte un propriétaire (`owner_user_id`) et une
   session (`session_id`). Seuls les missions du même utilisateur sont
   listées ou consultables ; un autre utilisateur reçoit 404/403.
2. **Jeton d'approbation** : la demande en attente porte un jeton
   imprévisible (32 octets), lié à **cette** demande (mission, périmètre
   d'outils, racines), expirant (300 s) et à usage unique. Il n'est **jamais**
   déduit d'un identifiant de mission.
3. **Vérification serveur** : `POST /mission/<id>/authorize` exige la session
   authentifiée, le jeton CSRF, la propriété de la mission **et** le jeton
   d'approbation correspondant. Le grant émis est lié à la session du client
   demandeur : il n'est pas utilisable par un autre client.
4. **Le modèle n'est pas une approbation** : ni le plan, ni un résultat
   d'outil, ni une valeur booléenne peuvent produire une autorisation.

| Cas | Résultat |
|-----|----------|
| Requête non authentifiée | 401, mission inchangée |
| Jeton CSRF invalide | 403, mission inchangée |
| Utilisateur B sur la mission de A | 403, mission inchangée |
| Jeton de la mission 1 sur la mission 2 | refus (exception), mission 2 inchangée |
| Jeton absent / falsifié | refus |
| Jeton expiré | refus |
| Jeton déjà utilisé (rejeu) | refus |
| Autorisation refusée par l'utilisateur | mission arrêtée en `failed` |

Le CLI présente le même jeton d'approbation (la demande en attente est
affichée à l'utilisateur, qui tranche) : la logique est unique.

---

## 6. Vérifications de sécurité complémentaires

| Point d'audit | Vérification | Résultat |
|---------------|--------------|----------|
| Jeton de confirmation renvoyé au client | Le client le reçoit (il doit confirmer), mais il est lié à la **session du client** : un autre client du même serveur ne peut pas le rejouer | **Corrigé** (P1-6-02 résiduel) |
| Session web partagée entre clients | Une session par client (`secrets.token_hex(32)` par connexion) | **Corrigé** |
| Contrôles appliqués dans le moteur et pas seulement dans l'interface | Le CLI et le web passent tous deux par `ToolService` → `ToolEngine` ; une clé `shell` est refusée par la politique dans les deux cas (tests) | **Confirmé** |
| Effet de bord possible avant un refus | Les refus d'origine/de type de contenu interviennent avant la lecture du corps et avant toute action ; journal d'audit vide et aucun souvenir écrit (tests) | **Confirmé** |
| Divulgation d'information par les erreurs | Les messages d'erreur sont génériques (« Origine non autorisee », « Jeton CSRF absent ou invalide ») ; aucun secret, aucune trace d'exception ; test dédié | **Confirmé** |
| Le grant remplace-t-il la politique ? | Non : un grant ne fait que remplacer la confirmation **interactive** ; permissions, types de paramètres, politique de sécurité et délais restent vérifiés par le moteur | **Confirmé** |

---

## 7. Tests

### 7.1 Nouveau fichier `tests/test_web_security_phase6_1.py` (35 tests)

| Cas exigé | Test(s) |
|-----------|---------|
| 1. origine étrangère refusée | `test_1_origine_etrangere_refusee_sur_toutes_les_routes` (5 routes), `test_1b_origine_etrangere_avec_content_type_non_json_refusee`, `test_origine_etrangere_refusee` (unitaire) |
| 2. origine autorisée acceptée **uniquement** avec authentification + CSRF | `test_2_origine_autorisee_sans_authentification_refusee`, `test_2b_origine_autorisee_avec_session_sans_csrf_refusee` |
| 3. absence d'Origin | `test_3_absence_d_origin_traitee_selon_la_politique`, `test_absence_d_origin_et_de_referer_admise` |
| 4. type de contenu incorrect | `test_4_type_de_contenu_incorrect_refuse` (3 types) |
| 5. jeton CSRF absent / incorrect / expiré | `test_5_csrf_absent_ou_incorrect_refuse`, `test_5b_csrf_expire_refuse`, `test_csrf_est_propre_a_la_session` |
| 6. appelant non authentifié incapable d'autoriser | `test_6_appelant_non_authentique_incapable_d_autoriser`, `test_6b_jeton_csrf_invalide_ne_permet_pas_d_autoriser` |
| 7. utilisateur A ne peut pas autoriser la mission de B | `test_7_utilisateur_a_ne_peut_pas_autoriser_la_mission_de_b`, `test_7b_mission_d_un_autre_utilisateur_invisible` |
| 8. jeton d'une mission inutilisable sur une autre | `test_8_jeton_d_une_mission_inutilisable_sur_une_autre`, `test_8b_jeton_absent_refuse` |
| 9. confirmation expirée, révoquée ou rejouée | `test_9_jeton_rejoue_refuse`, `test_9b_demande_expiree_refusee`, `test_9c_jeton_non_reexploitable_par_un_autre_client` |
| 10. aucun effet de bord après un refus | `test_10_aucun_effet_de_bord_apres_un_refus_d_origine` (audit vide), `test_10b_aucune_modification_d_etat_apres_un_refus` |
| 11. CLI et web soumis aux contrôles du moteur | `test_web_avec_session_valide_passe_par_le_moteur`, `test_cli_passe_toujours_par_le_moteur`, `test_moteur_refuse_toujours_un_outil_inconnu` |
| 12. non-régression | suite complète : **488 OK** |

Complétée par : `test_web_ferme_par_defaut_sans_identifiant`,
`test_connexion_avec_un_mauvais_jeton_refusee`,
`test_erreur_ne_divulgue_pas_de_secret`,
`test_jeton_de_confirmation_non_rejouable_entre_clients`,
`test_autorisation_refusee_arrete_la_mission`,
`test_autorisation_web_valide_fait_aboutir_la_mission`.

### 7.2 Tests d'audit d'Agent B exécutés tels quels

Les 47 tests d'audit (`tests/test_audit_phase6_agent_b.py` et
`tests/test_audit_phase6_v2_agent_b.py`, branche
`audit/agent-b-phase6-orchestrator-review-v2`) ont été exécutés **sans
modification** contre ce correctif :

| Résultat | Tests | Signification |
|----------|-------|----------------|
| **unexpected success** (5) | `test_audit_defaut_requete_cross_origin_refusee`, `test_audit_defaut_content_type_non_json_refuse`, `test_audit_defaut_tool_accepte_une_requete_cross_origin`, `test_audit_defaut_remember_accepte_une_requete_cross_origin`, `test_audit_defaut_forget_accepte_une_requete_cross_origin` | Les 5 tests qui exprimaient le **défaut P1-6-03** passent : le défaut est corrigé. L'auteur de l'audit avait écrit « ce test doit être retiré » |
| échec (4) | `test_jeton_invalide_refuse_par_la_route`, `test_outil_inconnu_refuse_par_la_route`, `test_parametres_non_objet_refuses` (routes web désormais authentifiées) ; `test_autorisation_de_mission_sans_identification` (analyse de source) | **Adaptation requise côté Agent B** : les 3 premiers attendent 400/200 et obtiennent 403 (les routes exigent désormais une session authentifiée) ; le 4e vérifie l'**absence** de « session_id / token / authenticate / Origin / csrf » dans `authorize_mission` — la présence de ces mécanismes le fait maintenant échouer (l'auteur avait prévu ce cas) |
| inchangé (1) | `test_audit_defaut_confirmation_partagee_entre_clients_web` (expectedFailure) | Le test simule manuellement une session partagée (`actor_id` réutilisé) : ce scénario ne peut plus se produire via le web (deux clients HTTP ont deux sessions distinctes). L'équivalent réel est couvert par `test_jeton_de_confirmation_non_rejouable_entre_clients` |

Ces 4 tests d'audit **n'ont pas été modifiés ni supprimés** dans cette
branche (ils appartiennent à la branche d'audit d'Agent B) ; l'adaptation
nécessaire est décrite ci-dessus.

### 7.3 Résultats

| Contrôle | Commande | Résultat |
|----------|----------|----------|
| Tests de sécurité 6.1 | `python -m unittest tests.test_web_security_phase6_1` | **35 OK** |
| Non-régression « gros résultat » | `python -m unittest tests.test_tool_large_result` | **2 OK** |
| Tests d'audit Agent B (tels quels) | `python -m unittest tests.test_audit_phase6_agent_b tests.test_audit_phase6_v2_agent_b` | 5 *unexpected success* (les P1 sont corrigés), 4 échecs d'adaptation documentés, 1 expectedFailure inchangé |
| Suite complète | `python -m unittest discover -s tests` | **488 OK, 0 échec, 4 ignorés** (67 s) |
| Compilation | `python -m compileall app miles.py` | **OK** |

Les 4 tests ignorés sont les limites Windows connues (3 symlink, 1
descripteurs de fichiers).

### 7.4 Reproduction manuelle du scénario d'audit

```
POST /tool      Content-Type: text/plain  Origin: http://site-malveillant.example
  -> 403 {"error": "Origine non autorisee."}
POST /remember  (idem)  -> 403
POST /forget    (idem)  -> 403

POST /tool  avec session + CSRF valides (Origin absent)
  -> 200 {"tool_id": "status_read", "success": true, ...}
```

---

## 8. Défaut préexistant découvert et corrigé

En validant la mission pilote, un blocage fonctionnel a été mis au jour :
**tout résultat d'outil supérieur à 8 Kio expirait à tort** (le tampon d'un
tube fait 8192 octets sous Windows).

Cause : le moteur attendait la **fin** du processus enfant avant de lire la
file de résultats. L'enfant, dont le résultat dépassait le tampon, attendait
l'écriture dans le tube pendant que le parent attendait la mort de l'enfant :
impasse. Le délai d'attente expirait, sans rapport avec un défaut de l'outil.

Correction (`app/tools/engine.py`) : le parent **consomme la file pendant
l'exécution** de l'enfant, avec respect du délai et arrêt effectif inchangé
(terminer puis tuer, sans processus zombie). Les files restent fermées dans
tous les cas (invariant S-006).

Effet mesuré : la mission d'analyse du dossier `docs/` passait de 21 s
(2 expirations) à **1,3 s** et se termine en `completed`.

Test de non-régression : `tests/test_tool_large_result.py` (résultat de
40 Kio transmis sans délai).

---

## 9. Autres points de l'audit (P2/P3)

| Point | Décision | Justification |
|-------|----------|---------------|
| **P2-6-04** `fork()` en contexte multi-thread | **Corrigé** | Contexte multiprocessing explicite (`forkserver` si disponible, sinon `spawn`) : plus de `DeprecationWarning` sous Linux, comportement stable face au changement de défaut de Python 3.14. Test S-006 adapté (couture `_make_queue`) sans affaiblissement |
| **P2-6-05** jeton renvoyé à l'appelant | **Partiellement corrigé** | Le jeton de confirmation est toujours renvoyé au client (il doit confirmer), mais il est désormais lié à la session du client : inutilisable par un autre client. Tant que les outils ne sont pas exposés au modèle, le risque résiduel est faible |
| **P2-6-07** bornes par passage de boucle, pas par mission | **Non corrigé — tâche séparée** | Les compteurs (`executed`, `deadline`) sont des variables locales de `_execute_loop` ; `answer()` / `authorize()` / `resume()` relancent une nouvelle boucle. Correction : porter les compteurs sur l'objet `Mission` persisté. Changement modéré, non trivial, à traiter dans une branche dédiée (risque de régression sur les tests de la Phase 6) |
| **P2-6-08** borne « 5 échanges » absente du web et de l'orchestrateur | **Non corrigé — tâche séparée** | Même remède que P2-6-07 (compteur persisté dans le mission) |
| **P3-6-11** table `mission_events` inutilisée | **Corrigé** | `record_event()` est désormais appelé aux transitions (création, clarification, autorisation demandée, autorisation accordée, annulation, fin) |
| **P3-6-12** interface web non lançable par `miles.py` | **Corrigé** | `python miles.py --web [--web-port N]` démarre le serveur local et affiche le jeton d'accès une seule fois. Ce lanceur est ce qui rend le parcours de connexion utilisable |

---

## 10. Limites restantes

| Limite | Impact |
|--------|--------|
| Pas de mot de passe, de rotation de secret ni de 2FA | Le jeton est un secret partagé à forte entropie ; sa fuite donne un accès complet à l'interface locale |
| Serveur web local sans authentification utilisateur au sens classique | La sécurité repose sur la possession du jeton + le caractère local du serveur |
| Pas de limitation de débit sur les routes de données (seulement sur la connexion) | Un client authentifié peut interroger l'API sans limite |
| P2-6-07 / P2-6-08 non corrigés | Une mission qui alterne questions et autorisations peut dépasser les bornes d'étapes et de durée |
| Pas de `SameSite`/`HttpOnly` (jetons en en-têtes, pas en cookies) | Le jeton de session est lisible par le JavaScript de la page (c'est le même origine) ; un XSS pourrait le voler — mitigé par l'absence de dépendance externe et l'absence d'injection HTML (tout est échappé) |
| Validation Debian 13 non faite | Tests validés sous Windows uniquement ; le contexte `forkserver` (Linux) reste à vérifier par Agent B |

---

## 11. Confidentialité

- Aucun secret, clé API, mot de passe ou donnée personnelle dans le code,
  les tests, la documentation ou les messages.
- Le jeton d'accès généré n'est **jamais** écrit sur disque : il est affiché
  une seule fois dans le terminal.
- Les empreintes de jeton ne sont stockées qu'en mémoire, avec un sel
  aléatoire par processus.
- L'artefact local parasite `tatus --short --branch` est préservé et non
  committé.

---

## 12. Fichiers

**Créés**
- `app/interface/web_auth.py`
- `tests/test_web_security_phase6_1.py`
- `tests/test_tool_large_result.py`
- `tests/web_test_support.py` (support de test : authentification)
- `docs/reports/PHASE_6_1_WEB_SECURITY_FIX_AGENT_A.md`

**Modifiés**
- `app/interface/web.py` (contrôles origine/type de contenu/auth/CSRF, session par client, routes de mission authentifiées, formulaire de connexion)
- `app/interface/cli.py` (session applicative présentée aux appels d'outils, jeton d'approbation)
- `app/orchestration/models.py` (propriétaire de mission, jeton d'approbation, expiration)
- `app/orchestration/runner.py` (autorisation liée à une identité, événements tracés)
- `app/orchestration/executor.py` (acteur = session du propriétaire de la mission)
- `app/tools/engine.py` (contexte multiprocessing explicite, drainage des files pendant l'exécution)
- `app/config/settings.py` (`web_auth_token`, `web_users_file`, `web_allowed_origins`)
- `miles.py` (lanceur `--web`, génération et affichage du jeton)
- `docs/installation/INSTALL.md` (section 3quinquies, 3 variables documentées)
- `docs/coordination/{TASKS,STATUS,DECISIONS}.md`
- `tests/{test_web,test_web_security,test_tool_integration,test_mission_orchestrator,test_docs_configuration,test_tool_resources}.py` (adaptation à l'authentification, sans suppression ni affaiblissement)
