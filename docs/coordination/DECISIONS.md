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
