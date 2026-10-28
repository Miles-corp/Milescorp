# docs/coordination/DECISIONS.md — Registre des décisions MILES

Convention : chaque décision reçoit un ID `DEC-###` (ou `D-###`), une date, un auteur, un contexte, la décision et un statut (`PROPOSEE`, `ACCEPTEE`, `REJETEE`, `OBSOLETE`). Journal append-only : les décisions ne sont jamais modifiées rétroactivement.

## DEC-001 — Système de coordination asynchrone par fichiers Markdown

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Deux instances OpenCode sur deux PC distincts, aucun serveur permanent, aucun service payant, pas de communication directe entre agents.
- **Décision** : La coordination s'appuie exclusivement sur des fichiers Markdown dans `docs/coordination/` (`AGENTS.md`, `WORKFLOW.md`, `TASKS.md`, `DECISIONS.md`, `STATUS.md`, `HANDOFF.md`, `REPORT_TEMPLATE.md`), synchronisés via Git et GitHub. La communication est asynchrone.
- **Statut** : ACCEPTEE

## DEC-002 — Identifiants des agents et format des tâches

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : Il faut distinguer clairement les deux agents et tracer chaque tâche.
- **Décision** : Les agents sont `Agent A` (PC principal, git `DripMind`) et `Agent B` (second PC). Les tâches utilisent l'identifiant `TASK-###` avec les statuts `TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`.
- **Statut** : ACCEPTEE

## DEC-003 — Pas de développement fonctionnel dans la Mission 001

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : La mission 001 concerne uniquement l'organisation, la documentation et les règles de collaboration.
- **Décision** : Aucune fonctionnalité de l'assistant MILES n'est développée durant cette mission.
- **Statut** : ACCEPTEE

## DEC-004 — Aucun push automatique vers GitHub

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : L'utilisateur a demandé de ne rien publier sans son autorisation.
- **Décision** : Les documents sont créés localement. Aucun commit ni push n'est effectué sans accord explicite pour publier.
- **Statut** : ACCEPTEE

## DEC-005 — Architecture hybride distant/local avec sélection explicite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande un fournisseur local sur PC avec GPU NVIDIA (RTX 3050, 4 Go VRAM détectés via nvidia-smi).
- **Décision** : Réutiliser `LocalProvider` existant (serveur local HTTP type Ollama/llama.cpp). Aucune réécriture des fournisseurs distants. Sélection explicite via `MILES_PROVIDER` ou `--provider`. Pas de basculement silencieux. Diagnostic GPU via `nvidia-smi` (lecture seule, optionnel). MILES ne télécharge aucun modèle.
- **Statut** : ACCEPTEE

## DEC-006 — Mémoire persistante locale SQLite

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-006 demande une mémoire persistante locale, contrôlable par l'utilisateur, indépendante du fournisseur IA.
- **Décision** : SQLite (stdlib Python) en fichier unique `data/memory.db`. Trois notions séparées : historique de session (éphémère), préférences (key-value), souvenirs explicites (uniquement à la demande utilisateur via `/remember`). Détection des motifs secrets au moment de l'enregistrement. Budget de contexte configurable. Dégradation gracieuse si base absente/corrompue/indisponible. Base exclue de Git via `.gitignore` (`data/*.db`).
- **Statut** : ACCEPTEE

## DEC-007 — Interface web http.server sur 127.0.0.1, zéro dépendance

- **Date** : 2026-10-19
- **Auteur** : Agent A
- **Contexte** : MILESTONE-005 demande une interface web pour converser avec MILES.
- **Décision** : Utiliser `http.server` de la bibliothèque standard Python (zéro dépendance supplémentaire). Serveur sur `127.0.0.1` uniquement par défaut. Routes : `/` (page d'accueil + formulaire), `/message` (POST), `/status` (GET), `/memory` (GET), `/remember` (POST), `/forget` (POST). Séparation claire entre serveur web, logique applicative (WebApp) et fournisseurs IA. Évolution vers Flask possible ultérieurement.
- **Statut** : ACCEPTEE

## DEC-008 — Couche métier unique `ToolService` partagée par le CLI et l'interface web

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : le moteur d'outils de la Phase 4 existait mais n'était branché nulle part. Le CLI disposait d'un chemin d'action parallèle (`propose_action()` / `ActionValidator`) jamais appelé, et le web n'exposait aucune route d'outils. Brancher les deux interfaces demandait de ne pas dupliquer la logique métier (validation, permissions, confirmation, délai, audit).
- **Décision** : introduire `app/tools/service.py` (`ToolService`) comme **unique** point d'entrée vers le moteur d'outils. Le CLI (`/tools`, `/tool`) et l'interface web (`GET /tools`, `POST /tool`) reçoivent la **même instance**, construite une seule fois dans `miles.py`. Le registre par défaut (`app/tools/builtin.py`) n'enregistre que des outils réellement implémentés ; les handlers sont des fonctions de niveau module picklables (le moteur exécute dans un sous-processus). L'ancien `propose_action()` est conservé pour compatibilité mais n'est plus le chemin d'exécution. Les actions MEDIUM/HIGH exigent une confirmation humaine explicite (CLI : saisie clavier ; web : boîte de confirmation), via le mécanisme de jeton existant du moteur (lié à l'outil et aux paramètres exacts, usage unique, TTL 300 s).
- **Conséquences** : comportement identique par construction entre les deux interfaces (vérifié par test d'identité du service), aucune nouvelle dépendance, aucun appel API payant. Limite assumée : le jeton n'est pas lié à une identité utilisateur ; à traiter avant toute exposition des outils au modèle.
- **Statut** : ACCEPTEE

## DEC-009 — Autorisations liées à la session et à la mission, mission pilote en lecture seule

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : le rapport de la Phase 5 signalait que le jeton de confirmation du moteur d'outils n'était lié ni à l'utilisateur ni à un contexte, et pouvait donc être rejoué. La Phase 6 introduit une capacité d'autonomie (exécution de plusieurs étapes sans intervention) : un mécanisme d'autorisation non lié serait un risque direct.
- **Décision** :
  1. **Autorisations (« grants »)** — `app/tools/grants.py`. Un grant est émis par l'application (jamais par le modèle), lié à une **session** (jeton aléatoire par exécution) et à une **mission**, portant une liste explicite d'outils et, éventuellement, des racines de chemin. Il expire, son nombre d'utilisations est borné, il est révocable et non rejouable. Le moteur d'outils le consulte avant d'exiger une confirmation interactive ; un grant ne contourne ni la politique de sécurité, ni les permissions, ni les délais.
  2. **Jetons de confirmation contextuels** — le moteur lie désormais chaque jeton au contexte (mission) et à l'identité de session ; un jeton émis dans un autre contexte est refusé (échec fermé) et reste à usage unique.
  3. **Mission pilote strictement en lecture seule** — la première mission autonome se limite à l'observation : `action_list_files` (listing borné en profondeur) et `action_read_file` (lecture bornée, fichiers sensibles refusés, contenu expurgé des secrets), avec la permission existante `lecture_systeme`. Aucune capacité d'écriture, de suppression, d'exécution de commande ou d'action externe n'est introduite.
  4. **Bornes appliquées par le code** — nombre maximal d'étapes, nombre maximal de tentatives par étape, durée maximale et détection de résultats identiques consécutifs sont vérifiés par l'orchestrateur, pas recommandés au modèle.
  5. **Plan IA toujours validé** — la sortie du fournisseur est validée (outil enregistré, outil autorisé, paramètres déclarés et typés, nombre d'étapes borné) avant toute exécution ; en cas de refus ou d'indisponibilité, le plan déterministe est utilisé et le repli est tracé dans la mission. Aucune décision IA n'est simulée.
  6. **Résultat d'outil = donnée** — le contenu retourné par un outil est rapporté, jamais exécuté, et ne peut modifier ni les autorisations, ni le plan, ni les règles.
- **Conséquences** : la mission pilote ne peut pas modifier le dépôt ; le compte rendu distingue faits observés, erreurs et étapes non terminées ; la reprise ne rejoue pas une étape au résultat incertain. Limites assumées : l'identité de session n'est pas une identité humaine authentifiée et le serveur web reste local et sans authentification.
- **Statut** : ACCEPTEE

## DEC-010 — Authentification par jeton porteur, session par client et autorisation de mission liée à une identité

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : le réaudit d'Agent B de la Phase 6 a confirmé deux P1 exploitables : aucune protection d'origine/CSRF sur les routes web modifiantes (P1-6-03) et une autorisation de mission acceptant `{"approved": true}` de n'importe quel client HTTP (P1-6-06). Un résiduel persistait : la session du serveur web, créée au démarrage, était partagée par tous les clients (P1-6-02).
- **Décision** :
  1. **Authentification explicite par jeton porteur.** Les identifiants sont configurés (`MILES_WEB_AUTH_TOKEN`, ou `MILES_WEB_USERS_FILE` pour plusieurs utilisateurs) ou générés et affichés une seule fois par `python miles.py --web`. **Sans identifiant configuré, l'interface web est fermée** (403 sur les routes sensibles). Ce n'est pas une identité humaine authentifiée au sens des comptes et mots de passe : c'est documenté comme tel, et cela ne dispense pas d'une authentification réelle avant toute exposition hors machine locale.
  2. **Session par client.** `POST /session` échange le jeton contre une session opaque (256 bits, expiration 30 min, révocable) et un jeton CSRF distinct. La session est l'**identité** utilisée pour les jetons de confirmation des outils, les grants et la propriété des missions. Le contrôle d'origine est une défense complémentaire, jamais une protection CSRF à lui seul.
  3. **Chaîne de contrôle sur toute route modifiante**, dans cet ordre : origine (403), type de contenu JSON (415), session authentifiée (401), jeton CSRF (403). Les refus interviennent avant la lecture du corps et avant toute action : aucun effet de bord.
  4. **Autorisation de mission liée à une identité.** Une mission porte un propriétaire et une session ; les demandes d'autorisation portent un jeton d'approbation imprévisible, lié à cette demande précise, expirant et à usage unique. Le jeton n'est jamais déduit d'un identifiant de mission et le grant émis est lié à la session du client demandeur.
  5. **Correction du blocage « résultat volumineux »** : le moteur consomme la file de résultats pendant l'exécution de l'enfant (le tampon d'un tube fait 8 Kio sous Windows) ; sans cela, tout résultat supérieur à 8 Kio expiraient à tort.
- **Conséquences** : les routes web sensibles ne sont plus atteignables sans jeton ; les 5 tests d'audit d'Agent B exprimant les P1 passent désormais ; 488 tests OK. Restent à traiter séparément : bornes par mission et non par passage de boucle (P2-6-07/08), rotation des secrets et 2FA.
- **Statut** : ACCEPTEE

## DEC-011 - Durcissement de la session web (duree, glissement, duree de vie maximale, liaison au client)

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : le reaudit Phase 6.1 d'Agent B (`ac627df`) a valide le commit `c0cb01b` **sous reserve** : le `session_id` est un jeton porteur valable 1800 s, et le jeton CSRF ne protege que les requetes *modifiantes* - un jeton de session vole suffisait donc a lire les donnees de l'utilisateur.
- **Decision** : (1) duree d'INACTIVITE de session ramenee de 1800 s a **900 s**, avec renouvellement glissant a chaque requete authentifiee ; (2) duree de vie **maximale de 8 h**, non renouvelable ; (3) **liaison de la session a l'agent utilisateur** du client (empreinte SHA-256) : un `session_id` presente depuis une autre pile cliente est refuse, y compris sur les routes de lecture ; (4) les tests d'audit d'Agent B ne sont ni supprimes ni affaiblis - deux *clients* de test ont ete adaptes pour presenter le meme agent.
- **Consequences** : la fenetre d'exploitation d'un jeton vole est reduite et le rejeu simple est bloque. Ce mecanisme **reste une authentification minimale par secret partage** : ni mot de passe, ni 2FA, ni rotation. L'absence de ces elements est explicitement documentee ; l'interface web reste locale et sans authentification multi-utilisateur reelle.
- **Statut** : ACCEPTEE

## DEC-012 - Budget global d execution porte par la mission

- **Date** : 2026-10-20
- **Auteur** : Agent A
- **Contexte** : l audit de la Phase 6 (P2-6-05, P2-6-07, P2-6-08) relevait que les bornes d execution etaient reinitialisees a chaque boucle : `_execute_loop` recalculait la deadline et remettait a zero le compteur d etapes et celui de detection de boucle, et `answer()`, `authorize()` et `resume()` relancent `run()`. Une mission alternant clarifications et autorisations pouvait donc depasser les plafonds prevus. Le plafond d interactions (5) n existait que dans l interface en ligne de commande : le web n en avait aucun. Aucun plafond global d appels d outils n existait.
- **Decision** : le budget est porte par la MISSION (`MissionBudget`), persiste en base, et n est jamais reinitialise (ni par une boucle, ni par une replanification, ni par une reponse, ni par une reprise). Il couvre : le temps d execution cumule (le temps d attente humaine n est pas consomme), le nombre d etapes, le nombre d appels d outils et le nombre d echanges avec l utilisateur. La detection de boucle devient globale. Chaque mission se termine avec un **motif d arret** explicite (`StopReason`), reporte dans le compte rendu et dans la charge utile web. Nouveaux reglages, coherents avec les valeurs existantes : `MILES_MISSION_MAX_TOOL_CALLS` (24 = 12 etapes x 2 tentatives) et `MILES_MISSION_MAX_INTERACTIONS` (5, valeur deja appliquee par le CLI, desormais appliquee par l orchestrateur donc aussi par le web).
- **Consequences** : une mission ne peut plus depasser son budget, quel que soit le nombre de boucles ; le plafond d interactions s applique enfin au web ; le motif d arret rend l arret explicable sans analyser le rapport. La version 2 du schema de la base ajoute la colonne `budget_json` (migration additive). Les limites locales existantes (tentatives par etape) sont conservees.
- **Statut** : ACCEPTEE

## DEC-013 - Registre d'identifiants, tri du depot et cockpit web de controle du projet

- **Date** : 2026-10-27
- **Auteur** : Agent A
- **Contexte** : trois identifiants de tache portaient deux taches differentes (`TASK-DEV-008`, `TASK-DEV-029`, `TASK-DEV-030`) ; la ligne Phase 3B du tableau `TASKS.md` avait perdu sa colonne Description ; l'identifiant `M-004` etait duplique et `M-010` n'a jamais existe ; `STATUS.md` decrivait encore l'etat du 2026-10-19 alors que le code allait jusqu'a la Phase 6.4. Par ailleurs `main` (b9b7e7d) est a 69 commits de la branche d'integration, seule verite du code.
- **Decision** :
  1. L'identifiant d'une tache est **immuable et unique** : un identifiant deja utilise n'est jamais reattribue. Un doublon est renumérote vers le prochain identifiant libre, avec la mention « renommee depuis TASK-... le 2026-10-27 » dans la ligne.
  2. Renommages appliques : Phase 4 conserve `TASK-DEV-008` ; Phase 3B devient **TASK-DEV-042** (ex-`TASK-DEV-008`) ; memoire 6.4a devient **TASK-DEV-040** (ex-`TASK-DEV-029`) ; son audit devient **TASK-DEV-041** (ex-`TASK-DEV-030`) ; le `M-004` duplique devient **M-017**.
  3. `integration/miles-post-d1` est la **reference du code**. `main` doit etre realisee dessus par une operation locale, sans push sans accord (DEC-004).
  4. Un **cockpit web de controle du projet** est ajoute a l'interface existante (`TASK-DEV-043`) : lecture des documents de coordination, ecriture limitee aux statuts de `TASKS.md` avec garde-fous, HTML/CSS/JS sortis du f-string Python.
  5. Aucune branche et aucun worktree n'est supprime sans liste prealable et accord explicite de l'utilisateur.
- **Consequences** : la tracabilite redevient verifiable, `STATUS.md` reflete l'etat reel, et le pilotage devient visible sans ouvrir les `.md` a la main. La suppression des branches et worktrees reste une action separee, listee et soumise a accord.
- **Statut** : ACCEPTEE


## DEC-014 — Miles Companion = façade unique, dépendances coupées, données du boîtier réelles

- **Date** : 2026-10-27
- **Auteur** : Agent A
- **Statut** : ACCEPTEE (décision de l'utilisateur)
- **Contexte** : deux interfaces coexistaient pour le même usage — le cockpit du dépôt (`assets/web`) et « Miles Companion », application React servie depuis le Lab, **hors dépôt**, chargeant ses polices, ses icônes, ses images et son analytics depuis des hôtes tiers (cdnjs, Google Fonts, `readdy.ai`, PostHog via jsDelivr), avec des liens vers un préfixe de prévisualisation Readdy. Sa page « Boîtier » affichait une charge, une batterie, des ventilateurs, un signal, une latence et une session fabriqués par le navigateur, sans aucun rapport avec la machine.
- **Décision** :
  1. **Miles Companion est la façade unique** : c'est l'interface à faire évoluer, servie par `app/interface/companion/server.py` sur `127.0.0.1:8787`, avec relais des routes de l'agent vers MILES (`127.0.0.1:8080`).
  2. Son code est **versionné dans le dépôt** (`app/interface/companion/`) : plus aucun code d'interface hors Git. La vidéo d'initialisation est conservée et servie localement.
  3. **Aucune ressource distante** : polices, icônes et images sont locales ; le filigrane et l'analytics tiers sont neutralisés ; les routes sont propres (plus de préfixe de prévisualisation).
  4. **Aucune donnée inventée** sur la page Boîtier : les valeurs de démonstration sont remplacées par des mesures réelles (hôte, cœurs logiques, disque, pid, durée du processus, fournisseur, latence loopback **mesurée**) ou par un « non mesuré » explicite pour les capteurs qui n'existent pas (température, batterie, ventilateurs, signal radio). L'indicateur d'état ne s'allume que si MILES a réellement répondu.
  5. Sur liste préalable et accord explicite de l'utilisateur : suppression des branches distantes **fusionnées** (21) et des worktrees **temporaires propres** (11). Les deux worktrees portant des modifications locales sont **conservés**.
- **Conséquences** : plus aucune requête ne sort du poste ; l'interface ne peut plus affirmer une mesure qu'elle n'a pas ; le pilotage projet reste assuré par la page « Projet » adossée aux documents de coordination. `main` n'est pas réalignée (aucun push sans accord, DEC-004).

## DEC-015 — `main` devient la référence, le cockpit n'a plus qu'une implémentation, le tri suit une règle de preuve

- **Date** : 2026-10-27
- **Auteur** : Agent A
- **Statut** : ACCEPTEE (décision de l'utilisateur)
- **Contexte** : `main` était restée 77 commits derrière la branche d'intégration ; deux interfaces remplissaient la même fonction (la page Projet du Companion et le cockpit `assets/web`) ; une bibliothèque d'icônes de 1,05 Mo était liée sans être utilisée ; deux worktrees sous `%TEMP%` portaient du travail absent de Git (un rapport de 71 lignes, 433 lignes de code).
- **Décision** :
  1. **`main` est la référence du code** : avance rapide locale depuis `integration/miles-post-d1`, sans `reset --hard` ni `push` (DEC-004). La branche d'intégration est conservée à l'identique comme repère.
  2. **Une seule implémentation du cockpit** (`assets/web/`) ; le serveur Companion la sert sous `/cockpit/` et `/projet` y redirige. Aucune copie divergente n'est admise.
  3. **Le tri ne supprime que ce qui est prouvé non référencé**, la preuve étant consignée dans `ORGANISATION.md` (§11). Les emplacements réservés sont conservés par leur marqueur `.gitkeep`.
  4. **Aucun travail ne reste dans un dossier temporaire** : avant retrait d'un worktree, son contenu unique est commité sur sa branche ou récupéré dans la référence, puis le dossier est retiré — les branches, elles, sont conservées.
  5. **`ORGANISATION.md`** (racine) fait autorité sur la carte du dépôt ; les rapports datés de `docs/reports/` décrivent leur date et ne sont jamais réécrits.
- **Conséquences** : la référence est unique et lisible ; la surface HTTP servie par le Companion est bornée par une liste blanche ; plus aucun travail ne dépend de `%TEMP%` ; la revue indépendante porte sur `TASK-DEV-044` et `TASK-DEV-046`.

## DEC-016 — Lot « paquets téléchargeables MILES » (Mode C/WiFi) : arbitrages et corrections factuelles

- **Contexte** : un second agent exécute en parallèle un plan de paquets téléchargeables (backend boîtier, paquet PC Debian, firmware ESP32-S3, opt-in d'écoute réseau `MILES_WEB_LAN`, intégration cockpit ↔ boîtier). La revue de ce plan contre le dépôt a relevé cinq écarts factuels et un conflit de fichiers, tranchés par l'utilisateur le 2026-10-28.
- **Décision** :
  1. **Un seul agent exécute le lot** : celui qui en est l'auteur. L'autre instance n'en écrit aucune ligne et n'ouvre aucun chantier concurrent sur les mêmes sujets ; son apport est la revue, les arbitrages et la documentation. `app/interface/web.py`, `miles.py` et `app/interface/companion/miles-bridge.js` appartiennent exclusivement à l'exécutant pendant ce lot.
  2. **Ouverture réseau** : elle passe par un opt-in explicite `MILES_WEB_LAN`, **refusé au démarrage** si `MILES_WEB_AUTH_TOKEN` n'est pas configuré. La garde `assert_local_host` (`app/interface/web.py`) et la classe `TestWebServerLocalOnly` (`tests/test_web_security.py`, neuf tests) doivent être réécrites pour porter ce contrat, dont un test qui prouve le refus sans jeton. Le défaut reste `127.0.0.1`.
  3. **Firmware ESP32** : la chaîne de compilation est installée et le firmware **réellement compilé** avant livraison ; la sortie de compilation est conservée dans le rapport. Une archive non compilée ne part pas.
  4. **Capteurs** : une valeur du boîtier (température, ventilateurs, charge) n'est affichée que si le backend a répondu, **avec l'âge de la mesure** ; tout le reste demeure « non mesuré ». DEC-014 reste en vigueur : aucune valeur inventée.
  5. **Paquet PC autonome** : il porte sa propre documentation d'installation et `docs/installation/INSTALL.md` renvoie vers elle au lieu de la dupliquer.
  6. **Document de conformité** : la règle qui encadre l'exposition réseau ne peut pas rester dans un document absent du dépôt. `BOX_DEBIAN_SETUP.md` est introuvable ici et dans le Lab ; il doit être créé dans le dépôt ou sa référence corrigée avant l'étape d'ouverture.
- **Corrections factuelles à appliquer au plan** :
  - `scripts/box_preflight.py` n'existe pas (`scripts/` ne contient que `.gitkeep`) : le `box_preflight.sh` prévu n'a rien à appeler.
  - `hardware/` ne contient que deux dossiers vides (`diagrams/`, `prototypes/`) : `hardware/packages/` est créé de zéro.
  - `app/config/settings.py` reconnaît **30** variables `MILES_*` distinctes, pas 19 ; le `.env.example` d'un paquet doit être **produit** à partir de celui de la racine, sous peine de dérive silencieuse.
  - `requirements.txt` est entièrement commenté : MILES est réellement zéro-dépendance, l'environnement virtuel ne sert qu'à l'isolation.
- **Conséquences** : le lot avance sans collision de fichiers ; la garde réseau ne peut plus être levée par inadvertance ; aucune archive ne part avec du code non compilé ; DEC-014 n'est pas contredit.

## DEC-017 — Isolation des tests par session et « valeur vide = source absente »

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : la suite complète comportait **2 échecs** (`tests/test_status_provider_diagnostics.py`) attribués tantôt au `.env` du poste, tantôt au code, sans cause établie. Diagnostic : `tests/__init__.py` redirigeait `MILES_ENV_FILE` vers un chemin **fixe** (`%TEMP%\miles_tests_no_such_env_file`) censé ne jamais exister — mais ce fichier **existait** (97 octets, 2026-10-27 15:14) et contenait `MILES_REMOTE_MODEL=` vide. Ses clés (`MILES_REMOTE_PROVIDER`) n'existent **que** sur `feature/miles-multi-provider` : une exécution de cette branche avait écrit son faux `.env` dans ce chemin partagé, et toutes les sessions suivantes le lisaient comme un vrai `.env`. Preuve : avec `MILES_REMOTE_MODEL` forcé, les 14 tests passaient ; sans, `Settings().get("remote_model")` valait `''` au lieu de `miles-default`.
- **Décision** :
  1. **Isolation par session** : le chemin `.env` des tests est créé dans un répertoire `tempfile.mkdtemp()` **unique par session**, avec un fichier inexistant à l'intérieur et nettoyage en fin de session. Un chemin fixe et prévisible est un piège : n'importe quelle exécution peut le rendre existant pour toutes les suivantes. Le chemin imposé par l'utilisateur (`MILES_ENV_FILE` défini avant la suite) reste prioritaire. Le chemin fixe devient une constante documentée `LEGACY_ISOLATION_PATH`, jamais utilisée.
  2. **Valeur vide = source absente** : une variable vide ou composée d'espaces, qu'elle vienne du processus ou du `.env`, ne configure rien. La source suivante prend le relais, jusqu'aux valeurs par défaut ; une variable de processus vide ne bloque plus la lecture du `.env`. La priorité entre sources non vides est inchangée, les conversions de type sont inchangées, une clé API vide reste **absente** (jamais une chaîne vide propagée).
  3. **Documentation** : `docs/installation/INSTALL.md` (§3ter, sources de configuration) énonce la règle ; `tests/test_docs_configuration.py` continue de garder l'alignement doc/code.
  4. **Aucun test existant affaibli** : les deux assertions en échec étaient justes, c'est l'environnement qui était pollué. Aucune assertion n'a été modifiée ni supprimée.
- **Conséquences** : suite complète **891 tests, 0 échec, 5 ignorés**, obtenue **avec le fichier parasite encore en place** (contrôle négatif), puis après suppression. Un `.env` contenant `MILES_REMOTE_MODEL=` ne produit plus un modèle vide en production, et `MILES_HISTORY_LIMIT=` ne bloque plus le démarrage. Limite assumée : la branche `feature/miles-multi-provider` n'est pas corrigée ici (elle écrit dans `MILES_ENV_FILE`, ce qui est le comportement attendu de l'application) ; le fuitage est signalé à Agent B dans `M-021`.
- **Statut** : ACCEPTEE

## DEC-018 — Retour du lot boîtier sur `main` par port de fichiers (ni merge, ni rebase)

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : le lot « paquets téléchargeables » (`TASK-DEV-047`) vit sur `fix/miles-d1-web-authorization`, branche partie de `3a59dae` (ère D1) : **49 commits de retard** sur `main` et **22 d'avance**, dont la majorité est de la documentation de coordination que `main` a réécrite depuis (`DECISIONS`, `MESSAGES`, `STATUS`, `continuations/`, `MISSIONS_REGISTRY`). Le contenu fonctionnel réellement utile tient en **15 fichiers additifs**, 2 scripts, 1 document et 3 fichiers de test.
- **Décision** :
  1. **Port, pas merge ni rebase.** Les fichiers utiles sont repris tels quels sur une branche neuve issue de `main`. Un merge ferait entrer de la documentation obsolète et écraserait des décisions récentes ; un rebase rejouerait 22 commits dont la plupart n'ont plus de sens. La branche d'origine reste intacte et non fusionnée comme archive.
  2. **Le port est additif.** Aucun fichier existant de `main` n'est modifié, à deux exceptions près, justifiées et testées : `.gitignore` (ajout de `releases/`, exigé par `scripts/build_release.py`) et l'exemple `.env` du paquet PC (voir point 3).
  3. **L'exemple `.env` d'un paquet est dérivé de la racine** (déjà exigé par `DEC-016`). Constat vérifié : la version portée contenait `MILES_PROVIDER=off`, valeur que `Settings` **refuse** (`SettingsError: Fournisseur inconnu : 'off'`), et `MILES_API_KEY`, nom qu'aucun code ne lit (`MILES_REMOTE_API_KEY` est le bon). `install.sh` copiant cet exemple en `.env`, **MILES ne démarrait pas après installation**. L'exemple est donc régénéré depuis la racine, complété des deux variables du paquet (`MILES_BOX_KEY`, `MILES_WEB_AUTH_TOKEN`).
  4. **Garde-fou automatique** : `tests/test_env_examples.py` vérifie que (a) chaque exemple livré se charge sans erreur, (b) aucun exemple n'utilise un nom de variable cité par aucun code, (c) un exemple de paquet contient toutes les variables de celui de la racine, (d) aucun exemple ne porte de valeur de clé. Un exemple invalide casse désormais la suite, plus une installation.
  5. **Le contrat réseau reste une étape séparée.** `miles.py` et `app/interface/web.py` ne sont **pas** touchés ici : sur `main`, `assert_local_host` est appelé par le setter `host` de `MilesWebServer` et garanti par **10 tests** de `TestWebServerLocalOnly`. Les réécrire est un travail de sécurité (`DEC-016` §2), pas un portage ; il fait l'objet de `TASK-DEV-050`.
- **Conséquences** : `main` gagne le lot boîtier sans dette documentaire ; la suite passe de 891 à **911 tests** (0 échec, 5 ignorés) ; le diagnostic des paquets connaît désormais ses défauts restants, tracés dans `TASK-DEV-050` ; une classe entière de fautes de configuration silencieuses est fermée.
- **Statut** : ACCEPTEE
