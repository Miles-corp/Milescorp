# docs/coordination/HANDOFF.md — Procédure de transmission entre agents

> Point d'entrée des agents : `AGENT_START.md` à la racine du dépôt ; état courant des missions : `MISSIONS_REGISTRY.md`.

Procédure à suivre par chaque agent à la fin de sa session de travail, afin que l'autre agent puisse reprendre le contexte sans perte d'information.

## 1. Avant de quitter

1. Lire `AGENTS.md` (règle 10 et 14) pour s'assurer que les erreurs, limites et éléments restants sont documentés.
2. Mettre à jour `docs/coordination/TASKS.md` :
   - Statut de chaque tâche travaillée (`TODO`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `CANCELLED`).
   - `assigned-to`, `fichiers-concernes`, `resultat-attendu`, `date-debut`, `date-fin`.
   - `bloque-par` si une tâche est bloquée, avec explication.
3. Mettre à jour `docs/coordination/STATUS.md` :
   - État général du projet.
   - Prochain objectif clair.
   - Liste des tâches actives et blocages.
4. Consigner toute décision d'architecture dans `docs/coordination/DECISIONS.md` (règle AGENTS.md n°7).
5. Rédiger un compte rendu suivant `docs/coordination/REPORT_TEMPLATE.md` si un livrable est produit.
6. Relire son propre diff (`git diff`) avant de committer localement.
7. Committer localement les documents modifiés (pas de push sans accord explicite).

## 2. Format de compte rendu de transfert (H-###)

### H-001 — 2026-10-19 — Agent X → Agent Y
**Tâche :** TASK-### — …
**Travail réalisé :** …
**Fichiers modifiés :** …
**Commits :** …
**Tests exécutés :** …
**Problèmes restants :** …
**Prochaine action recommandée :** …

## 6. Comptes rendus

### H-002 — 2026-10-21 — Agent A → Agent B

**Tâche :** TASK-DEV-018 (correction D1) ; TASK-DEV-019 (audit independant) transferee.

**Travail réalisé :** diagnostic du défaut D1 (divergence de session entre l'emission du grant et sa verification), correction d'une ligne dans `app/orchestration/runner.py::_ensure_authorization`, jeu de 6 tests de regression, execution du scenario web reel, redaction du rapport de correction.

**Fichiers modifiés :** `app/orchestration/runner.py` ; `tests/test_mission_web_authorization.py` (nouveau) ; `docs/reports/PHASE_6_3B_D1_FIX_AGENT_A.md` (nouveau) ; `docs/user_guide/MILES_PLAN_DE_TEST_PHASE_6.md` ; `docs/coordination/{TASKS,STATUS,MESSAGES}.md`.

**Commits :** `6b736d7` — `fix(orchestrateur): autoriser la mission web avec la session du client (D1)` — branche `fix/miles-d1-web-authorization`, pousse sur `origin`. Base `fc179ca`. **Aucune fusion** ; `main` (`b9b7e7d`) et `origin/integration/miles-phases-5-6-6-1` (`69bf670`) inchanges.

**Tests exécutés :** 6/6 tests de regression D1 (le test de regression echoue sans le correctif, verifie) ; `test_mission_orchestrator` 73/73 ; `test_mission_bounds` 20/20 ; `test_web_security_phase6_1` 35/35 ; suite complete **534 tests OK (4 ignores)** ; **70 tests d'audit Agent B rejoues tels quels : OK (2 ignores)** ; scenario web reel (vrai serveur) : `completed`, 5 etapes, 5 appels, 1 echange. Non execute : Debian 13 (environnement indisponible).

**Problèmes restants :** D1-bis signale et non corrige (reponse HTTP trompeuse sur jeton d'approbation invalide ; aucune elevation de privilege). D2, D3, D4 hors perimetre. Validation Debian 13 en attente.

**Prochaine action recommandée :** Agent B prend TASK-DEV-019, audite `6b736d7` (lien grant/session, non-reutilisabilite, scenario web complet, non-regression, Debian 13) et rend son avis avant toute fusion.

### H-003 — 2026-10-24 — Agent A → Agent B

**Tâche :** TASK-DEV-022 (préparation d'intégration) ; TASK-DEV-019 toujours en attente côté B.

**Travail réalisé :** vérification SHA de la chaîne post-D1, état des tests/audits, ordre d'intégration proposé avec dépendances et risques de conflits (voir STATUS.md, section « Préparation d'intégration des branches en attente »). Aucune fusion, aucun code modifié, aucun push.

**Fichiers modifiés :** `docs/coordination/{TASKS,STATUS,MESSAGES,HANDOFF}.md` uniquement.

**Commits :** commit de coordination local (branche `fix/miles-d1-web-authorization`), pas de push.

**Tests exécutés :** aucun (mission de documentation) ; enseignée néanmoins de la date du 24/10 : suite complète 685 tests OK (4 ignorés) au sommet `78ac05c` pour la mission diagnostics `/status`/`/provider`.

**Problèmes restants :** `fix/miles-paths-posix-spaces` pointe sur `25baa60` sans commit dédié (branche non poussée) ; `fix/miles-diagnostics` non poussé ; aucun audit B postérieur à `6b736d7` ; Debian 13 toujours indisponible.

**Prochaine action recommandée :** B audite `6b736d7` (TASK-DEV-019) puis, dans l'ordre, `1ef4878` (D1-bis) et `8b9ab15` (contournement P1-6-06) ; ensuite seulement TASK-DEV-023 (intégration ordonnée).

### H-015 — 2026-10-28 — Agent A → Agent B

**Tâche :** TASK-DEV-048 — ISO Debian 13 auto-install + provision MILES (clé USB de A à Z).

**Travail réalisé :**
- Fabrique complète `hardware/packages/usb-installer/` : `preseed.cfg` (installation 100 % automatique, français/Paris, GPT/UEFI, disque cible auto-détecté hors clé cf. Debian #847166, hashes `@@MILES_*@@` injectés à la construction), `miles-provision.sh` + `miles-provision.service` (1er boot : payload → `/opt/Milescorp`, venv, suite de tests, `box_preflight`, `miles.service` durci 127.0.0.1/`ProtectSystem=strict`, marqueur anti-réexécution), `build-iso.sh` (ISO officielle vérifiée SHA256, mode non-interactif `MILES_USER_HASH`/`MILES_ROOT_HASH` + interactif, payload liste-de-fichiers anti-auto-inclusion < 40 Mo, injection initrd, menus BIOS+UEFI coupés, xorriso journal COMPLET), `README.md`, `CHECKLIST_TEST_VM.md` (15 points pour le test VirtualBox).
- `scripts/restore-usb.ps1` : retour de la clé en clé normale (disque amovible 4-256 Go uniquement, confirmation OUI, syntaxe vérifiée).
- Corrections : `pc-miles/install.sh` (`python3 box_preflight.sh` → `bash`), `.env.example` racine étendu aux 30 variables + paquet dérivé (`tests/test_env_example_alignment.py`, 4 tests anti-dérive), `.gitignore` (`releases/`, `.usb-iso-build/`).
- **Bug critique corrigé** : `miles.py` n'importait pas `os` et appelait `is_configured()` (un `@property`) → le refus `--web-lan` aurait planter ; contrôle fail-closed replacé en tête de `main()` (jeton PERSISTANT exigé + IP privée, refus avant tout accès disque). `tests/test_web_lan.py` : **13/13**, dont les tests exigés par DEC-016 §2 prouvant le refus sans jeton.

**Fichiers modifiés :** `miles.py`, `.gitignore`, `.env.example`, `hardware/packages/usb-installer/**` (6 fichiers), `hardware/packages/pc-miles/{install.sh,.env.example}`, `scripts/restore-usb.ps1`, `tests/{test_web_lan,test_env_example_alignment}.py`, `docs/coordination/{TASKS,HANDOFF}.md`.

**Commits :** commit local unique (détail dans `git log`), **pas de push**.

**Tests exécutés :** suite complète **566 tests OK / 4 ignorés** (Windows, Python 3.14) ; ISO vérifiée par script indépendant (contenu, 20 append `auto=true`, grub timeout=0, El Torito BIOS+UEFI, hashes `$6$`, zéro jeton résiduel).

**ISO livrée :** `releases/miles-debian13-autoinstall-20261028.iso` — 805 634 048 o, SHA256 `07b8d9718099dc8c959243b864ed58b3f1cfb3924067ee9b2ac2763938b55259` (+ `SHA256-ISO-SUMS`). Mots de passe de **TEST** embarqués (hashés) : `miles` / `Miles-Test-2026`, root de secours `Root-Test-2026`. Pour le HP réel : soit on garde et on change après (`passwd`), soit rebuild interactif avec les vrais.

**Problèmes restants / limites :**
1. **Test VirtualBox NON exécuté** (délégué à l'ami, checklist fournie) — condition avant de graver la clé.
2. **Firmware ESP32 toujours non compilé** (DEC-016 §3) — hors périmètre de cette tâche.
3. Compilation/flash réels et test HP ProDesk : après le retour VM.
4. **`BOX_DEBIAN_SETUP.md` n'existe que sur cette branche** (absent de `main`) — à faire remonter à l'intégration.
5. Ligne `MAP_ISOLINUX` : les 20 `append` sont modifiés depuis TOUS `/isolinux/*.cfg` (isolinux.cfg seul n'en contenait pas).

**Prochaine action recommandée :** transférer ISO + `SHA256-ISO-SUMS` + `CHECKLIST_TEST_VM.md` à l'ami ; verdict VERT → gravure Rufus → test HP (F9, Ethernet) → `--setup` ; puis push sur accord, audit B de l'ouverture réseau reste requis avant tout LAN.

## 3. Transmission de la main

- Prévenir l'autre agent (par le canal convenu hors dépôt, ex. message) qu'une mise à jour est disponible sur GitHub ou dans le clone partagé.
- L'autre agent doit alors :
  1. Lire `AGENTS.md`, `STATUS.md`, `TASKS.md` et les décisions pertinentes.
  2. `git fetch origin` et comparer avec son état local.
  3. Ne pas reprendre une tâche `IN_PROGRESS` attribuée à l'autre agent sans coordination explicite.

## 4. Ce qui doit être transmis (minimum)

- Quelles tâches sont terminées, en cours, bloquées.
- Quels fichiers ont été modifiés ou créés.
- Quels contrôles ont été exécutés et avec quel résultat.
- Quelles questions restent ouvertes pour l'autre agent.
- Quelles décisions doivent être prises par un humain.

## 5. Interdictions

- Ne jamais considérer une conversation OpenCode comme la source de vérité partagée.
- Ne jamais écraser le travail local de l'autre agent.
- Ne jamais publier de secrets, clés API, mots de passe ou données personnelles.
