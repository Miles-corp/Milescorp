# docs/coordination/STATUS.md — État du projet MILES

## État instantané (2026-10-28, Agent A — lot boîtier fusionné dans `main`)

- **Référence du code** : **`main`**, `dcc3130` = `492ecb3` + fusion `--no-ff` de `feat/miles-box-packages` (`209e39f`). Poussée sur `origin/main`. La branche est conservée, non supprimée.
- **Tests** : **936 exécutés — 936 OK, 0 échec, 5 ignorés** sur la fusion elle-même (Windows 11, Python 3.14.7), 276 s. Contrôles ciblés avant fusion : `test_boxtelemetry` + `test_web_lan` + `test_build_release` = **25 OK** ; `bash -n hardware/packages/pc-miles/install.sh` : **aucune sortie** (la réserve du lot précédent est levée).
- **Audit B** (`M-024`) : **VALIDÉ** sur les trois surfaces — contrat d'écoute (aucun chemin n'active `allow_lan` sans décision humaine ; `0.0.0.0`, `::`, link-local, multicast, noms d'hôte et adresses publiques refusés ; `--web-lan` sans jeton persistant sort en 1 **sans construire de serveur**), relai `/api/box` (cible figée, chemin constant, pas de SSRF, 503 sans valeur), archives (exclusions par segments, `.env.example` conservé).
- **Réserves P3 fermées** (`M-025`) : comparaison de clé à **temps constant** (`hmac.compare_digest` sur octets), convention `.local` documentée et testée ; et un défaut adjacent corrigé — un corps JSON non-objet (`[]`, `null`, `"chaine"`) levait `AttributeError` donc une **500 au lieu d'un 401**.
- **Comptes de tests corrigés** : `TestWebServerLocalOnly` = **14** tests (recompté par lecture du fichier), `tests/test_web_lan.py` = **10**, `test_build_release.py` = **6**, `test_boxtelemetry.py` = **9** — soit les **25** du contrôle ciblé. Le rapport d'audit annonçait 8, `H-015` annonçait 11 pour boxtelemetry : les deux étaient faux.
- **Traçabilité** : la `M-024` d'Agent B n'était pas dans le dépôt (elle porte sur `6f18cd8`, antérieur aux correctifs P3). Elle est **transcrite** dans `MESSAGES.md` avec mention de provenance, et `M-026` demande le contre-audit du seul delta `6f18cd8..209e39f` (+98/−7, 8 fichiers) — c'est la dernière revue ouverte du lot.
- **Revue close** (`M-027`) : Agent B valide `compare_digest` sur octets (clé vide rejetée avant comparaison, longueur bornée par `MAX_BODY`, corps non-objet et clé non-textuelle rejetés par `isinstance`) et juge la convention `.local` suffisante ; ses comptes corrigés (**9 / 10 / 6 / 20**) rejoignent les miens. Sa recommandation résiduelle est appliquée **en plus strict** : `build_release.py` **refuse** (sortie 1, aucune archive créée) un `*.ini` ordinaire contenant un identifiant — `DEC-021`, `TASK-DEV-052`, `test_build_release` passe de 6 à **12** tests.
- **Exécuté, et un défaut trouvé du premier coup** (`DEC-022`) : shell de l'agent rétabli (jonction `usr\usr\bin` vers le bash système). `test_ini_local_ignore` **échouait** — le motif `*.ini.local` ne correspondait pas à `platformio.local.ini`, la convention documentée : **les identifiants WiFi réels partaient dans l'archive**. Corrigé (les deux orthographes exclues, décision dérivée d'`exclure()` au lieu d'un suffixe codé en dur). Preuves : `test_build_release` **12/12** ; archive réelle sans `platformio.local.ini` ; refus **exit 1** sans archive ; suite **942 tests OK, 5 ignorés**.
- **Tâches** : `TASK-DEV-047` **DONE** (fermeture), `TASK-DEV-049`, `TASK-DEV-050`, `TASK-DEV-051` DONE.
- **Reste hors du code** : installation Debian 13 jamais exécutée (procédure prête), firmware jamais flashé.

## Prochain objectif (après la fusion du lot boîtier)

1. **Multi-fournisseurs** : `feature/miles-multi-provider` (`b0ba016`) auditée **sans blocage** (`M-008`), mais non rebasée sur `main` ; les 2 échecs de tests qu'elle présentait sont corrigés sur `main` depuis `DEC-017`.
2. **Validation Debian 13** : [`docs/installation/VALIDATION_DEBIAN_13.md`](../installation/VALIDATION_DEBIAN_13.md) — écrite, **non exécutée**.
3. **Flash du firmware** sur le boîtier réel.
4. Les 10 audits de la Phase 6.3 restent en attente côté Agent B.

## État instantané (2026-10-28, Agent A — écarts DEC-016 fermés, TASK-DEV-050)

- **Branche** : `feat/miles-box-packages`, issue de `main` (`492ecb3`), **non fusionnée**.
- **Tests** : **934 exécutés — 934 OK, 0 échec, 5 ignorés** (Windows 11, Python 3.12).
- **Contrat d'écoute réseau** (`DEC-019`) : `assert_local_host` inchangée ; `assert_listen_host(host, allow_lan=False)` porte le contrat complet. Sans opt-in, seule `127.0.0.1` passe. Avec, une adresse **privée** passe et `0.0.0.0`, `::`, une adresse publique ou un nom d'hôte restent refusés. `allow_lan` n'a pas de setter. `--web-lan` exige un jeton **persistant** + `MILES_WEB_LAN_HOST`, sinon **code de sortie 1 sans serveur** (vérifié en réel, pas seulement en test).
- **Tests du contrat** : les 10 tests de `TestWebServerLocalOnly` sont conservés et **renforcés** (refus de `0.0.0.0` et `::` aussi en mode LAN), **4 ajoutés** (14 au total) ; `tests/test_web_lan.py` en apporte **10**. Comptes revérifiés : le rapport d'audit annonçait 8, ce document 11. Aucune assertion supprimée ni affaiblie.
- **Paquet PC** : `install.sh` exécute le préflight avec `bash` (il le soumettait à `python3`), est idempotent et crée l'utilisateur du service ; `cockpit-launcher.sh` lance le serveur Companion du dépôt au lieu d'un dossier `./cockpit` inexistant ; `miles.service` ne rend plus `.env` inscriptible et interdit explicitement l'ajout de `--web-lan`.
- **Firmware ESP32-S3** : `BACKEND_URL` n'a plus de valeur par défaut (une URL de bouclage est refusée), un marqueur `REPLACE_ME` arrête le démarrage sans tenter de connexion, et **aucune valeur n'est inventée** (un capteur absent n'est pas envoyé). **Compilation réelle : `[SUCCESS]` en 1227,56 s**, image `firmware.bin` de 1 103 072 octets, RAM 14,2 %, Flash 32,5 % (`espressif32@8.0.0`, `toolchain-xtensa-esp-elf@14.2.0`, `framework-arduinoespressif32@4.30312.261024`).
- **Télémétrie du boîtier** : route `/api/box` sur le serveur Companion (même origine, cible figée), consommée par `miles-bridge.js`. Une valeur ne s'affiche que si le backend a répondu, **toujours avec l'âge de la mesure** ; backend muet = 503 et « aucune valeur affichée ».
- **Archives** : `scripts/build_release.py` laissait entrer `.pio/` et `__pycache__/` (comparaison de motifs avec des `/` sur des chemins Windows). Corrigé, mesuré : 3 archives + `SHA256SUMS`, aucune entrée technique. `tests/test_build_release.py` archive un faux paquet piégé et vérifie qu'aucun secret ne sort.
- **Procédure de validation** : [`docs/installation/VALIDATION_DEBIAN_13.md`](../installation/VALIDATION_DEBIAN_13.md) — 12 phases, 15 contrôles, **écrite et non exécutée** (`TASK-DEV-051`).
- **Réserve de vérification à assumer** : `hardware/packages/pc-miles/install.sh` a été corrigé **après** la dernière exécution de la suite (cible `/opt/Milescorp` avec `INSTALL_SERVICE=1`, tests lancés sous l'utilisateur du service, installation de l'unité par `tee`). Ces corrections sont **relues, pas exécutées** : le shell de l'agent était indisponible. À confirmer par `bash -n install.sh`, puis par les phases 2 à 8 de la procédure.
- **Tâches** : `TASK-DEV-049`, `TASK-DEV-050` et `TASK-DEV-051` **DONE**.

## Prochain objectif

1. **Audit B** (`M-023`) sur trois surfaces : contrat réseau, relai `/api/box`, exclusions d'archives. **Rien ne fusionne avant.**
2. **Validation Debian 13** : la chaîne post-D1 n'a jamais tourné dessus. C'est la seule preuve manquante pour « installable sur le mini-PC ». La procédure est prête — [`docs/installation/VALIDATION_DEBIAN_13.md`](../installation/VALIDATION_DEBIAN_13.md) : commandes exactes, sorties attendues, grille de 15 contrôles, limites assumées. **Écrite, non exécutée.**
3. **Flash du firmware** sur le boîtier réel : compilation prouvée, matériel non testé.
4. Reste ensuite : multi-fournisseurs (branche à rebaser) et les 10 audits Phase 6.3.

## État instantané (2026-10-28, Agent A — port du lot boîtier, TASK-DEV-049)

- **Référence du code** : `main` (`492ecb3`) + branche `feat/miles-box-packages`, issue de `main`, **non fusionnée** (`DEC-018`).
- **Tests** : **911 exécutés — 911 OK, 0 échec, 5 ignorés** (Windows 11, Python 3.14.7). 891 (base `main`) + 15 (lot boîtier) + 5 (`tests/test_env_examples.py`).
- **Ce que la branche apporte** : le lot « paquets téléchargeables » (`TASK-DEV-047`) est revenu sur une base saine par **port de fichiers**, pas par merge ni rebase — la branche d'origine avait **49 commits de retard** et 22 d'avance, dont l'essentiel de la documentation réécrite depuis. 15 fichiers portés, aucune modification de `miles.py` ni de `app/interface/web.py`.
- **Défaut réel corrigé pendant le port** : l'exemple `.env` du paquet PC contenait `MILES_PROVIDER=off`, **valeur que `Settings` refuse** (reproduit : `SettingsError: Fournisseur inconnu : 'off'`), et `MILES_API_KEY`, nom qu'aucun code ne lit. `install.sh` le copiant en `.env`, **MILES n'aurait pas démarré après installation**. Exemple régénéré depuis la racine ; garde-fou `tests/test_env_examples.py` (4 vérifications, contrôle négatif prouvé).
- **Tâches** : `TASK-DEV-049` **DONE**, `TASK-DEV-050` **IN_PROGRESS** (écarts restants : contrat LAN, firmware non compilé, `install.sh`, `cockpit-launcher.sh`, `miles.service`, `miles-bridge.js`, renvoi `INSTALL.md`).

## Prochain objectif

- **`TASK-DEV-050` — fermer les écarts du lot boîtier** : réécrire `assert_local_host` et les **10 tests** de `TestWebServerLocalOnly` pour porter le contrat `DEC-016` §2 (local par défaut, LAN refusé sans jeton), corriger les trois scripts du paquet PC, recompiler le firmware, produire les archives.
- **Bloqué par** : l'audit B de l'ouverture réseau (`M-022`, Agent B).
- **En parallèle** : Agent B sur les 10 audits Phase 6.3 (code déjà dans `main`, constats seulement).

## État instantané (2026-10-28, Agent A — lot isolation des tests, TASK-DEV-048)

- **Référence du code** : **`main`**, publiée sur `origin/main` (`dffac9a`), puis ce lot.
- **Tests** : **891 exécutés — 891 OK, 0 échec, 5 ignorés**. C'est la **première suite entièrement verte** depuis la Phase 6.4B : les 2 échecs de `tests/test_status_provider_diagnostics.py` sont expliqués et corrigés.
- **Cause des 2 échecs** : `tests/__init__.py` redirigeait `MILES_ENV_FILE` vers un chemin **fixe** (`%TEMP%\miles_tests_no_such_env_file`) ; ce fichier existait pourtant (97 octets, 2026-10-27 15:14) et contenait `MILES_REMOTE_MODEL=` vide. Ses clés n'existent que sur `feature/miles-multi-provider` : une exécution de cette branche avait écrit son faux `.env` dans le chemin partagé, et toutes les sessions suivantes le lisaient. **Ce n'était pas un défaut du code de `main`**, et aucune assertion n'a été modifiée.
- **Correctifs (DEC-017)** : isolation dans un répertoire `mkdtemp` **unique par session** ; règle **valeur vide = source absente** (processus et `.env`), documentée dans `INSTALL.md` §3ter. Un `MILES_REMOTE_MODEL=` ne produit plus un modèle vide, un `MILES_HISTORY_LIMIT=` ne bloque plus le démarrage.
- **Tâches** : **31 DONE · 17 TODO** — détail dans `TASKS.md`. Publié sur GitHub : `main` et `feature/miles-multi-provider` (les deux seules références qui portaient du travail invisible).

## État instantané (2026-10-27, Agent A — après le lot « tri, `main`, cockpit unique ») — historique

- **Référence du code** : **`main`** — alignée sur `integration/miles-post-d1` par **avance rapide locale**, sans `push` (DEC-004) : **77 commits d'avance sur `origin/main`**. 250 fichiers suivis, 58 fichiers de tests.
- **Tests** : **876 exécutés — 874 OK, 2 échecs, 5 ignorés**. Les 2 échecs (`tests/test_status_provider_diagnostics.py`) sont **reproduits à l'identique dans une copie de `HEAD` sans `.env`** : ils ne viennent pas de ce lot. Le rapport précédent les attribuait au `.env` du poste ; cette vérification ne le confirme pas, la cause exacte reste à déterminer (hors de ce lot).
- **Interfaces** : **une seule implémentation du cockpit** (`assets/web/`), servie depuis deux origines — racine sur `127.0.0.1:8080`, `/cockpit/` sur `127.0.0.1:8787`. `/projet` redirige vers `/cockpit/`. Le bandeau de santé est **visible avant connexion** et n'affirme que ce qui est observable ; les icônes sont locales ; la surface servie par le Companion est **bornée par une liste blanche** (`GET /server.py` → 404, vérifié en direct).
- **Tri** : FontAwesome (1,05 Mo, zéro référence) supprimé ; 12 `.gitkeep` redondants retirés (les 18 marqueurs des emplacements réservés restent) ; page Projet dupliquée retirée. Carte du dépôt : `ORGANISATION.md`.
- **Worktrees** : **2 restants** — ce poste de travail (`main`) et le clone principal `C:\Users\StanC\Desktop\Milescorp`. Les deux dossiers `%TEMP%` sont retirés **après sauvegarde** : rapport récupéré dans la référence, 433 lignes de travail multi-fournisseurs commitées sur `feature/miles-multi-provider` (**non intégré, non vérifié**). Plus aucun travail hors de Git.
- **Tâches** : **29 DONE · 2 DONE (analyse rendue, puis implementation TASK-DEV-026) · 1 DONE (tests) · 17 TODO** — détail dans `TASKS.md`.

## Prochain objectif

- **Phase 7 — cockpit web de contrôle du projet** (`TASK-DEV-043`, Agent A) : **terminée** le 2026-10-27 (31 tests dédiés, audit design du Lab 100/100, vérification navigateur réelle). Rapport `docs/reports/PHASE_7_COCKPIT_AGENT_A.md`. Branche `feat/miles-cockpit-ui`, aucune fusion.
- **Audits Agent B en attente de décision** : `TASK-DEV-019`, `021`, `024`, `027`, `030`, `032`, `034`, `037`, `039`, `041`.
- **Tri Git** : liste de suppression (branches fusionnées + worktrees temporaires) à valider avant exécution.
- **Réalignement de `main`** sur l'intégration : opération locale d'abord, aucun push sans accord (DEC-004).

## Tâches actives (extrait)

| ID | Titre | Statut | Assigné à |
|----|-------|--------|-----------|
| TASK-DEV-043 | Phase 7 : cockpit web de controle du projet | DONE | Agent A |
| TASK-DEV-019 | Audit independant de la correction D1 (Phase 6.3b) | TODO | Agent B |
| TASK-DEV-041 | Audit independant du correctif memoire (D-MEM-01) | TODO | Agent B |
| TASK-DEV-039 | Audit independant de la Mission P1 | TODO | Agent B |
| TASK-DEV-007 | MILESTONE-007 : Fournisseur local hors ligne (RTX 3050) | TODO | Agent A |
| TASK-002 a TASK-004 | Revue independante de l'organisation | TODO | Agent B |

## Blocages

- Aucun blocage technique.
- Limite assumée : la validation sur Debian 13 reste non faite sur ce poste (VM d'audit injoignable les 2026-10-21 et 2026-10-24).
- Limite assumée : les 2 échecs de tests sont dus au fichier `.env` du poste, pas au code ; ils sont documentés et reproductibles.

## Phase 6.3b — Correction D1 : autorisation des missions web (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md`
- **Branche** : `fix/miles-d1-web-authorization` (base `fc179ca`, commit de correction `6b736d7`, pousse sur `origin`). **Aucune fusion.** `main` (`b9b7e7d`) et `origin/integration/miles-phases-5-6-6-1` (`69bf670`) sont inchanges.
- **Defaut corrige (D1)** : `app/orchestration/runner.py::_ensure_authorization` interrogeait le registre d'autorisations avec la **session du runner** (session de l'application) alors que le grant est emis pour la **session du client proprietaire** de la mission (`mission.session_id`). Les deux coincident en CLI, mais pas en web : le grant web legitime etait refuse, la mission soulevait une nouvelle demande d'autorisation en boucle jusqu'a l'epuisement du budget d'echanges.
- **Correctif** : une seule ligne — `mission.session_id or self.session_id`. Coherent avec l'emission du grant et avec l'executeur (`app/orchestration/executor.py:221`, `actor_id=mission.session_id or self._session_id`). Aucun autre defaut touche (D2, D3, D4 et le code de securite sont hors perimetre).
- **Tests ajoutes** : `tests/test_mission_web_authorization.py` (6 tests) — regression D1, mission web autorisee qui se termine, mission web sans autorisation valide qui ne continue pas (0 etape, 0 grant), autorisation non reutilisable depuis une autre session, mission d'un autre utilisateur refusee, invariant du runner. Le test de regression **echoue sans le correctif** (verifie explicitement).
- **Controles executes** : 6/6 tests de regression ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security_phase6_1` 35/35 ; suite complete **534 tests OK (4 ignores, plateforme Windows)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; **scenario web reel** (vrai serveur `miles.py --web`) : mission `completed`, 5 etapes, 5 appels d'outils, **1 echange** (avant : boucle jusqu'a `interaction_budget_exceeded`). Bases de test isolees et supprimees.
- **Defaut connexe signale, non corrige (D1-bis)** : `POST /mission/<id>/authorize` renvoie `{"approved": true}` meme avec un jeton d'approbation invalide (validation faite dans le fil d'execution, exception journalisee et non retournee). **Aucune elevation de privilege** : l'autorisation n'est pas accordee, aucun grant n'est emis, la mission ne continue pas. Correctif separe propose (validation synchrone du jeton dans `WebApp.authorize_mission`).
- **Limites** : aucune validation Debian 13 (environnement indisponible) ; les tests ignores sont des limites de plateforme Windows.
- **En attente** : audit independant par Agent B (TASK-DEV-019) avant toute fusion.

## Phase 6.3c — Correction D2 (chemins Windows) et analyse D3 (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3C_D2_WINDOWS_PATHS_AGENT_A.md`
- **Branche** : `fix/miles-windows-paths` (base `3a59dae` = tete de `fix/miles-d1-web-authorization`, qui porte le correctif D1). **Aucune fusion.** `main` (`b9b7e7d`), `origin/integration/miles-phases-5-6-6-1` (`69bf670`) et `fix/miles-d1-web-authorization` (`3a59dae`) sont inchanges. Travail effectue dans un **worktree isole** (`C:\Users\StanC\AppData\Local\Temp\miles-d2`) : le checkout principal et son artefact non suivi (`tatus --short--branch`) n'ont pas ete touches.
- **Defaut corrige (D2)** : `app/orchestration/planner.py::extract_target_path` perdait la lettre de lecteur d'un chemin Windows absolu (`C:/Windows` -> `/Windows`). Un chemin sans lettre de lecteur n'est plus absolu : il est resolu comme racine du lecteur **courant**. Mesure : `D:\donnees\rapports` etait servi par `C:\donnees\rapports` (autre repertoire, parfois dans le perimetre) ; le refus de perimetre citait `/Windows/System32` au lieu de `C:/Windows/System32`.
- **Correctif** : `app/orchestration/planner.py` uniquement — conservation de la lettre de lecteur, restauration du tiret dans les segments, espaces internes (mot contenant un separateur, ou mot capitalise sur un chemin Windows absolu), chemins entre guillemets, prefixe de marqueur ignore, `C:` seul non retenu. **Aucune modification de la politique de securite ni du perimetre** : le confinement (`app/security/paths.py`) reste le seul juge.
- **Tests** : `tests/test_windows_paths.py` (21 tests) — chemins absolus Windows, chemins avec espaces, chemins relatifs, chemins POSIX, non-regression, et confinement (hors perimetre, traversee, entrees malformedes, racines inchangees) ; **9 tests echouent sans le correctif** (verifie par `git stash`). Suite complete **555 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; verification manuelle CLI (chemin absolu -> `completed`, chemin avec espaces -> `completed`, hors perimetre -> `failed` avec le vrai chemin dans le message).
- **D3 — analyse seule, aucune modification** : `app/tools/policy.py` applique un controle par sous-chaine aux VALEURS ; les faux positifs sont confirmes (`source`, `code`, `script`, `python`, `javascript`) **et la meme famille existe dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`)**. Strategie proposee : conserver le controle exact sur les CLES, appliquer au parametre de type chemin un controle structurel (metacaracteres) au lieu du controle par sous-chaine, inchange pour toute valeur non chemin, et sur les trois validateurs. Deux voies : **2-a typage explicite du parametre chemin (recommandee)** ou 2-b heuristique (deconseillee). Cas qui doivent rester bloques et cas qui doivent etre acceptes lists dans le rapport.
- **Limites** : un chemin dont le dernier segment porte des espaces en minuscules n'est reconnu qu'entre guillemets ; aucun test Debian 13 (environnement indisponible) ; D1-bis et D4 toujours non corriges.
- **En attente** : audit independant par Agent B (TASK-DEV-021) et decision sur la voie de correction de D3 (TASK-DEV-022).

## Phase 6.3d / 6.3e — Correction D1-bis et analyse D3 (Agent A, 2026-10-21)

- **Rapports** : `docs/reports/PHASE_6_3D_D1BIS_AGENT_A.md` (D1-bis) et `docs/reports/PHASE_6_3E_D3_ANALYSIS_AGENT_A.md` (D3, analyse seule).
- **Branche** : `fix/miles-d1bis-authorization-response` (base `d3240d2` = tete de `fix/miles-windows-paths`, qui porte D1 et D2). **Aucune fusion.** `main` (`b9b7e7d`), `origin/integration/miles-phases-5-6-6-1` (`69bf670`), `fix/miles-d1-web-authorization` (`3a59dae`) et `fix/miles-windows-paths` (`d3240d2`) sont inchanges. Travail en **worktree isole** (`Temp\miles-d1bis`).
- **D1-bis corrige** : `POST /mission/<id>/authorize` repondait **200 `{"approved": true}`** meme avec un jeton invalide : la validation du jeton avait lieu dans le FIL d'execution, dont l'exception (`MissionAuthorizationError`) etait journalisee et absorbee, et le `try/except` place autour du *demarrage* du fil ne pouvait rien intercepter. Le defaut est **pre-existant** (branches D1 et D2), la propriete de securite n'etait pas violee (0 grant, 0 etape sensible executee).
- **Correctif** : validation **synchrone** du jeton, de l'expiration et de la session via la nouvelle methode `MissionRunner.check_authorization` (source de truth unique, `authorize()` l'appelle) ; `MissionAuthorizationError` porte un code de raison stable et non sensible ; reponses explicites : **403** (jeton invalide / expire / absent, autre session, autre utilisateur, mission terminee ou inconnue) avec `reason`, **409** (`mission_busy`) si l'action n'a pas ete appliquee. Fichiers modifies : `app/interface/web.py`, `app/orchestration/runner.py`.
- **Variante trouvee (D1-ter, signalee, cause racine NON corrigee)** : une autorisation recue pendant que la mission termine son rapport (appel au fournisseur IA) etait **silencieusement ignoree** (`_start_mission_thread` ignore l'action si un fil est actif), et la reponse annoncait un succes. La reponse est desormais honnete (409) ; la correction racine (ne pas interroger le fournisseur pour une mission en attente) est **proposee** dans le rapport D1-bis §6.1.
- **Tests** : `tests/test_mission_authorize_response.py` (20 tests) — autorisation valide, jeton invalide, jeton expire, autre session, autre utilisateur, mission terminee, mission inconnue, jeton d'une autre mission, jeton absent, non-divulgation du jeton/de la session, mission en cours (409) ; aux niveaux appel direct et **HTTP reel**. **15 tests echouent sans le correctif** (verifie par `git stash`). Suite complete **575 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** (dont le test qui inspecte le code source de `authorize_mission`) ; scenario web reel : 403 (jeton invalide) -> 409 x2 -> 200 -> mission `completed`.
- **D3 — analyse seule, AUCUNE modification de securite** : le controle par sous-chaine applique aux VALEURS dans `app/tools/policy.py` refuse les chemins legitimes (`source`, `code`, `script`, `python`, `javascript`) **et la meme famille existe dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`)**. Faits etablis : l'application ne declare que **2 parametres de type chemin** (`action_list_files.path`, `action_read_file.path`) et le moteur dispose deja de la definition d'outil au point ou la politique est appliquee → le **typage explicite est trivialement applicable** ; les tests existants n'echouent pas le comportement fautif (seulement des cas de cles) → le correctif est possible sans changer les attentes. Deux voies proposees (2-a : la politique ignore les valeurs de chemin ; 2-b : filtrage avant la politique, `policy.py` non modifie — **recommandee**) ; matrice de 29 tests (18 doivent rester refuses, 11 doivent etre acceptes) ; 7 risques de contournement analyses. Aucune ecriture dans `app/tools/policy.py`.
- **Limites** : aucune validation Debian 13 ; D3 non corrige (decision d'Agent B requise) ; D1-ter cause racine non corrigee ; le jeton d'approbation reste contournable par le proprietaire via `/mission/<id>/answer` (comportement preexistant, signale).
- **En attente** : audit independant par Agent B (TASK-DEV-024) et decision D3 (TASK-DEV-025).

## Phase 6.3f — Correction D3 : typage explicite des paramètres de chemin (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3F_D3_IMPLEMENTATION_AGENT_A.md`
- **Base retenue** : `1ef4878` (`fix/miles-d1bis-authorization-response`) — la tete la plus recente (D1 + D2 + D1-bis). `main` (`b9b7e7d`) ecartee : elle ne contient pas `app/tools/builtin.py`. Branche d'integration `69bf670` ecartee (anterieure aux correctifs en vol). **Aucune fusion.**
- **Branche** : `fix/miles-policy-path-typing`, poussee sur `origin`. Travail en **worktree isole** (`Temp\miles-d3`) ; le checkout principal, son artefact non suivi et les bases du developeur n'ont pas ete touches.
- **Defaut corrige (D3)** : la politique appliquait un controle par sous-chaine aux VALEURS, y compris aux chemins : `C:\dev\source`, `Documents\code`, `C:\Python39\Lib` etaient refuses, et toute mission sur un tel repertoire etait impossible. Meme famille dans les controles shell (`system`, `run`, `command`, `exec`) et secrets (`secret`).
- **Correctif** : 4 fichiers — `app/tools/registry.py` (`ToolParameter.is_path`), `app/tools/builtin.py` (2 marqueurs), `app/tools/policy.py` (controle **structurel** des valeurs de chemin + factorisation des trois validateurs), `app/tools/engine.py` (transmission du typage declare). **`app/security/paths.py` n'est PAS modifie** ; le planificateur n'est pas modifie (son controle porte sur des motifs de commandes, sans faux positif). L'exemption exige **simultanement** un parametre **declare** chemin **et** une chaine directe ; elle ne s'applique ni aux valeurs libres, ni aux structures imbriquees, ni aux parametres non declares.
- **Garanties verifiees (9)** : G1 cles interdites toujours interdites ; G2 valeurs libres toujours controlees ; G3 chemins valides structurellement ; G4 exemption bornee ; G5 confinement inchange (un chemin accepte par la politique est refuse par `resolve_authorized_path` hors racines) ; G6 traversees refusees ; G7 lectures inchangees (fichiers sensibles refusés) ; G8 aucun outil, permission ni racine nouveau ; G9 les trois niveaux (politique / validation du chemin / autorisation effective) sont distincts et testes separement.
- **Tests** : `tests/test_policy_path_typing.py` (40 tests, 3 niveaux) — **3 echouent sans le correctif** (revert de `app/tools/engine.py` : le defect D3 reapparait au niveau outil) ; suite complete **615 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; `test_tool_policy` 11/11, `test_tool_engine` 26/26, `test_tool_integration` 40/40, `test_path_security` 21/21 (3 ignores), `test_web_security_phase6_1` 35/35, `test_web_security` 33/33, non-regression D1 (6), D1-bis (20), D2 (21).
- **Matrice de 29 cas de l'analyse D3 verifiee contre le code reel** : deux attentes etaient erronees (la politique detecte des MOTS, pas des motifs de code ; les cles imbriquees ne sont pas vues par la politique) — corrigees dans la suite et signalees.
- **Points signales, non corriges (hors perimetre)** : (1) `_iter_keys` ne descend pas dans les valeurs : une cle interdite imbriquee n'est pas vue par la politique (fermee par le schema) ; (2) la politique ne detecte pas les fragments de code sans mot interdit (« import os ») ; (3) D1-ter et le contournement du jeton via `/mission/<id>/answer` (rapport D1-bis).
- **Limites** : aucune validation Debian 13 ; aucun appel API payant ; aucun acces a un fournisseur distant ; seule une directory temporaire de test est creee puis supprimee.
- **En attente** : audit independant par Agent B (TASK-DEV-027). L'audit D3 n'est **pas** considere comme approuve.

## Phase 6.3h — Correctifs A-alpha et B-alpha (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3H_ANSWER_D1TER_FIX_AGENT_A.md`
- **Base** : `0be08cd` (`fix/miles-policy-path-typing`, qui porte D1 + D2 + D1-bis + D3). Branche : `fix/miles-answer-d1ter`, poussee sur `origin`. **Aucune fusion** ; `main` (`b9b7e7d`), l'integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`) et D3 (`0be08cd`) sont inchanges. Travail en **worktree isole** (`Temp\miles-answer`).
- **A-alpha** : `POST /mission/<id>/answer` repondait 200 `{"answered": true}` meme lorsque la reponse etait **refusee dans le fil** (session differente, budget epuise, demande expiree) : l exception etait absorbee par le fil. Nouvelle methode `MissionRunner.check_answer` (modele D1-bis, source de verite unique, appellee par `answer`) ; l interface web valide **de facon synchrone** avant de lancer le fil et renvoie 403 + `reason` (mission inconnue, mission terminee, aucune demande en attente, autre session, autre utilisateur, demande expiree, budget epuise) ; 409 conserve pour le cas « mission occupee ». **Le contrat de la route est inchange : aucun jeton n est exige (A-beta NON applique).**
- **B-alpha** : l analyse qualitative IA n est plus demandee pour une mission **en attente** (une seule ligne dans `_execute_loop`) : le fil se termine des la demande d autorisation, la fenetre pendant laquelle une autorisation etait ignoree **disparait**. Effet de bord assume : le compte rendu **provisoire** d une mission en attente ne comporte plus la section « Analyse qualitative » ; le compte rendu **definitif** la conserve (verifie par test). Le 409 reste comme filet.
- **Tests** : `tests/test_answer_d1ter_fixes.py` (18 tests de regression, non destructifs : outils simules, fournisseur simule, aucun appel reseau, aucune donnee reelle). **7 tests echouent sans A-alpha** (revert de `app/interface/web.py`) et **1 sans B-alpha** (neutralisation ciblee) : la reintroduction des defauts est donc detectee. Suite complete **633 tests OK (4 ignores)** ; **70 tests d audit Agent B rejoues tels quels : OK (2 ignores)** ; non-regression D1 (6), D1-bis (20), D2 (21), securite web (35 + 33), orchestrateur (73), bornes (20), politique (11), confinement (21, 3 ignores), moteur (26), integration outils (40).
- **Perimetre respecte** : ni la politique de securite, ni les permissions, ni le confinement des chemins (`app/security/paths.py` intact), ni le planificateur, ni les outils. Aucun appel API payant, aucune donnee reelle lue ni ecrite.
- **Interactions avec les audits en cours** : D1 doit etre fusionne **avant** ce correctif (le refus cross-session repose sur son controle de session) ; D1-bis touche les **memes fichiers** (`runner.py`, `web.py`) mais dans des hunks distincts, avec un **conflit de contexte possible sur le bloc d imports** des constantes `REASON_*` (a resoudre manuellement, sans risque semantique) ; D2 et D3 n ont aucun fichier commun.
- **En attente** : audit independant d Agent B (TASK-DEV-030) et decision sur l option **A-beta** (exiger le jeton sur `/answer` : changement de contrat d API, non applique).

## Phase 6.3i — D-B05 (persistance des missions) et validation D-B01 (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3I_MISSION_PERSISTENCE_AGENT_A.md`
- **Base** : `25baa60` (`fix/miles-answer-d1ter` : D1 + D2 + D1-bis + D3 + A-alpha/B-alpha). Branche : `fix/miles-mission-persistence-owner`. **Aucune fusion** ; `main` (`b9b7e7d`), l integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`), A-alpha/B-alpha (`25baa60`) sont inchanges. Travail en **worktree isole** (`Temp\miles-persist`) ; artefact non suivi et bases du developeur preserves.
- **Point de vigilance (etat reel releve)** : la branche d audit d Agent B a **BOUGE** depuis les travaux precedents : `origin/audit/agent-b-phase6-1-web-security-review` est desormais a **`fd25a26`** (« audit contradictoire »), et non plus `ac627df`. Ce rapport porte sur l arbre Phase 5/6/6.1, en amont de nos correctifs : il **ne contredit aucun constat** et ne signale **aucune regression** sur D1, D2, D1-bis, D3 ou A-alpha/B-alpha. Aucune suspension n est donc appliquee.
- **Examen des six defauts D-B01 a D-B06 sur le code reel de la base** : D-B01 **corrige** par le typage explicite (branche D3) ; D-B03, D-B04 et D-B06 **corriges** par les phases 6.1/6.2 (bornes portees par la mission, borne d interactions dans l orchestrateur, lanceur `miles.py --web`) ; D-B02 **reserve de conception assumee** (le `session_id` reste un jeton porteur : composant d authentification en audit, non modifie) ; D-B05 **partiellement ouvert**.
- **D-B05 corrige** : (1) `MissionRunner.list_missions` ne listait que les missions **en memoire** (les missions d une session precedente disparaissaient de la liste au redemarrage) ; (2) constat complementaire : le **proprietaire** (`owner_user_id`) etait serialise par le modele mais **jamais ecrit** par le magasin — au rechargement, le proprietaire valait `""` et la condition de garde de la separation entre utilisateurs ne tenait plus. Correctif : colonne `owner_user_id` + migration `ALTER TABLE` idempotente (SCHEMA_VERSION 3), ecriture et lecture du proprietaire, filtrage par proprietaire dans `MissionStore.list_missions`, combinaison memoire + base dans `MissionRunner.list_missions` (deduplication, tri, limite). **Ni la politique de securite, ni les permissions, ni le confinement des chemins, ni les routes d autorisation ne sont modifies.**
- **D-B01 valide** : reproduction **exacte** du constat de l audit dans un depot place dans un chemin contenant `code` : base `1ef4878` (avant D3) → **2 echecs**, exactement `test_lecture_d_un_fichier_volumineux` et `test_resultat_volumineux_au_dela_du_tampon` (les deux tests cites par l audit) ; base `0be08cd` (avec D3) → **615/615 OK**. Le test de non-regression demande par l audit (`test_chemin_legitime_contenant_code_accepte`) est ajoute et **ne depend pas de l emplacement du depot**.
- **Tests** : `tests/test_mission_persistence_owner.py` (9 tests) — **3 echouent sans le correctif** (revert du magasin et du runner) ; suite complete **642 tests OK (4 ignores)** ; **70 tests d audit Agent B rejoues tels quels : OK (2 ignores)** ; non-regression orchestrateur (73), bornes (20), D1-bis (20), D1 (6), D2 (21), D3 (40), securite web (35).
- **Limites** : les missions enregistrees avant la migration n ont pas de proprietaire connu : elles n apparaissent pas dans la liste filtree par utilisateur (choix sur : ne pas attribuer un proprietaire inconnu) mais restent visibles dans la liste non filtree (console locale) ; les points D-B05 restants (`results` non persistes, etape `RUNNING` non reprise) ne sont pas traites ; aucune validation Debian 13.
- **En attente** : audit independant d Agent B (TASK-DEV-032). Les audits en cours ne sont pas considers comme approuves ; aucune fusion.

## Phase 6.3j — Persistance des resultats et reprise des missions interrompues (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_3J_RESULTS_RECOVERY_AGENT_A.md`
- **Base (reference de lecture, non modifiee)** : `79692fe` (`fix/miles-mission-persistence-owner`). Branche : `fix/miles-results-persistence`. **Aucune fusion** ; `main` (`b9b7e7d`), l integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`), A-alpha/B-alpha (`25baa60`) sont inchanges. Travail en **worktree isole** (`Temp\miles-results`) ; artefact non suivi et bases du developeur preserves.
- **Diagnostic** : le dictionnaire `results` etait une variable locale de `_execute_loop` ; apres une reprise, les etapes dependantes ne resolvaient plus leur source et etaient **sautees** (la mission finissait en `partial` sans ses dernieres etapes). Point cle : le resultat d une etape est **deja persiste** dans le plan (`PlanStep.result` -> `plan_json`) : **aucun changement de schema n est necessaire**, le dictionnaire se reconstruit depuis le plan. Une etape laissee en `RUNNING` (arret du programme pendant son execution) n etait ni rejouee ni signalee.
- **Correctifs** : (1) `results` reconstruit depuis le plan persiste au debut de la boucle ; (2) `resume()` distingue l etape interrompue : rejouee si l outil est declare **SANS EFFET** par l application (`ToolDefinition.read_only`, faux par defaut), sinon marquee **UNCERTAIN** et **jamais rejouee** (note « interrompue : resultat incertain, action non rejouee, verification requise ») ; (3) les cinq outils de lecture seule sont declares sans effet (la liste `READ_ONLY_TOOLS` reste la reference).
- **Garantees** : budget global preserve (la reprise consomme une etape et un appel de plus) ; isolation par proprietaire et controles d autorisation inchanges (la reprise passe par `runner.resume()`) ; politique de securite, confinement des chemins et routes d autorisation **non modifies** ; la declaration `read_only` est une affirmation de l application, fausse par defaut.
- **Tests** : `tests/test_mission_results_recovery.py` (12 tests, deterministes : outils simules, magasin temporaire, compteur d appels par fichier car le moteur execute les outils dans un processus separe) — **4 echouent sans le correctif** (revert de `app/orchestration/runner.py`) ; suite complete **654 tests OK (4 ignores)** ; **70 tests d audit Agent B rejoues tels quels : OK (2 ignores)** ; non-regression orchestrateur (73), bornes (20), D1-bis (20), D1 (6), D2 (21), D3 (40), securite web (35), moteur (26), integration outils (40), politique (11), confinement (21, 3 ignores).
- **Limites** : la declaration `read_only` est une affirmation de l application (faux par defaut) ; la reprise d une etape de lecture relit la donnee (resultat plus frais, pas faux) ; le budget global peut etre atteint par la reprise (comportement voulu) ; un outil a effet interrompu laisse la mission en `partial` avec une etape incertaine ; aucune validation Debian 13 ; aucun appel API payant, aucune donnee reelle lue ni ecrite.
- **Interactions** : aucun conflit de code avec D1, D2, D1-bis et A-alpha/B-alpha ; **D3 touche les memes fichiers de schema d outils** (`app/tools/registry.py`, `app/tools/builtin.py`) mais des hunks differents (champ `ToolParameter.is_path` vs champ `ToolDefinition.read_only`) → fusionner D3 **avant** ou simultanement, en verifiant le hunk. L audit contradictoire (`fd25a26`) ne contredit aucun constat et ne signale aucune regression.
- **En attente** : audit independant d Agent B (TASK-DEV-034). Les audits en cours ne sont pas consideres comme approuves ; aucune fusion.

## Phase 6.4a — Mémoire persistante : isolation par utilisateur (Agent A, 2026-10-21)

- **Rapport** : `docs/reports/PHASE_6_4A_MEMORY_PERSISTENCE_AGENT_A.md`
- **Base** : `54bd138` (`fix/miles-results-persistence`). Branche : `fix/miles-memory-persistent`. **Aucune fusion** ; `main` (`b9b7e7d`), l'integration (`69bf670`) et les branches D1 / D2 / D1-bis / D3 / A-alpha-B-alpha / D-B05 / D-B05-restants sont inchangees. Travail en **worktree isole** (`Temp\miles-memory`) ; artefact non suivi et bases du developeur preserves.
- **Etat initial reel** : `/remember`, `/memory`, `/forget` sont **operationnels** (console et web) ; le stockage est une base SQLite locale (`data/memory.db`, tables `memories` et `preferences`) ; les souvenirs **persistent** apres fermeture (fichier) ; le lien avec l'historique de conversation est **inexistant** (choix d'origine : le stockage est exclusivement a la demande) ; le lien avec l'**identite de l'utilisateur** est **inexistant** (aucune occurrence de `user_id` / `session` / `identity` dans `app/memory/persistent.py`).
- **Defaut D-MEM-01 CONFIRME (P2)** : les souvenirs n etant rattaches a personne, **tout utilisateur authentifie voit et peut supprimer les souvenirs des autres** (interface web multi-utilisateurs). L exploitation suppose un acces local au poste ; l impact porte sur la confidentialite entre utilisateurs, pas sur l acces a distance. 4 tests en erreur avant correction.
- **Correctif** : `app/memory/persistent.py` — colonne `owner_user_id` + **migration sans perte de donnees** (les souvenirs existants restent partages, non attribues arbitrairement), `add_memory` / `list_memories` / `get_memory` / `delete_memory` acceptent un propriétaire et filtrent ; `app/interface/web.py` — la session est propagee jusqu aux handlers de memoire ; `app/interface/cli.py` — **inchange** (console locale mono-utilisateur, souvenirs partages). Ni les routes d autorisation, ni les controles de chemins D2, ni la politique de securite ne sont modifies.
- **Tests** : `tests/test_memory_persistence.py` (17 tests) couvrant les 7 exigences de la mission (enregistrer, retrouver, supprimer, redemarrage, supprime-ne-reapparait-pas, base absente/vide/endommagee, isolation des utilisateurs) et les trois commandes de la console ; **4 echouent sans le correctif** ; suite complete **671 tests OK (4 ignores)** ; **70 tests d audit Agent B OK (2 ignores)** ; non-regression des suites memoire, web, CLI, entree, configuration et defauts Agent B.
- **Limites** : base non chiffree ; souvenirs « partages » (proprietaire vide) visibles de tous ; **lien souvenirs / historique toujours inexistant** ; filtre anti-secret base sur une liste de mots ; **Debian 13 non teste** (VM d audit injoignable : connexion refusee) — la validation Debian 13 n est donc pas declaree.
- **Catalogue** : ligne « Memoire persistante » ajoutee au catalogue du guide (etat : operationnelle, isolation par utilisateur) + section §4.11 (procedure et limites).
- **En attente** : audit independant d Agent B (TASK-DEV-030) et decision sur les deux sujets d architecture ouverts (lien a l historique, chiffrement). Aucune fusion.

## Blocages

Aucun blocage à ce jour.

## Phase 5 — Intégration du moteur d'outils (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_5_TOOL_ENGINE_INTEGRATION_AGENT_A.md`
- **Branche** : `feature/miles-tool-engine-integration` (base `bccdc1c` = branche V1). Aucun merge sur `main`.
- **Constat initial** : le moteur d'outils de la Phase 4 existait mais n'était branché nulle part (registre vide en production, `propose_action()` jamais appelé, aucune route web).
- **Livré** : `ToolService` commun (CLI + web, zéro doublon), 4 outils enregistrés réellement implémentés (`status_read`, `action_datetime`, `action_workdir`, `action_list_files`), CLI `/tools` et `/tool`, web `GET /tools` et `POST /tool` + panneau HTML, confirmation humaine explicite pour les actions MEDIUM.
- **Tests** : 40 nouveaux tests (`tests/test_tool_integration.py`), **378 tests OK** sur Windows (0 échec, 4 ignorés — limites plateforme connues).
- **À faire par Agent B** : validation sur Debian 13 (4 tests ignorés + symlink), revue indépendante du câblage de la confirmation.
- **Point de vigilance** : le jeton de confirmation est lié à l'outil et aux paramètres mais **pas à une identité utilisateur** ; à traiter avant toute exposition des outils au modèle. **Corrigé en Phase 6** (voir ci-dessous).

## Phase 6 — Orchestrateur de missions (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_6_MISSION_ORCHESTRATOR_AGENT_A.md`
- **Branche** : `feature/miles-mission-orchestrator` (base `a11ab4a` = Phase 5, elle-même based on `bccdc1c`). Aucun merge sur `main`.
- **Constat initial** : le moteur d'outils était utilisable mais il n'existait aucune capacité d'orchestration ; le jeton de confirmation n'était lié ni à l'utilisateur ni à un contexte (défaut signalé par le rapport de la Phase 5).
- **Livré** :
  - `app/orchestration/` — mission, plan, planificateur (déterministe + IA validé), exécuteur, observateur, `MissionRunner`, persistance SQLite (`data/missions.db`), compte rendu structuré ;
  - **correctif de sécurité** : `app/tools/grants.py` — autorisations liées à la session **et** à la mission, expirantes, bornées en usages, révocables ; les jetons de confirmation du moteur sont désormais liés au contexte et à la session ;
  - extension lecture encadrée : `action_read_file` (MEDIUM, permission existante `lecture_systeme`, fichiers sensibles refusés, lecture bornée, contenu expurgé) et listing borné en profondeur ;
  - CLI : `/mission`, `/missions`, `/mission-status`, `/mission-answer`, `/mission-cancel`, `/mission-resume` ;
  - web : `POST /mission`, `GET /missions`, `GET /mission/<id>`, `POST /mission/<id>/authorize`, `POST /mission/<id>/answer`, `POST /mission/<id>/cancel` (exécution en fil séparé, anti-double-exécution).
- **Tests** : 73 nouveaux tests (`tests/test_mission_orchestrator.py`), **451 tests OK** sur Windows (0 échec, 4 ignorés — limites plateforme connues).
- **À faire par Agent B** : validation sur Debian 13, revue indépendante de la chaîne d'autorisation (grant → moteur → outil) et de la reprise de mission.
- **Point de vigilance** : l'identité de session est un jeton aléatoire par exécution de l'application, **pas** une identité humaine authentifiée ; le serveur web est local et sans authentification. À traiter avant toute exposition à un utilisateur distant.

## Phase 6.1 — Correction des P1 de sécurité web (Agent A, 2026-10-20)

- **Rapport** : `docs/reports/PHASE_6_1_WEB_SECURITY_FIX_AGENT_A.md`
- **Branche** : `fix/miles-web-authorization-security` (base `0754032` = Phase 6 auditee par Agent B). Aucun merge sur `main`.
- **Défauts corrigés** :
  - **P1-6-03** — protection des routes modifiantes : contrôle d'origine (403), type de contenu JSON (415), session authentifiée (401), jeton CSRF lié à la session (403) ; refus **avant** toute lecture de corps et tout effet de bord.
  - **P1-6-06** — autorisation de mission : propriétaire authentifié + jeton d'approbation lié à la demande (imprévisible, expirant, à usage unique) ; un jeton n'est jamais déduit d'un identifiant de mission.
  - **P1-6-02 résiduel** — session **par client** (le jeton de confirmation d'un client n'est pas rejouable par un autre).
  - **P2-6-04** — contexte multiprocessing explicite (`forkserver`/`spawn`).
  - **P3-6-11** — table `mission_events` alimentée. **P3-6-12** — `python miles.py --web` lance l'interface web et affiche le jeton d'accès.
- **Modèle d'authentification** : jeton porteur explicite (`MILES_WEB_AUTH_TOKEN` ou `MILES_WEB_USERS_FILE`), session par client (256 bits, 30 min), jeton CSRF distinct par session, comparaison en temps constant, blocage après 5 échecs. **Sans identifiant configuré, l'interface web est fermée.**
- **Tests** : 35 nouveaux tests de sécurité + 2 de non-régression ; **488 tests OK** sur Windows (0 échec, 4 ignorés). Les 47 tests d'audit d'Agent B ont été exécutés tels quels : **5 « unexpected success »** (les P1 sont corrigés), 4 échecs d'adaptation documentés (routes désormais authentifiées), 1 expectedFailure inchangé.
- **Défaut préexistant découvert et corrigé** : tout résultat d'outil > 8 Kio expiraient à tort (tampon de tube) — le moteur consomme désormais la file pendant l'exécution de l'enfant. Mission d'analyse : 21 s → 1,3 s.
- **À faire par Agent B** : adapter les 4 tests d'audit concernés, valider sur Debian 13 (contexte `forkserver`), re-auditer la chaîne d'autorisation.
- **Point de vigilance** : le jeton porteur n'est pas un mot de passe ; pas de rotation ni de 2FA ; le serveur reste local. P2-6-07/P2-6-08 (bornes par mission et non par boucle) restent à traiter dans une branche dédiée.

## Décisions récentes

- DEC-001 à DEC-004 acceptées (voir `docs/coordination/DECISIONS.md`).
- DEC-005 : Architecture hybride distant/local avec sélection explicite (ACCEPTEE, Agent A).
- DEC-006 : Mémoire persistante locale SQLite (ACCEPTEE, Agent A).
- DEC-007 : Interface web http.server sur 127.0.0.1, zéro dépendance supplémentaire (ACCEPTEE, Agent A).
- DEC-008 : Couche métier unique `ToolService` partagée par le CLI et l'interface web pour le moteur d'outils (ACCEPTEE, Agent A).
- DEC-009 : Autorisations liées à la session et à la mission, confirmations contextuelles, mission pilote strictement en lecture seule (ACCEPTEE, Agent A).

## Audit final Agent A (MISSION 004A)

- Rapport : `docs/reports/AUDIT-TASK-DEV-003.md`
- Résultat : TASK-DEV-003 marqué DONE par Agent B avec réserves (tests exécutés sur Windows Python 3.14.7, pas sur Debian 13).
- Critères PASS : tests unitaires (18/18 sur Windows), démarrage `miles.py --help` (code 0), absence de secrets, cohérence des documents, pas de basculement silencieux, pas d'accès shell arbitraire, configuration invalide gérée, dégradation gracieuse voix.
- Critères FAIL : documentation d'installation manquante (résolu par Agent B : `docs/installation/INSTALL.md` créé dans TASK-DEV-004).
- Critères BLOCKED : validation spécifique sur Debian 13 (environnement non disponible sur le poste Windows d'Agent B et de Agent A).
- Recommandation : valider sur Debian 13 avant de considérer le jalon pleinement atteint.

## Notes

- Les deux PC possèdent leur propre clone local du dépôt.
- La communication est asynchrone via GitHub ; aucun mécanisme direct entre les instances OpenCode n'est installé.
- Avant de commencer une tâche, consulter les messages non résolus dans `MESSAGES.md` (statut `[EN ATTENTE]`).
- GPU détecté sur ce poste : NVIDIA GeForce RTX 3050, 4096 MiB VRAM, pilote 617.42, CUDA 13.4 (Windows).

## Phase 6.3k — Frontieres de confiance de la propriete `read_only` (Agent A, 2026-10-21)
- **Rapport** : `docs/reports/PHASE_6_3K_READ_ONLY_TRUST_BOUNDARIES_AGENT_A.md`
- **Reference de lecture** : `54bd138` (`fix/miles-results-persistence`). **Deux branches livrees** : `test/miles-read-only-trust-boundaries` (`155dab3`, tests seuls) et `fix/miles-read-only-prudent-type` (correctif minimal, empilee sur la precedente). **Aucune fusion** ; `main` (`b9b7e7d`), l integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`), A-alpha/B-alpha (`25baa60`), D-B05 (`79692fe`) et D-B05-restants (`54bd138`) sont inchanges. Travail en **deux worktrees isoles** (`Temp\miles-trust`, `Temp\miles-trustfix`) ; artefact non suivi et bases du developeur preserves.
- **Examen prealable** : aucun test equivalent n existait. Les tests de plan existants ne couvrent que le `tool_id` et les parametres ; l immuabilite du schema d outils, l impossibilite pour le modele de declarer une propriete de securite, et le traitement des proprietes absentes ou invalides n etaient testes par personne.
- **Frontieres verifiees (et deja garanties par l architecture)** : (F1) `PlanStep` n a aucune propriete `read_only` : le modele ne peut pas declarer lui-meme un outil sans effet, et le plan ne peut rien changer au schema ; (F2) `ToolDefinition` est fige (`frozen=True`) : toute mutation est refusee, et un `read_only` passe en *parametre* est refuse comme parametre non declare ; (F3) la propriete est lue dans le **registre** de l application, jamais dans la mission ni dans le plan ; (F4) un outil inconnu ou non declare n est jamais rejoue ; (F5) une propriete absente ou `None` est prudente.
- **Defaut CONFIRME (F6)** : `bool(getattr(tool, "read_only", False))` faisait passer une valeur **non booleenne vraie** pour une declaration « sans effet » : la chaine `"false"` (dont le sens est l inverse), la chaine `"oui"`, l entier `1`… autorisaient la **reprise automatique d une operation susceptible d avoir un effet**. Exploitabilite : **nulle par le modele** (la declaration est applicative) ; c est une defaillance du principe de prudence, mesuree et couverte par un test.
- **Correctif minimal** : seule la valeur booleenne `True` vaut declaration (`getattr(tool, "read_only", False) is True`) ; absente, `None`, chaine, entier, liste redeviennent prudents. **6 echouent sans le correctif**, 12/12 avec.
- **Tests** : `tests/test_read_only_trust_boundaries.py` (12 tests deterministes : outils simules, magasin temporaire, compteur d appels par fichier car le moteur execute les outils dans un processus separe) ; suite complete **665 tests OK (4 ignores)** sur la branche de tests et **666 tests OK (4 ignores)** sur la branche de correctif ; **70 tests d audit Agent B rejoues tels quels : OK (2 ignores)** ; non-regression orchestrateur (73), bornes (20), D1-bis (20), securite web (35), moteur (26), integration outils (40), registre (6), politique (11), D3 (40), reprise (12), persistance (9). Aucun appel API payant, aucune donnee reelle lue ni ecrite.
- **Limites** : la declaration `read_only` reste une assertion de l application (le defaut est « a effet ») ; un outil declare sans effet mais qui en a un serait rejoue (responsabilite de l application) ; aucune validation Debian 13 ; l option de remplacer le booleen par une **enumeration stricte** (supprimant par construction toute valeur malformee) est proposee a Agent B, non appliquee (plus large que le correctif minimal).
- **En attente** : audit independant d Agent B (TASK-DEV-037). Les audits en cours ne sont pas consideres comme approuves ; aucune fusion.

## Phase 6.3l — Mission P1 : `/answer` n'approuve plus (Agent A, 2026-10-21)
- **Rapport** : `docs/reports/PHASE_6_3L_P1_ANSWER_AUTHORIZATION_AGENT_A.md`
- **Base** : `25baa60` (`fix/miles-answer-d1ter` : D1 + D2 + D1-bis + D3 + A-alpha/B-alpha). Branche : `fix/miles-answer-authorization-only`. **Aucune fusion.** `main` (`b9b7e7d`), l'integration (`69bf670`), D1 (`3a59dae`), D2 (`d3240d2`), D1-bis (`1ef4878`), D3 (`0be08cd`), A-alpha/B-alpha (`25baa60`) sont inchanges. Travail en **worktree isole** (`Temp\miles-answeronly`) ; artefact non suivi et bases du developeur preserves.
- **Correction (P1)** : `MissionRunner.answer` ne transforme **plus** une reponse textuelle (`o`, `oui`, etc.) en approbation d'autorisation : une demande d'autorisation leve `MissionAuthorizationError` (`authorization_requires_token`), et l'approbation exige `/authorize` et un jeton valide (usage unique, expiration, session, proprietaire). `MissionRunner.check_answer` est mise a jour (elle ne valide plus `check_authorization`) ; l'interface CLI intercepte l'exception. La mission n'est **ni approuvee ni tuee** : elle reste en attente.
- **Tests** : `tests/test_answer_authorization_invariant.py` (8 tests d'invariant) : aucun mot d'approbation par `/answer` n'approuve, l'API interne n'approuve pas, `/authorize` sans jeton valide n'approuve pas, le jeton d'une autre mission / d'une autre session / d'un autre utilisateur est refuse, avec un jeton valide l'action est approuvee puis executee (grant unique lie a la session et a la mission), le jeton ne sert qu'une fois. **9 tests echouent sans le correctif** ; 655 tests OK (4 ignores) ; 70 tests d'audit Agent B OK (2 ignores). Verification HTTP reelle : 403 sur tous les mots d'approbation, mission terminee par `/authorize` avec le jeton.
- **Limite** : les tests d'observation (`test_investigation_d1ter_answer_path.py`) sont mis a jour pour refléter le nouveau comportement ; ils ne contournent pas la protection.
- **En attente** : audit independant d'Agent B (TASK-DEV-039). Les audits en cours ne sont pas consideres comme approuves. Aucune fusion.
## Phase 7 — Cockpit web de contrôle du projet (Agent A, 2026-10-27)

- **Rapport** : `docs/reports/PHASE_7_COCKPIT_AGENT_A.md` — **Tâche** : `TASK-DEV-043` (DONE).
- **Branche** : `feat/miles-cockpit-ui`, créée depuis `origin/integration/miles-post-d1` (`05b7b82`). **Aucune fusion, aucun push.**
- **Livré** : cockpit de pilotage dans l'interface web existante — lecture de `TASKS.md`, `STATUS.md`, `DECISIONS.md` et `MESSAGES.md` (module `app/interface/project_board.py`, stdlib), routes `GET /api/project`, `GET /api/tasks`, `POST /api/tasks/<id>/status`, HTML/CSS/JS sortis du `f-string` vers `assets/web/`.
- **Écriture contrôlée** : un seul fichier modifiable (`TASKS.md`), transitions bornées (`TODO`/`IN_PROGRESS`/`BLOCKED` → `DONE`/`CANCELLED`), propriétaire vérifié (règle anti-conflit), écriture atomique, refus explicite si la ligne est ambiguë, journal d'audit JSONL hors Git (`data/project_board_audit.jsonl`).
- **Tests** : 31 tests dédiés (`tests/test_web_project_board.py`), suite complète **845/847** (les 2 échecs sont les tests `test_status_provider_diagnostics` faussés par le `.env` du poste, sans rapport avec le changement), 5 ignorés de plateforme.
- **Design** : audit `competences/web-design/AUDIT.py` du Lab sur copie de travail (`Lab/workspaces/miles-cockpit/`) — **100/100** ; vérification navigateur réelle sur `127.0.0.1:8099` (session, CSRF, 46 tâches, un seul `h1`, colonne terminée repliée).
- **Limites** : l'identité « Agent A / Agent B » est déclarée par l'utilisateur dans l'interface, pas authentifiée par le serveur (aucune correspondance compte ↔ agent n'existe) ; la réouverture d'une tâche `DONE` reste manuelle ; aucun test sous Debian 13.

## Phase 8 — Façade unique « Miles Companion » et données réelles du boîtier (Agent A, 2026-10-27)

- **Décision** : `DEC-014` (Miles Companion = façade unique, dépendances coupées, aucune donnée inventée).
- **Branche** : `integration/miles-post-d1`, commit `b8cb2c8` (fusion `f53b03d`). **Aucun push.**
- **Livré** : application Companion versionnée dans `app/interface/companion/`, servie sur `127.0.0.1:8787` (relais vers MILES sur `127.0.0.1:8080`) — polices, icônes, images et vidéo locales, filigrane et analytics tiers neutralisés, routes propres. Page « Projet » adossée aux documents de coordination (46 tâches, blocages, décisions, messages dépliables). Page « Boîtier » : mesures réelles (`GET /api/device`) — hôte, cœurs, disque, pid, durée du processus, fournisseur, latence loopback mesurée — et « non mesuré » explicite pour les capteurs absents ; l'indicateur ne s'allume que si MILES a répondu.
- **Tests** : 56 OK (`test_web`, `test_web_project_board`, `test_web_device`). Écriture réelle vérifiée par l'interface (`TASK-DEV-007` `TODO → IN_PROGRESS`, une ligne, audit JSONL, puis restauration). Navigateur réel : aucun 404, aucune requête sortante, valeurs stables.
- **Nettoyage Git** (sur accord explicite) : 11 worktrees temporaires propres supprimés, 21 branches distantes **fusionnées** supprimées ; 2 worktrees conservés (modifications locales : `miles-merge`, `miles-diag`).
- **Audit du Lab** : `lab.ps1 exec "python3 /workspace/tools/AUDIT-TOUS.py"` -> **vert** (49 fichiers, seuil 85). Portée : espace du Lab, **pas le dépôt MILES**.
- **En attente** : revue indépendante d'Agent B (`TASK-DEV-044`). Les autres audits en attente ne sont **pas** approuvés.

## Lot du 2026-10-27 (suite 2) — `main`, tri prouvé et cockpit unique (Agent A)

- **Décision** : `DEC-015`. **Tâches** : `TASK-DEV-045` (DONE), `TASK-DEV-046` (revue à faire).
- **`main`** : avance rapide locale depuis l'intégration ; aucun `push`.
- **Cockpit** : `app/interface/companion/server.py` sert `assets/web/` sous `/cockpit/` (liste blanche : `index.html`, `app.css`, `app.js`, `miles.svg`) ; `/cockpit` et `/projet` répondent **302** vers `/cockpit/`. Le bandeau de santé sort de la zone connectée : sans session il affiche l'état réellement observable (`Service : joignable` = MILES a répondu, **401 compris**) au lieu d'un tiret muet. Sonde côté client : `probeService` (`assets/web/app.js`) ; style : `.is-off` (`assets/web/app.css`).
- **Icônes** : `assets/web/miles.svg` (également servie par MILES via `PUBLIC_ASSETS`) et `app/interface/companion/assets/miles.svg` — plus de 404 (`/vite.svg` retiré, favicon du cockpit fourni) ; la page du Companion passe en `lang="fr"`.
- **Écoute bornée** : seuls `index.html`, `miles-bridge.js` et `assets/**` sont servis par le Companion.
- **Tests** : `tests/test_companion_server.py` — **18 tests** (redirections, liste blanche, relais des routes et du **corps des POST**, MILES injoignable → 502 explicite, refus d'écoute hors boucle locale) ; `tests/test_web_project_board.py` couvre l'icône publique. Suite web complète : **74 OK**.
- **Vérification navigateur (8787)** : lien `Projet → /cockpit/` ajouté dans les deux navigations du Companion ; `/cockpit/` rend les onglets Projet / Conversation / Mémoire / Outils, `lang="fr"`, lien d'évitement, bandeau « joignable / session requise / fermée » ; **13 requêtes, aucune en échec**, aucune erreur console ; à 390 px de large, **aucun débordement horizontal**.
- **Audit design du Lab** (`competences/web-design/AUDIT.py`, copie de travail rafraîchie `/workspace/miles-cockpit/`) : **100/100 — excellente** (contraste, échelle typographique, rythme des espacements, cibles cliquables, SEO, images, accessibilité, responsive, sémantique ; 11 titres, un seul `h1`).
- **Audit de fin de tâche du Lab** (`AUDIT-TOUS.py`) : **vert** — 49 fichiers au-dessus du seuil de 85. Portée réelle : **l'espace du Lab**, pas ce dépôt (limite déjà signalée en `M-018`).
- **Réserve** : `GET /miles.svg` sur le serveur MILES **en cours** répond encore 401 (processus démarré avant ce lot) ; un redémarrage de `miles.py --web` le corrige et affiche un **nouveau jeton d'accès**.
- **En attente** : revues indépendantes `TASK-DEV-044` et `TASK-DEV-046`, ainsi que les dix audits de la Phase 6.3 (liste dans `HANDOFF.md`, `H-014`).

## Phase 9 — Lot paquets téléchargeables : arbitrages et périmètre exclusif (Agent A, 2026-10-28)

- **Décidé** (DEC-016, questions tranchées par l'utilisateur) : un seul agent exécute le lot ;
  ouverture réseau par `MILES_WEB_LAN` refusée sans jeton ; firmware compilé avant livraison ;
  valeur de capteur seulement si le backend a répondu, avec l'âge de la mesure ; paquet PC
  autonome et `INSTALL.md` qui renvoie vers lui ; règle d'exposition réseau versionnée.
- **Écarts factuels corrigés dans le plan** : `scripts/box_preflight.py` absent ; `hardware/`
  vide ; 30 variables `MILES_*` (pas 19) ; `requirements.txt` sans dépendance ;
  `BOX_DEBIAN_SETUP.md` introuvable (dépôt et Lab).
- **Périmètre de cette instance** : aucune ligne de code du lot — revue, arbitrages,
  documentation. `web.py`, `miles.py` et `miles-bridge.js` sont réservés à l'exécutant.
- **Contrôles exécutés** : `git status --porcelain` (arbre propre) ; `git rev-list --left-right
  --count origin/main...main` → **0 / 80** ; `git push origin main` → **ÉCHEC** (gestionnaire
  d'identifiants inopérant, aucun terminal interactif) : rien n'est publié.
- **Reste à faire** : push de `main` depuis un terminal authentifié ; exécution du lot par le
  second agent ; revue indépendante d'Agent B une fois les commits accessibles.
