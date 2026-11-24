## DEC-027 — Le site Companion devient notre code : coque React, comptes locaux, capteurs réels

- **Date** : 2026-10-29
- **Auteur** : Agent A
- **Contexte** : le Companion était encore un export Readdy retouché (page pré-rendue, pont `miles-bridge.js`, relais générique `/api/*`, jeton MILES demandé dans le navigateur, aucune notion de compte). L'utilisateur a demandé de le séparer de Readdy pour en faire notre propriété, d'y ajouter les capteurs (sans connexion réelle) et un mode développeur. Plan validé avant exécution.
- **Décision** :
  1. **Coque propriétaire** : React + TypeScript + Vite dans `app/interface/companion/frontend/`, build servi depuis `dist/` par le serveur Python (bibliothèque standard uniquement, aucune dépendance Python nouvelle).
  2. **Comptes locaux à la box** : aucun compte public, aucune inscription depuis le site, aucun e-mail sortant. L'administrateur crée les comptes en CLI ; **deux administrateurs maximum** garantis par transaction SQLite, tous les autres comptes sont `user`. Mots de passe `scrypt` + sel, sessions opaques dont seul le SHA-256 est stocké, cookie `HttpOnly` `SameSite=Strict`, CSRF synchronisé, verrouillage après 5 échecs.
  3. **Le jeton MILES reste côté serveur** : `miles_client.py` ouvre la session avec `MILES_WEB_AUTH_TOKEN` et ne relaie qu'une liste blanche de routes. Le navigateur ne voit jamais ce jeton.
  4. **Capteurs réels uniquement** : `sensors.py` lit `/proc` et `/sys` ; toute mesure absente est renvoyée **indisponible avec sa raison**, jamais une valeur inventée (DEC-014). Le backend boîtier local (`127.0.0.1:8095`) est lu côté serveur, refusé hors boucle locale.
  5. **Mode développeur par compte** : activé dans les réglages, il ajoute les détails bruts des capteurs et ouvre le journal d'audit et le journal d'accès HTTP. Il ne donne aucun droit supplémentaire sur les actions ; les administrateurs seuls gèrent les comptes.
  6. **Applets typées** : `system` (primitive réelle), `render` (état déjà calculé), `action` (effet réel, confirmation à jeton unique). Le registre serveur est la seule source de vérité : une action inconnue est refusée.
  7. **Aucune ressource distante** : polices, icônes et scripts sont servis localement ; CSP `default-src 'self'` ; aucune requête sortante hors MILES local.
  8. **Écoute locale par défaut** : `127.0.0.1:8787`. L'ouverture LAN reste refusée tant que l'audit indépendant et `COMPANION_LAN_AUDITED=1` ne sont pas réunis (DEC-016/DEC-019) — la règle n'est pas contournée par ce lot.
  9. **Base locale** : `data/companion.db` (ignorée par Git), à côté des autres bases `data/`.
- **Conséquences** : `index.html`, `miles-bridge.js` et `assets/` de l'export Readdy ne sont plus servis (conservés hors service pour historique) ; `/api/box` public et le relais `/api/*` disparaissent ; toute modification d'interface exige `npm ci && npm run build` dans `frontend/`.
- **Preuves d'exécution** : voir `docs/reports/SITE_COMPANION_V1_AGENT_A.md` (suite complète, tests dédiés, vérification navigateur réelle, mesures honnêtes sur Windows).
- **Limites assumées** : MILES et le backend boîtier n'étaient pas démarrés pendant la vérification (états « non configuré » / « indisponible » affichés tels quels) ; aucun fournisseur IA réel n'a été appelé ; l'écoute LAN n'a pas été testée puisqu'elle reste interdite ; l'audit de design du Lab n'a pas été exécuté (Lab en travaux, consigne utilisateur).
- **Statut** : ACCEPTEE


## DEC-026 — La clé API reste sur la box ; le site n'en détient aucune copie

- **Date** : 2026-10-28
- **Auteur** : Agent A bis
- **Contexte** : la vision utilisateur décrit un onglet IA sur le site et un
  jumelage box ↔ site. Le risque évident est de faire transiter les clés
  fournisseurs par un site, même « juste pour configurer ».
- **Décision** :
  1. **Aucune clé API côté site**, sous aucune forme : ni stockée, ni relayée,
     ni journalisée, ni affichée, ni saisie dans un formulaire du site. La
     saisie se fait sur la page locale de la box, qui écrit son `.env` par le
     mécanisme existant (`provider_config`, écriture atomique et masquage).
  2. Le site ne reçoit qu'un **état** : fournisseur actif, modèle actif,
     configuré ou non. Toute absence de réponse s'affiche « inconnu ».
  3. **Jumelage V1 sans serveur** : code court affiché par la box, comparaison
     à temps constant, jeton révocable, aucun paquet hors du réseau local.
  4. **V2 avec passerelle** : la box ouvre une connexion **sortante**
     persistante (une box derrière NAT n'est pas joignable) ; la passerelle ne
     relaie que des signaux, aucun contenu ni secret.
  5. **Position** : consentement distinct, arrondi, rétention bornée, refus
     possible sans perte de fonction.
- **Conséquences** : l'hébergement de la passerelle, la collecte de position et
  l'obligation de comptes sont des **décisions utilisateur** ; rien n'est
  provisionné. La spec `docs/specs/SITE_PAIRING_IA_SPEC.md` en découle.
- **Statut** : ACCEPTEE
tion et les règles de collaboration.
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

## DEC-019 — Contrat d'écoute réseau : local par défaut, LAN sur preuve

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : `DEC-016` §2 exigeait de réécrire la garde réseau, pas de la contourner. Sur `main`, `assert_local_host` était appliquée par le setter `host` de `MilesWebServer` et verrouillée par 10 tests de `TestWebServerLocalOnly`. Le lot boîtier avait ajouté une garde parallèle (`allow_lan`) sans toucher ce verrou : `--web-lan` n'aurait pas pu fonctionner, et rien ne prouvait le refus sans jeton.
- **Décision** :
  1. **Deux gardes, pas une.** `assert_local_host` reste inchangée (refus de tout ce qui n'est pas `127.0.0.1`). Une seconde fonction, `assert_listen_host(host, allow_lan=False)`, porte le contrat complet. Un appelant qui ignore le mode LAN obtient donc exactement le comportement d'avant.
  2. **Asymétrie volontaire.** Sans `allow_lan`, seule `127.0.0.1` passe. Avec `allow_lan`, une adresse **privée** (RFC 1918 ou ULA IPv6) est acceptée — mais `0.0.0.0`, `::`, une adresse publique, un nom d'hôte, une adresse de bouclage IPv6 ou une valeur non textuelle restent refusés. Nommer une adresse précise est obligatoire : l'écoute accidentelle sur toutes les interfaces devient impossible.
  3. **Le mode d'écoute est figé à la construction.** `allow_lan` est une propriété sans setter : une affectation tardive lève `AttributeError`. `start()` revalide de toute façon l'adresse avant la liaison.
  4. **Refus au démarrage, pour deux raisons distinctes.** `miles.py --web-lan` exige (a) un jeton porteur **persistant** (`MILES_WEB_AUTH_TOKEN`) — un jeton éphémère affiché une fois ne convient pas à un service joignable par le réseau — et (b) `MILES_WEB_LAN_HOST` nommant une adresse privée. `--web-lan` sans `--web` est également refusé. Dans tous ces cas : code de sortie 1, aucun serveur construit (prouvé par un test qui remplacerait `MilesWebServer` par un objet qui échoue).
  5. **Aucun test affaibli.** Les 10 tests de `TestWebServerLocalOnly` sont conservés et renforcés (les refus de `0.0.0.0` et `::` sont désormais vérifiés **aussi** en mode LAN) ; **4 tests sont ajoutés** (la classe en compte **14**) ; `tests/test_web_lan.py` en apporte **10**, qui couvrent les refus et le cas complet. Comptes vérifiés par comptage des `def test_`, après qu'un rapport d'audit en ait annoncé 8 et ce document 11 : les deux étaient faux.
- **Conséquences** : le défaut est inchangé à l'identique (`127.0.0.1`) ; l'ouverture réseau est possible mais ne peut résulter ni d'un oubli, ni d'une variable vide, ni d'une affectation tardive. **L'ouverture réelle reste soumise à l'audit B** : aucune installation ne doit l'activer avant cet audit.
- **Statut** : ACCEPTEE

## DEC-020 — Paquet PC, télémétrie du boîtier et archives : défauts corrigés

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : la relecture du lot porté (`TASK-DEV-049`) puis la vérification des livrables ont établi plusieurs défauts **reproductibles**, qu'aucun test ne couvrait.
- **Décision et corrections** :
  1. **`install.sh`** lançait le préflight par `python3 box_preflight.sh` : un script bash soumis à Python, échec garanti. Il est désormais exécuté par `bash`, et le script est idempotent (clone, venv, `.env`, tests, service sur demande), avec création de l'utilisateur système avant l'installation de l'unité.
  2. **`cockpit-launcher.sh`** servait un dossier `./cockpit` inexistant, ce qui aurait publié une copie statique non authentifiée. Il lance maintenant le serveur Companion du dépôt (`assets/web` sous `/cockpit/`), conformément à `DEC-015` — une seule implémentation.
  3. **`miles.service`** déclarait `User=miles` sans que l'utilisateur soit créé, et rendait `.env` inscriptible alors que seul `--setup` l'écrit. L'unité décrit ses conditions réelles : utilisateur existant, `ReadWritePaths` limité à `data/`, `UMask=0077`, et **aucune** option `--web-lan` (commentaire explicite pour empêcher qu'on l'ajoute sans audit).
  4. **Firmware** : `BACKEND_URL` valait `http://127.0.0.1:8095`, c'est-à-dire l'ESP32 lui-même ; et deux relevés factices (`-99`, `-1`) étaient envoyés comme des mesures. Désormais : plus aucune adresse par défaut (le firmware refuse une URL de bouclage), configuration incomplète = arrêt net sans connexion, et **aucune valeur inventée** — un capteur absent n'est pas envoyé du tout.
  5. **Archives** : `exclure()` comparait les motifs sur le chemin complet avec des `/`, alors que Windows produit des `\`. Mesuré : `.pio/` (artefacts de compilation) et `__pycache__/` **entraient dans les archives livrées**. La fonction compare maintenant des **segments** et gère les deux séparateurs ; `tests/test_build_release.py` archive un faux paquet piégé et vérifie qu'aucun secret ne sort, **contenu des fichiers compris**.
- **Conséquences** : le paquet PC est cohérent avec ses scripts ; la télémétrie du boîtier est lue en même origine (`/api/box` sur le serveur Companion, cible figée) et n'affiche une valeur **que si le backend a répondu, avec l'âge de la mesure** ; les archives ne contiennent que des sources. Compilation réelle du firmware : `[SUCCESS]`, image de 1 103 072 octets. **Flash et comportement sur matériel restent non vérifiés.**
- **Statut** : ACCEPTEE

## DEC-021 — La convention `.local` est vérifiée par refus, pas par avertissement

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : l'audit B (`M-024`) a relevé que `scripts/build_release.py` exclut par construction les `*.ini.local`, mais archive sans broncher un `*.ini` ordinaire. `M-025` a répondu par la convention écrite (en-tête du script, doc du firmware, test) ; `M-027` a confirmé la convention mais recommandé en plus un **avertissement** quand un `*.ini` non-`.local` contient des motifs de clé.
- **Décision** :
  1. **Un avertissement ne suffit pas** : il s'affiche et la livraison continue, donc le secret part quand même. `tests/test_build_release.py` dit du script qu'il est « le dernier rempart avant publication » ; un rempart qui prévient sans empêcher n'en est pas un. Le script **refuse** : sortie 1, **aucune archive créée**, même partiellement.
  2. **Portée volontairement étroite** : seuls les `*.ini` **ordinaires** sont relus (les `.ini.local` sont déjà exclus), seules les lignes actives sont examinées (commentaires `;`, `#`, `//` ignorés, sinon la documentation du dépôt elle-mêmes déclencherait l'alerte), et les valeurs de gabarit (`REPLACE_ME`, `CHANGEME`, `CHANGE_ME`, `A_COMPLETER`, `TODO`, vide) sont tolérées — elles sont dans le dépôt et ne sont pas des secrets.
  3. **Le message d'erreur ne peut pas devenir la fuite** : il nomme le fichier, la ligne et la **variable**, jamais la valeur.
  4. **Six tests** couvrent le refus, dont un **non-faux-positif sur le `platformio.ini` réel du dépôt** et une vérification qu'aucune archive n'existe après refus. `test_build_release.py` passe de 6 à **12** tests.
- **Conséquences** : la règle `.local` n'est plus une consigne mais une condition de livraison. Un identifiant laissé dans un `*.ini` ordinaire fait échouer la construction des archives au lieu de partir chez l'utilisateur. Limite assumée : le contrôle porte sur des **noms de variables** et non sur une détection d'entropie — une clé rangée sous un nom anodin reste invisible.
- **Statut** : ACCEPTEE

## DEC-022 — `*.ini.local` ne protégeait pas `platformio.local.ini` : exclusion corrigée

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : première exécution réelle du refus de `DEC-021` (shell de l'agent rétabli). `test_ini_local_ignore` **échoue** : `avertir_identifiants_ini` signale `platformio.local.ini`. Diagnostic : le motif d'exclusion était `*.ini.local`, alors que la convention écrite partout — en-tête du script, `hardware/packages/esp32-s3/platformio.ini`, README du firmware, `VALIDATION_DEBIAN_13.md`, `.gitignore` — est `*.local.ini`. `fnmatch("platformio.local.ini", "*.ini.local")` est **faux** : les identifiants WiFi réels partaient donc dans l'archive, et le test censé le prouver n'avait jamais été lancé.
- **Décision** :
  1. `MOTIFS_EXCLUS` couvre les deux orthographes (`*.local.ini`, `*.ini.local`) : la convention documentée est honorée, l'ancienne reste tolérée.
  2. `avertir_identifiants_ini` ne décide plus par suffixe codé en dur mais par `exclure(relatif)` : **une seule règle**. Un fichier qui ne part pas ne peut plus être signalé, et réciproquement. Deux règles distinctes avaient divergé.
  3. Le message de refus cite désormais `*.local.ini`.
- **Preuve d'exécution** (2026-10-28, Windows 11, Python 3.14.7) :
  - `tests.test_build_release` : **12 tests, OK** ;
  - essai réel avec `platformio.local.ini` contenant `-DWIFI_PASS="vrai_secret"` → construction **exit 0**, fichier **absent** de `miles-esp32-s3-2026-10-28.tar.gz` ;
  - essai réel avec le même secret dans un `platformio.ini` ordinaire → **exit 1**, `REFUS : identifiants dans un *.ini ordinaire`, **aucune archive créée** (3 avant, 3 après) ;
  - contenu des archives : `platformio.ini` (gabarit `REPLACE_ME`) et `.env.example` partent ; aucun `.env`, `.pem` ni `.key` ;
  - suite complète : **942 tests, OK, 5 ignorés**.
- **Leçon de méthode** : `DEC-021` a été écrite, relue et fusionnée **sans exécution**. La relecture n'a pas vu que la règle d'exclusion et le test qu'elle prétendait satisfaire ne parlaient pas du même nom de fichier. Un test écrit et jamais lancé n'est pas une preuve, c'est une intention.
- **Statut** : ACCEPTEE

## DEC-023 — Quatre fournisseurs derrière une fabrique unique, une clé jamais divulguée

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : branche `feature/miles-multi-provider` (`263da9e`, `ed6d6c5`, `b0ba016`) auditée par Agent B (`M-008`) **sans blocage**, mais jamais fusionnée ; `main` avait 23 commits d'avance, dont l'isolation `.env` par session (`DEC-017`) que la branche ne possédait pas.
- **Décision** :
  1. **Quatre fournisseurs** : `remote` (compatible OpenAI), `local` (Ollama), `anthropic` (`/v1/messages`, en-tête `x-api-key`), `gemini` (`generateContent`). **Bibliothèque standard uniquement** (`urllib`) — aucune dépendance tierce ajoutée.
  2. **Une seule fabrique** : `build_provider(nom, …)`, avec `est_soutenu()` et `fournisseurs_soutenus()`. Un nom inconnu échoue explicitement ; aucun repli silencieux vers un fournisseur par défaut.
  3. **Les clés ne vivent que dans `.env`** : `MILES_API_KEY_<FOURNISSEUR>` et `MILES_MODEL_<FOURNISSEUR>`. Écriture atomique qui préserve les autres lignes ; `statut()` ne renvoie qu'une forme masquée (`configuree (n=N)`) ; `cle_pour()` est réservé à l'usage interne. Aucune clé dans un message d'erreur, un journal ou une sortie CLI.
  4. **Priorité environnement réel > `.env`**, signalée par `environnement_prioritaire()`.
  5. **Gemini impose la clé en paramètre d'URL** (`key=`) : l'URL n'est jamais journalisée ni renvoyée dans une erreur.
  6. **Validation de clé durcie** : les caractères de contrôle (`NUL`, tabulation, retour arrière, `DEL`) et les espaces sont refusés. Mesuré qu'ils étaient **acceptés** et écrits tels quels dans le `.env`, le corrompant pour tout autre consommateur.
- **Preuves d'exécution** (2026-10-28, Windows 11, Python 3.14.7) :
  - fusion **sans conflit** (`git merge-tree` sur `main` 47a2442) ;
  - `test_provider_*` + `test_status_provider_diagnostics` : **49 OK** ; les 2 échecs signalés par Agent B sur la branche seule **disparaissent** — `main` les avait corrigés (`DEC-017`), la fusion les apporte donc résolus ;
  - suite complète : **978 tests, OK, 5 ignorés** ;
  - aller-retour réel sur un `.env` : espaces, `#`, `=`, `+`, `/` et unicode **identiques** après relecture, variables voisines conservées, `statut()` sans la clé ; refus de `"`, `'`, antislash, saut de ligne, `NUL`, tabulation, espace.
- **Limites assumées** : aucun **appel réseau réel** n'a été effectué (tests à mocks) ; la clé Gemini transite dans l'URL par construction de l'API ; la modification **concurrente** du `.env` est **mesurée, pas garantie** : `write_env` est atomique (`os.replace`, jamais de fichier corrompu), mais `set_key` fait lire-modifier-écrire — quatre processus écrivant quatre clés différentes ont perdu une clé **1 fois sur 40 tours** (2026-10-28). Aucun verrou ajouté : CLI mono-utilisateur. À fermer par un verrou `O_CREAT|O_EXCL` avec reprise si l'écriture devient concurrente (web, multi-instance).
- **Statut** : ACCEPTEE

## DEC-024 — Moteur local : Ollama, llama.cpp reporté

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : `MI-010` laissait ouvert le choix du moteur local pour la RTX 3050 du boîtier. L'adaptateur `local` parle déjà le protocole compatible OpenAI sur `MILES_LOCAL_BASE_URL` (défaut `http://localhost:11434`), c'est-à-dire l'API d'Ollama.
- **Décision** : **Ollama**. Raisons, dans l'ordre : aucun code à écrire ni à tester (l'adaptateur existe et est couvert) ; gestion des modèles et du GPU CUDA incluse ; service systemd fourni, donc démarrage au boot du mini-PC ; aucune dépendance Python supplémentaire ; aucune clé d'API à gérer puisqu'il écoute en local.
- **llama.cpp reporté**, pas rejeté : il exigerait un adaptateur dédié, une chaîne de compilation et des choix de quantification à figer, pour un gain de performance **non mesuré** ici. À réexaminer seulement si une latence mesurée sur le M75q devient gênante — avec la mesure, pas avant.
- **Conséquences** : sur le boîtier, installer Ollama, tirer un modèle, puis `MILES_PROVIDER=local` et `MILES_LOCAL_BASE_URL=http://127.0.0.1:11434`. Aucun changement de code.
- **Limite** : aucune mesure de performance sur RTX 3050 n'a été faite — le matériel n'est pas accessible depuis cette session.
- **Statut** : ACCEPTEE

## DEC-025 — Mémoire avancée v3 intégrée (MI-022)

- **Date** : 2026-10-28
- **Auteur** : Agent A
- **Contexte** : branche locale `feature/miles-memoire-avancee` (`99c8590`, 17 tests, jamais poussée), en attente de validation humaine depuis la mission `MI-022`. Décision humaine : **valider et intégrer**.
- **Décision** : intégrer telle quelle. Apports :
  1. **`kind`** d'un souvenir — `inconnu`, `fait`, `hypothese` — modifiable par un humain (`set_kind`), jamais par le modèle.
  2. **Liens entre souvenirs** (`memory_links`) : `duplique` et `contradit`, détectés à l'écriture, **confirmables** par un humain (`confirm_link`).
  3. **Visibilité par propriétaire** : chaque souvenir reste rattaché à son `owner_user_id` (prolongement de `D-MEM-01`).
  4. **Résumé pur** (`resume_memoire`) : fonction sans effet de bord, réutilisable par le CLI et le web.
  5. **Commandes** : `/fait`, `/hypothese`, `/contradictions`, `/confirmer`.
- **Preuves d'exécution** (2026-10-28, Windows 11, Python 3.12) : `tests.test_memory_avancee` **17/17 OK** ; suite complète **995 tests, OK, 5 ignorés** ; fusion **sans conflit**.
- **Limite assumée** : la détection de contradiction est **lexicale** (`_normaliser` + `_sans_negation`), donc heuristique — deux formulations éloignées du même fait ne seront pas reliées, et une négation complexe peut échapper. C'est un signalement à confirmer par un humain, jamais une vérité automatique.
- **Statut** : ACCEPTEE

## DEC-028 — Skill `web-site` et système de mouvement du companion

- **Date** : 2026-11-07
- **Auteur** : Buffy (mission skill/site, validation humaine)
- **Contexte** : le skill `web-site` ne contenait qu'une description de deux lignes, sans ressource. Le companion React (`app/interface/companion/frontend`, 15 pages, React 19 + Vite) n'avait aucun système de mouvement tokenisé.
- **Décision** :
  1. **Source unique** du skill : `docs/skills/web-site/` (`SKILL.md` + `references/`), déclinée en copie dans le Lab (`workspaces/competences/web-design/references/web-site/`) ; la copie ne s'édite jamais seule.
  2. **Fondements documentés** : `docs/design/RECHERCHE-UX-PSYCHOLOGIE.md`, `RECHERCHE-MOTION.md`, `RECHERCHE-DASHBOARDS.md` (NN/g, Apple HIG, MDN/Chrome, WCAG 2.2, anthropics/skills).
  3. **Code propriétaire** : aucun CDN, dépendances bundlées, recréer plutôt qu'installer quand c'est petit, licence vérifiée.
  4. **Mouvement tokenisé** dans le companion : `--dur-1/2/3`, `--ease`, `--ease-enter` ; entrée de page 8 px/300 ms sur trois blocs ; pulsation réservée à `.dot-warn` ; `prefers-reduced-motion` prioritaire.
  5. **Couche 1 du cockpit** : phrase d'état en langage clair avant les chiffres sur l'accueil.
- **Preuves d'exécution** (2026-11-07, Windows 11, Node 26.13.0) : `npm run typecheck` **statut 0** ; `npm run build` **statut 0** (66 modules, 361,94 kB JS / 35,85 kB CSS, empreinte `5c30e6c1f1129814`).
- **Limites assumées** : aucune vérification visuelle (pas de capture demandée) ; pas d'audit Lab exécuté sur le SPA (authentification et API requises) ; sauvegarde du skill sur le compte Freebuff refusée, donc non effectuée.
- **Statut** : ACCEPTEE

## DEC-029 — Skill `web-site` v2 : workflow à portes, références routées, evals et validateur

- **Date** : 2026-11-07
- **Auteur** : Buffy (mission skill, validation humaine)
- **Contexte** : audit du skill contre la spécification Agent Skills et les bonnes pratiques Anthropic. Le format était valide, mais il manquait un workflow exécutable, des critères mesurables, des evals et un validateur ; `references/motion.md` contredisait la règle « tokens uniquement » (`.dot-warn` en 2.4 s codé en dur) et le README donnait une commande de synchronisation fragile.
- **Décision** :
  1. **Corps réécrit** en workflow à portes (0 contrat → 9 erreurs fréquentes), avec un tableau de vérification mesurable et un format de compte rendu imposé. `SKILL.md` reste sous 500 lignes et ~5 000 tokens.
  2. **Description élargie** (< 1 024 caractères) pour couvrir site, landing, dashboard, refonte, animation, audit et stack, y compris sans le mot « design ».
  3. **Références** : `motion.md` réécrit (pipeline de rendu, FLIP, View Transitions, `@starting-style`, perf) ; `psychologie-ux.md` élargi (lois cognitives, formulaires, confiance, mesure) ; nouvelles `stack-et-dependances.md` et `sites-professionnels.md` ; `dashboards.md` complété (fraîcheur, accessibilité des graphes).
  4. **Evals** : `evals/evals.json` (4 scénarios, assertions vérifiables) et `evals/trigger-queries.json` (14 requêtes, 7 positives / 7 négatives proches).
  5. **Validateur** : `scripts/validate-skill.mjs`, sans dépendance, exécutable par `node` ; il contrôle frontmatter, taille, sections, références, sommaires, evals et cohérence.
  6. **Source unique conservée** : `docs/skills/web-site/`, copie Lab synchronisée ; evals et scripts restent au dépôt.
- **Preuves d'exécution** : voir `docs/skills/web-site/VALIDATION.md` (sortie du validateur, vérifications statiques, limites).
- **Limites assumées** : les evals ne sont pas exécutées par un modèle dans ce dépôt ; le déclenchement réel de la description n'est pas mesuré ; la copie du Lab est une copie manuelle.
- **Statut** : ACCEPTEE

## DEC-030 — Skill `web-site` : validation officielle et evals réellement exécutées

- **Date** : 2026-11-07
- **Auteur** : Buffy (mission skill, validation humaine)
- **Contexte** : DEC-029 laissait deux limites ouvertes — evals non exécutées et déclenchement non mesuré. La mission exigeait le passage au validateur officiel de création de skill et des preuves d'exécution réelles.
- **Décision** :
  1. **Scripts officiels vendoreés** dans `tools/skill-creator/` (`quick_validate.py`, `package_skill.py`, Apache-2.0, sans modification) : la validation est reproductible et cite la version exacte.
  2. **Validateur officiel** exécuté : `Skill is valid!`, code 0. Il a d'abord révélé un YAML invalide (un ` : ` dans la description), corrigé ; le validateur maison a reçu le contrôle correspondant.
  3. **Paquet** `dist/web-site.skill` produit par le packager officiel (code 0, 9 fichiers) et inspecté ; copie `.zip` pour vérification.
  4. **4 evals exécutées** sur une instance OpenCode neuve, baseline vs skill injecté : **7/20 (35 %) → 20/20 (100 %)**. Sorties brutes, verdicts et itérations conservés dans `evals/results/`.
  5. **Déclenchement mesuré** sur deux modèles (`beam-free`, `flint-40b-free`) : **7/7 positifs, 7/7 négatifs, 0 faux positif** après correction de la description (première passe 6/7).
  6. **Cinq défauts corrigés et rejoués** : YAML, déclenchement stack, token d'attention (`--dur-pulse`), `aria-describedby`, audit commençant par job/état.
- **Preuves d'exécution** : `docs/skills/web-site/VALIDATION.md` et `docs/skills/web-site/evals/REPORT.md` (commandes, chiffres, extraits, limites).
- **Limites assumées** : evals sur un seul modèle gratuit (`deepseek-v4.1-flash-free`), notation manuelle non aveugle, aucun test de rendu réel ; les modèles payants sont indisponibles (`Insufficient account funds`, `Model access is disabled`). Le paquet n'est pas testé par un consommateur externe.
- **Statut** : ACCEPTEE

## DEC-031 — Validation multi-modèles de `web-site` et clôture de la copie Lab

- **Date** : 2026-11-07
- **Auteur** : Buffy (mission skill, validation humaine)
- **Contexte** : DEC-030 laissait deux points ouverts — un seul modèle d'évaluation et une copie Lab non resynchronisée. La mission demandait un second modèle gratuit distinct et la suppression de toute action restante.
- **Décision** :
  1. **Deux modèles complets** : DeepSeek `7/20 → 20/20` (exécution initiale) et GLM `5/20 → 20/20` (état final), avec les quatre scénarios et 20 assertions par modèle ; sorties et verdicts conservés sous `evals/results/`.
  2. **Flint essayé en second** : eval 2 a expiré deux fois (`EXIT=124`, `timeout 180`, JSONL réduit à `step_start`). Les traces `*.timeout*.{txt,jsonl}` sont conservées ; GLM a pris le relais comme second modèle complet, conformément à la consigne de bascule.
  3. **Corrections issues du second modèle** : bloc `Job et statut`, brief de 5 lignes écrit, 3–5 questions avec options, direction structurelle testée par substitution, `## Limites` rédigée, `prefers-reduced-motion` avec `animation: none`, suppression de la checklist et du tableau de portes recopiés, `Exécuté`/`Non exécuté` sans faux `statut 0`.
  4. **Copie Lab** : `SKILL.md`, `README.md`, `VALIDATION.md` et les cinq références sont identiques à la source (`cmp` et MD5).
  5. **Paquet final** : `dist/web-site.skill` et `dist/web-site.zip`, 9 fichiers, `SKILL.md` identique à la source, MD5 des deux archives identique.
- **Preuves d'exécution** : `docs/skills/web-site/VALIDATION.md`, `docs/skills/web-site/evals/REPORT.md`, `evals/results/verdicts-glm-5.3-flash-free.json`.
- **Limites assumées** : notation manuelle non aveugle ; réponses en texte sans code, donc pas de mesure de rendu réelle ; Flint sans score complet (eval 2 expirée) ; modèles payants indisponibles (`Insufficient account funds`, `Model access is disabled`) ; paquet non testé par un consommateur externe.
- **Statut** : ACCEPTEE

## DEC-032 — Démarrage automatique de l'ISO Debian 13 : `ontimeout` graphique sans `speakup`

- **Date** : 2026-11-08
- **Auteur** : Agent A
- **Contexte** : l'ISO ne démarrait pas automatiquement. La cause reproduite en QEMU BIOS était `spkgtk.cfg`, inclus en dernier, dont `timeout 1` et `ontimeout ... speakup.synth=soft` lançaient l'installateur vocal. Supprimer l'`ontimeout` laissait le menu attendre une touche ; `default installgui` dans `isolinux.cfg` échouait au prompt.
- **Décision** :
  1. Conserver `vesamenu.c32` et toutes les entrées manuelles, y compris l'installation vocale.
  2. Remplacer uniquement l'`ontimeout` de `spkgtk.cfg` par le chemin direct du noyau, l'initrd graphique, `preseed/file=/preseed.cfg` et les arguments automatiques, sans `speakup`.
  3. Vérifier dans le build et dans l'ISO finale : absence de `speakup` dans l'`ontimeout`, présence de l'initrd graphique, `default installgui` dans `gtk.cfg`, `vesamenu.c32` dans `isolinux.cfg`.
  4. Conserver le mécanisme éprouvé de Debian (chemin noyau direct) plutôt qu'un label dans `ontimeout`, non résolu dans cette version.
- **Preuves d'exécution** : QEMU BIOS, sans touche → installateur à 60 s ; QEMU UEFI/OVMF → installateur français à 80 s. ISO SHA256 `00f88ac52294c846c450d6fd3a063cc8d959cfc34cb94c36b9ce8b1352787290`. Suite complète 1062 OK, 5 ignorés.
- **Limites assumées** : VirtualBox absent du poste de build ; installation complète non terminée ; délais QEMU TCG non représentatifs de VirtualBox.
- **Statut** : ACCEPTEE

## DEC-033 — ISO Debian 13 : preseed fichier, S30 neutralisé et langue fixée dans localechooser

- **Date** : 2026-11-09
- **Auteur** : Agent A
- **Contexte** : l'ISO 20261108 atteignait l'installateur mais s'arrêtait sur « Select a language ». La question `localechooser/languagelist` est posée avant la lecture fiable du preseed ; le `S30initrd-preseed` de Debian 13 échoue (`Illegal number`) et le preseed présent dans l'initrd n'est pas appliqué de façon fiable.
- **Décision** :
  1. Réactiver `preseed/file=/cdrom/preseed.cfg` sur les lignes noyau BIOS et UEFI : le preseed fichier devient la source de vérité, sans dépendre du `S30`.
  2. Neutraliser `S30initrd-preseed` dans les deux initrds (`/install.amd/initrd.gz` et `/install.amd/gtk/initrd.gz`) par un script no-op, pour supprimer l'erreur et le double traitement.
  3. Patcher `localechooser` dans les deux initrds : remplacer `db_input critical $tpl_languagelist` par `db_set $tpl_languagelist fr` et `db_fset $tpl_languagelist seen true`, afin que la question ne soit plus posée.
  4. Conserver `auto=true`, `language=fr`, `country=FR`, `locale=fr_FR.UTF-8` et `frontend=text` sur la ligne noyau comme secours.
  5. Vérifier dans le build l'application du patch, la validité syntaxique de `localechooser` et la présence de `preseed/file` dans les menus BIOS et UEFI.
- **Preuves d'exécution** : test minimal `LANG_COUNT=0`, installateur atteignant le menu principal ; build 20261109 en cours. Les preuves finales (SHA256, installation complète, premier boot) seront consignées dans `H-019` et le rapport.
- **Limites assumées** : la validation complète QEMU UEFI/TCG est encore en cours ; aucun test VirtualBox ; build sur WSL avec un disque 9p lent.
- **Statut** : ACCEPTEE

### Addendum 2026-11-10 — cause vraie du blocage (Agent A)

- **Constat** : avec l'ISO 20261109, l'installation UEFI/TCG atteignait GRUB puis restait sur `[!!] Terminer l'installation` au corps `<ERR>`. La note `finish-install/reboot_in_progress` était suspectée à tort : la base cdebconf invitée (`/var/lib/cdebconf/questions.dat`) la montre avec `Value: (vide)`, `Owners: d-i, finish-install`, `Flags: seen` — elle était déjà neutralisée.
- **Cause vraie** : `hardware/packages/usb-installer/miles-late.sh` commençait par `#!/bin/bash`, mais l'environnement d'installation Debian ne fournit que `dash` (`/bin/sh`). L'exécution du `late_command` (`log-output sh -c "$command"` dans `/bin/preseed_command`) échouait avec `env: can't execute 'bash'` (visible dans le syslog VT4), et `preseed_command` affichait alors le dialogue `preseed/command_failed` (`Type: error`, `db_input critical` + `db_go`), qui bloque la fin d'installation.
- **Correctif** : `miles-late.sh` passe en `#!/bin/sh` avec un corps strictement POSIX (variable `CDPATH` renommée `CANDIDAT`), vérifié `dash -n` (SYNTAX_OK) ; le `sed` grub `\1\2` est confirmé correct. Rebuild ISO 20261110 non interactif (hashes SHA-512 recalculés des mêmes mots de passe, sels `miles1`/`miles2`), ISO vérifiée : 798294016 o, SHA256 `dfa8257a4e74e1b387ca79f8b92fb25696903117cf1b9a2254bdda6603517c5f`, `/files/miles-late.sh` extrait avec `#!/bin/sh` en première ligne.
- **Preuves** : installation UEFI/TCG n°3 sans touche → `Requesting system reboot`, zéro occurrence de `Terminer` dans le log série (107690 o) ; premier boot → session `miles`, `/var/lib/miles-late-ran` (`... OK`), `/var/lib/miles-provision.done`, service `miles` enabled, `/opt/Milescorp` 115 entrées `miles:miles`. Captures : `logs/firstboot-screen.png`, transcript `logs/guest-exec.log` (vérifiés sans identifiant).
- **Réserve reportée** : `miles.py` n'est présent dans la payload qu'en `worktrees/<id>/miles.py` (artefact), et `data/` manque → `miles.service` enabled mais en boucle de redémarrage. Contenu de payload à traiter dans un lot ultérieur, pas dans DEC-033.

## DEC-034 — ISO Debian 13 : `.env` provisionné pour `ReadWritePaths`, service `miles` actif au premier boot

- **Date** : 2026-11-11
- **Auteur** : Agent A
- **Contexte** : avec l'ISO 20261110 (payload corrigée : `miles.py` au sommet, `data/` présent, service enabled), `miles.service` restait en boucle `auto-restart` (`NRestarts=128`) malgré `miles-provision.done`. L'application elle-même fonctionne (lancement manuel hors sandbox : jeton affiché, `Interface web MILES sur 127.0.0.1:8081`).
- **Cause établie** : `systemctl status miles` → `code=exited, status=226/NAMESPACE` (échec du montage du sandbox systemd, avant tout `ExecStart`). L'unité porte `ReadWritePaths=/opt/Milescorp/data /opt/Milescorp/.env` mais `/opt/Milescorp/.env` n'existait pas (`ENV_MISSING`, seul `.env.example` présent) : systemd refuse un chemin `ReadWritePaths` inexistant. Le commentaire historique « échec normal si .env absent » est faux : l'échec est définitif et précède `--setup`.
- **Décision** :
  1. `miles-provision.sh` crée `/opt/Milescorp/.env` vide (clé API saisie plus tard via `--setup`) avant le `chown` ; le message de premier démarrage est corrigé en conséquence.
  2. `miles-late.sh` applique `chmod 644` à l'unité `miles-provision.service` installée (avertissement systemd « marked executable » supprimé, cause : `cp` depuis l'ISO).
  3. `build-iso.sh` : prune `*/.manus` à tout niveau (le garde-fou rejetait l'ISO à cause de `CLIP/.manus/…`) ; build sur ext4 natif (`WORK` sur `/home/stanc`, pas sur le montage 9P où l'extraction des initrds restait bloquée en `D`).
- **Preuves d'exécution** : ISO 20261111 (812974080 o, SHA256 `a6a4653ae59a0cd2deec6fa25b126851449dc6bc9871f836c8a629416fd2299c`, 1004 fichiers, 0 `manus`, `miles.py` au sommet, `touch "$DEST/.env"` ligne 54 vérifié dans le tarball). Installation n°5 sans touche → `Requesting system reboot`, zéro `Terminer`. Premier boot : `provision.done` 10:47:36, `is-enabled` → enabled, `is-active` → **active**, `NRestarts=0`, `ActiveState=active`, `SubState=running`, `curl 127.0.0.1:8080` → **HTTP:200**, 17 entrées, `ENV_OK`. Captures `logs/firstboot-screen.png` + transcript `logs/guest-exec.log` (10 blocs) vérifiés CLEAN.
- **Limites assumées** : `HEAD /` répond `501` (l'application ne gère pas `HEAD`, hors périmètre) ; `sendkey` sur keymap FR perd `{`/`}` (preuve HTTP chiffrée portée par la série, écran par `curl -sI`) ; VirtualBox absent, KVM indisponible, TCG ; aucun commit/push.
- **Statut** : ACCEPTEE

## DEC-035 — Image Live USB : construction manuelle, persistance par partition, console comme interface principale

- **Date** : 2026-11-24
- **Décidé par** : Agent A
- **Contexte** : livrer une clé USB 64 Go exécutant MILES sans installation disque, en français/AZERTY, avec persistance et démarrage automatique de l'assistant.
- **Décisions** :
  1. **Image live construite à la main** (`debootstrap` → `mksquashfs` → `xorriso`) : `live-build` n'est pas en place sur le poste et la chaîne doit rester lisible et rejouable (`.usb-iso-build/README.md`).
  2. **Persistance = seconde partition étiquetée `persistence`** contenant `persistence.conf` (`/ union`). Sans ce fichier, `live-boot` referme la partition après montage : les deux sont donc exigés par le guide.
  3. **Interface principale = console MILES auto-démarrée sur tty1** : l'image ne contient ni serveur graphique ni navigateur (choix « le plus fiable, le moins lent »). `miles.service` (127.0.0.1:8080) et `miles-companion.service` (127.0.0.1:8787) restent actifs, en boucle locale uniquement.
  4. **Défauts fail-closed** : aucun secret embarqué (`MILES_PROVIDER=local`, jeton web vide), `ssh` installé mais désactivé, exposition du LAN toujours soumise à l'audit B.
  5. **`sudo` sans mot de passe** pour l'utilisateur `miles` : acceptable sur une clé live personnelle, **jamais** sur une machine installée.
- **Alternatives écartées** : live-build (indisponible), session graphique (lente et fragile sur clé), fichier de persistance posé sur la partition ISO (live-boot attend une partition dédiée).
- **Conséquences** : `docs/installation/LIVE_USB.md` fait foi pour l'écriture de la clé, la persistance et le premier `miles --setup` ; la chaîne et ses tests sont documentés dans `.usb-iso-build/README.md`.
