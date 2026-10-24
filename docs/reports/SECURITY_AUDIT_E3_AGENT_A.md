# SECURITY_AUDIT_E3_AGENT_A.md — Analyse interne de sécurité (E3) + analyse D1

> **ATTENTION — ANALYSE INTERNE, SANS AUDIT INDÉPENDANT.**
> Ce rapport est réalisé par Agent A (l'auteur du code en partie). Il ne
> remplace PAS l'audit d'Agent B (MI-001 / TASK-DEV-019), toujours attendu.

- **Auteur** : Agent A — **Date** : 2026-10-24
- **Branche analysée** : `integration/miles-post-d1` (`79f8552`, worktree miles-merge)
- **Fichiers** : `app/interface/web_auth.py` (569 lignes), `app/tools/grants.py` (351 lignes),
  `app/orchestration/runner.py` (région `_ensure_authorization`)

## 1. Authentification et sessions (web_auth.py) — VERDICT : SOLIDE

Points forts vérifiés :
- Jetons porteurs : empreintes SHA-256 avec **sel aléatoire par processus** (pepper),
  comparaison **constante** (`hmac.compare_digest`) — aucun stockage en clair après chargement.
- Sessions par client : ID opaque 256 bits, jeton CSRF distinct, expiration 15 min
  d'inactivité **renouvellement glissant**, durée de vie maximale 8 h non renouvelable.
- Lien **User-Agent** : une session volée est **inutile depuis un autre client** (refus
  « fail-closed » si l'UA diffère ou est absent).
- Force brute : blocage 60 s après 5 échecs par adresse.
- **Fermé par défaut** : aucun identifiant configuré → 403 sur toutes les routes sensibles.
- Politique d'origine (CSRF) : Origin/Referer contrôlés, hôtes locaux uniquement.

### Observations résiduelles (aucune vulnérabilité critique)

| ID | Niveau | Observation | Recommandation |
|----|--------|-------------|----------------|
| S-E3-01 | P3 (faible) | Les jetons d'accès sont en clair dans le fichier JSON configuré (`MILES_WEB_USERS_FILE`) | Documenter la protection par permissions OS du fichier ; acceptable en usage local |
| S-E3-02 | P3 (faible) | Aucune route de déconnexion/révocation proactive côté UI (la TTL de 15 min couvre) | Ajouter `POST /logout` (révocation immédiate) dans une itération UI |
| S-E3-03 | P3 (mineur) | `authenticate()` parcourt les utilisateurs dans l'ordre du dictionnaire (timing sur l'ordre, pas sur le jeton) | Négligeable en local ; constat sans action |

## 2. Autorisations — grants (grants.py) — VERDICT : SOLIDE

Points forts vérifiés :
- Grants liés à **session + mission + outils explicites** (+ racines de chemin optionnelles) ;
- expiration (300 s) + bornage des usages (32) ; consommation **atomique** ;
- en mémoire seulement (invalide au redémarrage) ;
- **le modèle ne fournit jamais un grant** — il est injecté par l'application ;
- le grant ne contourne jamais `ToolPolicy`, il ne remplace que la confirmation
  interactive d'un outil déjà connu.

### Observations résiduelles

| ID | Niveau | Observation | Recommandation |
|----|--------|-------------|----------------|
| S-E3-04 | **P2 (modéré)** | Dans `GrantRegistry.authorize`, si `actor_id` ou `context_id` vaut `None`, le test de liaison session/mission est **sauté** : un grant actif couvrant l'outil est retourné même sans preuve d'appartenance. Le moteur actuel passe toujours `actor_id` (runner, service), mais le contrat `GrantChecker` ne l'exige pas. | Renforcer : retourner `None` si `actor_id is None` (fail-closed), ou documenter l'invariant dans le contrat. **À traiter en correctif ciblé** après revue. |
| S-E3-05 | P3 | `covers_path` sans `allowed_roots` n'impose aucune restriction de chemin supplémentaire (comportement documenté, la politique `app/security/paths` s'applique) | Aucune action ; conforme au design |

## 3. Analyse interne du correctif D1 (runner.py) — CONCLUSION : CORRECT

- **Correctif** : `_ensure_authorization` vérifie désormais le grant avec
  `mission.session_id or self.session_id` (émission et vérification alignées sur la
  session du **client propriétaire** de la mission).
- **Cohérence vérifiée** : `MissionRunner.authorize` émet le grant avec
  `session_id=requester_session_id or mission.session_id` ; l'exécuteur utilise
  `actor_id=mission.session_id or self._session_id` (ligne ~221). Les trois lieux
  sont désormais cohérents.
- **Régression testée** : `tests/test_mission_web_authorization.py` (6 tests) +
  scénario web réel `completed` avec 1 échange (rapport PHASE_6_3B).
- **Réserves** : seule l'analyse **indépendante** (Agent B) peut clore MI-001.

## 4. Verdict global E3

La couche sécurité (Phase 6.1 durcie + D1) est **cohérente et robuste pour un
service strictement local**. Aucune vulnérabilité critique trouvée. Un
renforcement P2 recommandé (S-E3-04, fail-closed sur `actor_id=None`) et deux
P3 documentés. **Aucune opération sensible supplémentaire ne doit être ouverte
sans l'audit indépendant B.**
