# docs/reports/MILES_V1_VERIFICATION_AGENT_B.md — Vérification indépendante MILES V1 (Agent B)

> **Révision 5 — contre-audit final D-C1 / D-C2 du commit `9a53652`, 2026-10-20.**
> Révision 4 : contre-audit du commit `95dac41` (R3 + R6) — D-C1 et D-C2 confirmés.
> Révision 3 : finalisation de l'audit V1 et validation Debian 13.
> Révision 2 : audit de suivi après les corrections d'Agent A.
> Révision 1 : audit initial du commit `be9f317` (défauts D-B1 à D-B5 ouverts).

## 0quater. Contre-audit final D-C1 / D-C2 — commit `9a53652` — synthèse

### SHA exacts audités

| Rôle | SHA | Branche |
|------|-----|---------|
| **Commit de développement audité** | **`9a536523dabe29ebe5840bc85fa09cd08d8058f6`** (`docs+test: correctif D-C1 (detection symlink) et documentation D-C2`) | `origin/feature/miles-v1-conversation-persistence` |
| Précédent audité (révision 4) | `95dac41fabde232901dd3c806c6edaec485c39c3` | idem |
| Correctif d'Agent B rebasé par Agent A | `8d30809a6cac699282b0d81d9b756dac0f2451c1` | idem |
| Correctif d'Agent B d'origine | `c548e3b6ca8c45a4529641510b4b2eb905f73f4d` | `audit/agent-b-v1-review` |
| Branche d'audit d'Agent B | `9d8f9a4c38e88e20519fd067f7009bf22ef7bc41` | `origin/audit/agent-b-v1-review` |
| `main` | `b5e100725efe3886a742d2eb13c2bd4bf185733f` — **inchangée** | `main` |

**Note sur `c548e3b`.** Il n'est **pas** un ancêtre direct de la branche V1 : Agent A l'a **rebasé** sur `95dac41`, produisant le SHA `8d30809`. Conformément à la consigne (« ne considère pas la simple présence du commit comme une preuve suffisante »), j'ai vérifié **le code et les résultats d'exécution**, pas l'ascendance.

### Résultats complets des tests

| Exécution | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Durée |
|---|---|---|---|---|---|---|
| **Debian 13** (`9a53652`) | **338** | **338** | 0 | 0 | **0** | 35,3 s |
| Windows (`9a53652`) | 338 | 338 | 0 | 0 | 4 | 34,4 s |

Les 4 skips Windows sont **justifiés et attendus** : 3 tests de liens symboliques (création de lien symbolique exigeant le privilège « Développeur » sous Windows) et 1 test de comptage de descripteurs (`/proc/self/fd` absent). Le message de skip indique correctement « Test exécuté sous Debian 13 » — et c'est désormais **exact**, puisque ces tests s'y exécutent bel et bien.

### D-C1 — RÉSOLU : les tests de liens symboliques ne sont plus ignorés

| Preuve | Résultat |
|--------|----------|
| Code de la détection | `_symlink_supported()` : temporaire créé, `dst` correct (`<tmp>/cible`), `os.symlink("cible", probe)`, nettoyage garanti par `finally: shutil.rmtree(...)`. Plus aucun usage d'`os.devnull` **en code** (seule mention dans la docstring qui explique pourquoi ne pas l'utiliser). |
| Exécution sous Debian 13 | `python3 -m unittest tests.test_path_security -v` → **OK, 0 ignoré** |
| Compte global de skips sous Debian 13 | **0 ligne « skipped »** dans toute la suite |
| Preuve fonctionnelle (hors test) | **Lien symbolique sortant réellement créé** pointant vers `/tmp/…/out` → `resolve_authorized_path` → **REFUSE** (le confinement tient) |
| Nouveau module de test | `tests/test_symlink_detection.py` (Agent A) → **OK** : le détecteur lui-même est désormais testé, ce qui empêche la régression |

### D-C2 — RÉSOLU : la documentation correspond au code

| Vérification | Résultat |
|---|---|
| Variables lues depuis le `.env` (`env_mapping` du code) | **17** |
| Variables lues hors mapping (environnement du processus) | **2** → `MILES_ENV_FILE`, `MILES_CONFIG` |
| **Total lu par le code** | **19** |
| Annoncé dans `INSTALL.md` | **19** (dont « 17 variables de configuration ») → **cohérent** |
| Comportement réel de `MILES_ENV_FILE` | **Ignoré** dans un `.env` : démonstration → valeur lue `42` (dans `.env`) et non `999` (dans `autre.env`) |
| Correction apportée par Agent A | Les 2 variables de chemin sont désormais dans une **section dédiée** « Variables de chemin de fichier (lues uniquement de l'environnement) », avec l'explication *pourquoi* (impossible de localiser le `.env` par une variable qu'il contient), un avertissement que les écrire dans le `.env` est **sans effet**, et les 3 formulations concernées (introduction du tableau, section « variables non reconnues », puce « Limites ») ont été corrigées. |
| Tests documentaires | `tests/test_docs_configuration.py` → **OK** (11 tests, dont le compte 19/17 et la bidirectionalité doc↔code) |

### Non-régression (scénarios indépendants, Debian 13)

| Point | Résultat |
|---|---|
| D-B1 | ✅ `recreated`, 0 orphelin, 1 conversation visible |
| D-B2 | ✅ `assertEqual(413)` et `assertEqual(400)` présents, `_assert_refused` **absent**, `send_body=False` présent, contrôle de limite **avant** `rfile.read` |
| D-B3 | ✅ `PRAGMA foreign_keys=1`, insertion fantôme refusée, messages 2→0 |
| D-B4 | ✅ `close()` en sortie normale **et** en exception |
| D-B5 | ✅ `add_user_message` → `False` sur panne d'écriture |
| `/clear` | ✅ base 2→0, restauration après redémarrage = 0 |
| Confinement | ✅ hors racine REFUSÉ, dans racine ACCEPTÉ, **lien symbolique sortant REFUSÉ** |
| Transactions | ✅ autocommit, 50 écritures, séquences 1..50 contiguës |
| R3 | ✅ variables non mappées ignorées, process env prioritaire sur `.env` |
| R6 | ✅ CLI == Web sur 6 cas, **aucune fuite**, détail assaini (`AIProviderError: echec [REDACTED]`) |

### Défauts résiduels

| ID | Statut |
|----|--------|
| D-C1 | ✅ **RÉSOLU** — plus de défaut résiduel de ce côté |
| D-C2 | ✅ **RÉSOLU** |
| D-B1→D-B5, R2, R3, R4, R5, R6 | ✅ résolus, non réintroduits |

**Aucun défaut résiduel identifié sur le commit `9a53652`.**

### Limites de validation

| Limite | Raison |
|--------|--------|
| Test d'inférence réel (Groq) | **Non autorisé** — coût API ; aucun appel payant effectué |
| Fournisseur local (llama.cpp) | Hors périmètre ; aucun modèle téléchargé ni installé |
| Dépendances vocales | `pyttsx3` / `speech_recognition` non installées (non nécessaires : les 6 tests de voix passent en vérifiant le comportement « dépendances absentes ») |
| Exécution Windows | Les 4 tests ignorés sous Windows ne sont pas des échecs : ce sont des limites de plateforme ; leur exécution réelle est prouvée sous Debian 13 |
| Périmètre | Voix, actions autonomes et performance non évalués (hors périmètre V1) |

### Verdict global — contre-audit `9a53652`

# VALIDÉ POUR LE PÉRIMÈTRE ANNONCÉ

**D-C1 et D-C2 sont résolus, vérifiés par le code et par l'exécution, sans réserve.** La suite complète passe **338/338 avec 0 test ignoré sous Debian 13** ; les 4 skips restants sous Windows sont des limites de plateforme réelles et documentées, et les tests concernés s'exécutent effectivement sous Debian 13. Aucune non-régression D-B1→D-B5, R2→R6 n'a été introduite, et les assertions de sécurité n'ont pas été affaiblies.

La garantie **S-005** (confinement des chemins tenant compte des liens symboliques) est désormais **réellement prouvée** : le test échoue si la protection est retirée (10 échecs mesurés en révision 3) et le cas réel d'un lien sortant est refusé.

**Reste à faire, hors périmètre de ce contre-audit :** fusionner `9a53652` dans `main` (autorisation explicite requise) ; décider d'un éventuel test d'inférence réel (coût API).

---

## 0ter. Contre-audit du commit `95dac41` — synthèse

| Élément | Valeur vérifiée |
|---------|-----------------|
| Commit audité | `95dac41fabde232901dd3c806c6edaec485c39c3` (`docs+fix: R3 documentation INSTALL.md et R6 erreurs fournisseur`, DripMind, 2026-10-20 14:48) |
| Branche | `origin/feature/miles-v1-conversation-persistence` (avancée de `7dacdfe` → `95dac41`) |
| Diff | 9 fichiers, +692/−11 : `app/ai_providers/public_errors.py` (nouveau), `app/interface/cli.py`, `app/interface/web.py`, `docs/installation/INSTALL.md`, `tests/test_docs_configuration.py` (nouveau, 11 tests), `tests/test_provider_errors.py` (nouveau), 2 documents de coordination, 1 rapport |
| Environnement | Debian GNU/Linux 13 (trixie), noyau `6.12.113+deb13-amd64`, Python 3.13.5, stdlib uniquement, worktree isolé `/root/miles-audit`, dépôt local propre |
| Ma branche d'audit | `audit/agent-b-v1-review` @ `e98c320` — **synchronisée** avec le distant avant et après session |

### Faits vérifiés — suite de tests Debian 13

| Mesure | Valeur |
|--------|--------|
| Tests exécutés | **328** |
| Réussis | **328** |
| Échoués | **0** |
| Erreurs | **0** |
| Ignorés | **3** (les 3 tests de liens symboliques — **pour un motif erroné**, voir D-C1) |
| Durée | 38,4 s |

Le total de **328** correspond exactement à l'annonce d'Agent A. L'écart avec mes 302 tests précédents vient des 26 nouveaux tests de `test_docs_configuration.py` (11) et `test_provider_errors.py` (15).

### Écarts de plateforme

| Plateforme | Exécutés | Réussis | Ignorés | Raison des skips |
|---|---|---|---|---|
| **Debian 13** | 328 | 328 | **3** | Les 3 tests de liens symboliques — **motif erroné** (D-C1). Le message affiche « Test exécuté sous Debian 13 » alors que l'exécution a lieu sous Debian 13. |
| Windows | 328 | 328 | 7 | 3 liens symboliques (privilège « Développeur » requis) + 4 tests de voix liés à `pyttsx3`/`speech_recognition` absents. |

**Correction de la mission :** `tests/test_voice.py` comporte **6** tests (et non 4) et **aucun n'est ignoré** — ils s'exécutent et passent, car le cas « dépendances vocales absentes → `VoiceUnavailableError` » est précisément le comportement attendu, vérifié sans installation. Aucun paquet n'a été installé.

### D-C1 — Les tests de liens symboliques restent ignorés sous Debian 13 (défaut confirmé)

| Élément | Valeur |
|---|---|
| **Priorité** | **Moyenne** |
| **Fichiers** | `tests/test_path_security.py` (lignes 31-37, détection) ; `app/security/paths.py` (protection, non modifiée) |
| **Branches concernées** | `origin/feature/miles-v1-conversation-persistence` (`95dac41`) → **défectueuse** ; `origin/fix/agent-b-s002-s004-s005-s006` → **défectueuse** ; `origin/audit/agent-b-v1-review` → **corrigée** ; `origin/main` et `origin/work/agent-a-phase4-audit` → fichier de test absent (antérieur à S-005) |
| **Scénario de reproduction** | `python3 -m unittest tests.test_path_security -v` sur Debian 13 avec le commit `95dac41` |
| **Comportement attendu** | Les 3 tests de confinement par lien symbolique s'exécutent sous Linux (la création de liens symboliques y est possible nativement) |
| **Comportement observé** | Les 3 tests sont **ignorés** avec le motif « Création de lien symbolique non permise sur cette plateforme (**Windows** requiert un privilège). Test exécuté sous Debian 13. » — message contradictoire, puisqu'on est sous Debian 13 |
| **Preuve disponible** | Contrôle en casse-sensible du contenu de `tests/test_path_security.py` à `95dac41` : la détection est toujours `os.symlink("cible", os.devnull)` → tente de créer le lien **à `/dev/null`** (chemin déjà existant) → `FileExistsError` (une `OSError`) → faux négatif « symlink non supporté ». Vérifié sur Debian 13 : `os.symlink("cible", os.devnull)` → `FileExistsError: [Errno 17] File exists: 'cible' -> '/dev/null'`, alors qu'une création correcte (`dst` dans un temporaire) réussit. |
| **Impact** | La **preuve centrale de S-005** (le confinement des chemins tient compte des liens symboliques) **reste non exécutée sur toutes les plateformes**. Le rapport de Phase 4 d'Agent A et le rapport V1 d'Agent A présentent donc cette garantie comme validée, alors qu'elle ne l'est pas. |
| **Correction recommandée** | Déjà écrite et **publiée par Agent B** : `c548e3b` (intégré dans `3029f3f`) remplace la détection par `_symlink_supported()` (sonde dans un répertoire temporaire, `dst` correct, nettoyage garanti). Il reste à **fusionner** `audit/agent-b-v1-review` dans la branche V1 puis dans `main` — aucune correction de production n'est nécessaire. |
| **Test de non-régression requis** | `tests.test_path_security` doit s'exécuter **sans skip** sous Debian 13 (0 ignoré) et la mutation de `is_within()` doit faire échouer 10 tests (déjà vérifié en révision 3). |

### D-C2 — Nuance de formulation dans la documentation R3 (faible)

| Élément | Valeur |
|---|---|
| **Priorité** | **Faible** (documentation) |
| **Fichier** | `docs/installation/INSTALL.md` — section « 3ter. Sources de configuration et variables reconnues » |
| **Scénario** | Un `.env` contenant `MILES_ENV_FILE=/tmp/r3/autre.env` |
| **Comportement attendu** | Le tableau liste ces variables sous « Seules les variables `MILES_*` listées ci-dessous sont **lues depuis le fichier `.env`** » |
| **Comportement observé** | `MILES_ENV_FILE` et `MILES_CONFIG` sont lues **exclusivement de l'environnement du processus** (`os.environ.get(...)`), jamais du `.env` : impossible d'utiliser une variable du `.env` pour localiser le `.env`. Démonstration : avec `MILES_ENV_FILE` pointant vers `.env`, la valeur lue est `42` (dans `.env`) et non `999` (dans `autre.env`). |
| **Preuve disponible** | Exécution réelle sur Debian 13 (§ R3 ci-dessus) ; lecture du code `settings.py` (2 lectures directes hors `env_mapping`) |
| **Correction recommandée** | Distinguer visuellement les 2 variables de chemin dans le tableau (colonne « lue depuis le `.env` ? » : non) ou les sortir du tableau des variables lues depuis le `.env`. Le décompte **19 = 17 + 2** et la puce dédiée qui suit sont **exacts** : l'incohérence est uniquement dans l'introduction du tableau. |
| **Test de non-régression requis** | Assert que `MILES_ENV_FILE` présent dans un `.env` est **ignoré** (le test documentaire existant couvre déjà les 19/17 et l'ignorance des variables non mappées). |

### Points validés sans réserve

| Point | Preuve (Debian 13, `95dac41`) |
|---|---|
| **R3 — 4 sources et priorité** | Process env > `.env` > JSON > défauts : vérifié par `tests/test_docs_configuration.py` (4 tests de priorité) — **tous passent** |
| **R3 — décompte des variables** | **19 = 17 + 2** : `env_mapping` du code = 17 ; `MILES_ENV_FILE` et `MILES_CONFIG` lus hors mapping = 2. Le compte d'Agent A (19) est **exact** — mon estimation antérieure de 18 était erronée et est rectifiée ici. |
| **R3 — variables non mappées** | `HTTP_PROXY` dans un `.env` → absent de `os.environ` et non lu par `Settings` (vérifié par exécution et par `test_variable_non_reconnue_ignoree`) |
| **R3 — procédure proxy** | `export HTTP_PROXY=…` puis `urllib.request.getproxies()` → `http://proxy.exemple:3128` : la procédure documentée est **correcte** (`test_proxy_du_processus_est_utilise_par_urllib` passe) |
| **R6 — CLI et web alignés** | 8 cas d'erreur traités → **CLI et web exposent un message public identique** dans les 8 cas |
| **R6 — aucune fuite** | Aucun message public ne contient de code HTTP, d'URL, de corps de réponse ni de secret (contrôle sur 8 cas × 7 motifs) |
| **R6 — détail technique assaini** | `technical_detail()` → `AIProviderError: echec avec [REDACTED]` : le secret est absent, le type d'exception conservé pour le diagnostic |
| **R6 — scénario réel** | Serveur simulé renvoyant HTTP 401 + corps `body!` → stdout : `Erreur du fournisseur IA : authentification refusée.` ; `401`, `body!` et `Erreur HTTP` **absents** de la sortie. Le détail va dans le journal `miles.cli`. |
| **Non-régression D-B1** | `attach_transcript(t,"INEXISTANT")` → `recreated`, 0 orphelin, 1 conversation visible |
| **Non-régression D-B2** | `assertEqual(status, 413)` et `assertEqual(status, 400)` présents, `_assert_refused` **absent**, `send_body=False` présent : les assertions n'ont pas été affaiblies |
| **Non-régression D-B3** | `PRAGMA foreign_keys = 1`, insertion fantôme refusée, messages 2 → 0 à la suppression |
| **Non-régression D-B4** | `memory.close()` appelé en sortie normale **et** en exception |
| **Non-régression D-B5** | `_persist` renvoie `False` sur `TranscriptError` et quand `message_id is None` |
| **Non-régression `/clear`** | Messages supprimés de la base (2 → 0) et **non restaurés** après redémarrage (0) |
| **Non-régression confinement** | `/tmp/ailleurs/x.db` refusé, `data/ok.db` accepté |
| **Non-régression transactions** | Autocommit, 50 écritures sans échec, séquences 1..50 contiguës et uniques |
| **Aucun appel payant** | Aucun appel à Groq ni à un autre fournisseur distant ; aucun modèle téléchargé ni installé |

### Tests non exécutés et raisons

| Non exécuté | Raison |
|---|---|
| Inférence réelle (Groq) | **Non autorisé** — coût API ; hors périmètre de ce contre-audit |
| 3 tests de liens symboliques *sur `95dac41`* | **Ignorés par la defective detection** (D-C1) — ils s'exécutent si la correction d'Agent B est fusionnée (prouvé en révision 3 : 0 ignoré) |
| 4 tests de voix sous Windows | Dépendances `pyttsx3`/`speech_recognition` absentes — **non installées volontairement** ; sous Debian 13 ces 6 tests de voix s'exécutent et passent sans installation |

### Verdict global (contre-audit `95dac41`)

**VALIDÉ POUR LE PÉRIMÈTRE ANNONCÉ, AVEC UNE RÉSERVE D-C1 À LEVANT.**

R3 et R6 sont **correctement implémentés et prouvés** : la documentation correspond au code (19 variables, priorités, variables non mappées, proxy), et les erreurs fournisseur ne divulguent plus rien au terminal comme au client HTTP, avec une source de classification unique partagée par le CLI et le web. Aucune non-régression D-B1→D-B5 n'a été introduite.

**Réserve D-C1 (à lever)** : la branche auditée conserve le détecteur de liens symboliques défectueux, ce qui maintient **silencieusement ignorés** les 3 tests qui prouvent le confinement des chemins — la garantie S-005 reste donc invérifiée sur la branche de développement. Le correctif existe déjà et est publié par Agent B : il ne reste qu'à **fusionner `audit/agent-b-v1-review`**.

---

## 0. État réel vérifié (rectificatif)

L'énoncé de la mission annonçait que « le rapport et la correction de détection des liens symboliques sont sur ta branche d'audit **locale, non publiés** ». **Vérification faite : cette information était dépassée.** État réel constaté sur les branches et commits réellement accessibles :

| Élément | État réel constaté |
|---------|--------------------|
| `origin/audit/agent-b-v1-review` | `3029f3fcc1982dd3283766e252c6cb315c2a0fa3` — **la correction symlink y est déjà publiée** |
| Branche locale `audit/agent-b-v1-review` | `3029f3f`, **synchronisée** avec le distant, working tree propre |
| `origin/feature/miles-v1-conversation-persistence` | `7dacdfefe0717602d14144e98bc9bd326d227464` (inchangé) |
| `origin/main` | `b5e100725efe3886a742d2eb13c2bd4bf185733f` (inchangé) |
| Conflit résolu | Un `git pull` lancé hors de l'agent avait créé une fusion (`MERGE_HEAD=fa5384f`) bloquée sur `docs/reports/MILES_V1_VERIFICATION_AGENT_B.md`. Résolu en conservant la révision 2 du rapport, sans réécriture d'historique. Fusion commité `3029f3f` et poussé. |

Les priorités 1 (finaliser le correctif symlink) et 2 (push automatique) étaient donc **déjà réalisées** ; elles ont été revalidées par exécution sur Debian 13, et un nouveau push automatique a été effectué à la fin de cette session (révision 3 du rapport, §9).

## 1. Commits audités

| Audit | Commit audité | Branche distante | État |
|-------|---------------|------------------|-------|
| Révision 1 (initiale) | `be9f31753bca77fd3bdc5d11e3dfa896d7404610` | `feature/miles-v1-conversation-persistence` | Défauts D-B1→D-B5 signalés |
| Révision 2 (suivi) | `7dacdfefe0717602d14144e98bc9bd326d227464` | `feature/miles-v1-conversation-persistence` | Corrections d'Agent A |
| **Révision 3 (finalisation)** | **`7dacdfe`** via la branche d'audit publiée **`3029f3f`** | `audit/agent-b-v1-review` | Validation Debian 13 + correctif symlink |
| Audit initial (contexte) | `e0886a7b926861788805cf69cfdca3ab0a408a30` | `fix/agent-b-s002-s004-s005-s006` | Base de la V1 (S-002→S-006) |
| `origin/main` | `b5e100725efe3886a742d2eb13c2bd4bf185733f` | `main` | **Ne contient pas** la V1 |

**Diff des corrections d'Agent A** (`be9f317` → `7dacdfe`) : 13 fichiers, +996/−87. Un seul commit, chaîne continue, aucune réécriture d'historique. Fichiers touchés : `app/core/conversation.py`, `app/interface/cli.py`, `app/memory/__init__.py`, `app/memory/transcript.py`, `miles.py`, 3 fichiers de tests, 3 documents de coordination, 1 nouveau rapport, 1 nouveau fichier de tests (27 tests).

**Aucun invariant de sécurité affaibli.** Vérifié par lecture du diff et par deux tests de mutation (§4).

## 2. Environnement et commandes

| | Windows | Debian 13 |
|---|---|---|
| Système | Windows | **Debian GNU/Linux 13 (trixie)**, noyau `6.12.113+deb13-amd64` |
| Python | 3.14.7 | **3.13.5** |
| Dépendances | stdlib uniquement | stdlib uniquement (`pip3 list` vide) |
| Accès | poste de l'agent | `ssh -p 2222 miles@127.0.0.1` (mot de passe via `SSH_ASKPASS`), élévation `su` → root |
| Isolation | — | worktree dédié `/root/miles-audit` sur `3029f3f` (copie principale non modifiée) |

Commandes exécutées sur Debian 13 (révision 3) :
```bash
git fetch origin
git worktree add --detach /root/miles-audit 3029f3fcc1982dd3283766e252c6cb315c2a0fa3
cd /root/miles-audit
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_path_security -v
python3 -m unittest tests.test_tool_resources -v
python3 -m unittest tests.test_defects_agent_b -v
```

## 3. Résultats des tests

| Exécution | Exécutés | Réussis | Échoués | Erreurs | Ignorés | Durée |
|-----------|----------|---------|---------|---------|----------|-------|
| **Debian 13, `3029f3f`** (branche d'audit publiée) | **302** | **302** | 0 | 0 | **0** | 36,9 s |
| **Debian 13, `7dacdfe`** (V1 publiée, sans correctif symlink) | 302 | 302 | 0 | 0 | 3 | 43,97 s |
| Debian 13, avec détection `/dev/null` restaurée (mutation B) | 302 | 302 | 0 | 0 | **3** | — |
| Debian 13, avec confinement neutralisé (mutation A) | 21 | 11 | **10** | 0 | 0 | — |
| Windows, `3029f3f` | 302 | 302 | 0 | 0 | 4 | 33,9 s |

**Les 4 tests ignorés sous Windows s'exécutent et passent sous Debian 13** : `test_pas_de_fuite_de_descripteurs` (S-006), `test_lien_symbolique_sortant_refuse`, `test_lien_symbolique_sortant_refuse_par_list_files`, `test_lien_symbolique_interne_accepte` (S-005).

**Aucun test n'est ignoré sous Debian 13.** Sous Windows, les 4 skips restants sont **justifiés** : 3 tests de liens symboliques (privilège « Développeur » requis pour `os.symlink` sous Windows) et 1 test de comptage de descripteurs (`/proc/self/fd` absent). Ces 4 tests **s'exécutent réellement sous Debian 13**.

## 4. Revalidation de D-B1 à D-B5 — scénarios indépendants (révision 3)

Chaque scénario a été écrit par Agent B, sans utiliser les tests d'Agent A, et exécuté sur **Debian 13** sur le commit publié.

| ID | Statut | Preuve (Debian 13, réédition 3) |
|----|--------|-----------------------------------|
| **D-B1** | ✅ **RÉSOLU** | `attach_transcript(t, "INEXISTANT-1")` → statut `recreated` ; `conversation_id` = identifiant réel `e14a269d…` ; messages du fantôme = **0** ; conversations visibles = **1** ; messages de la conversation réelle = 1. Aucun message orphelin. |
| **D-B2** | ✅ **RÉSOLU** | Code : `assertEqual(status, 413)` et `assertEqual(status, 400)` présents ; helper `_assert_refused` **absent** ; contrôle de limite **avant** `self.rfile.read(length)` (vérifié par position dans le source). Test de mutation : 3 échecs. |
| **D-B3** | ✅ **RÉSOLU** | `PRAGMA foreign_keys` = **1** ; insertion avec `conversation_id` fantôme **refusée** (`IntegrityError`) ; `delete_conversation` : 2 messages → **0**, conversation supprimée. |
| **D-B4** | ✅ **RÉSOLU** | `memory.close()` appelé en sortie normale = **True** et en cas d'exception = **True**. |
| **D-B5** | ✅ **RÉSOLU** | Panne d'écriture SQLite réelle (`DROP TABLE`) → `add_user_message` retourne **False** ; message conservé en mémoire mais **absent** de la base. Rôle invalide → `TranscriptError` rattrapée → `False`. |

## 5. Tests de mutation — les tests couvrent-ils réellement le risque ?

Deux mutations ont été appliquées sur le code **de production** puis la suite relancée, sur Debian 13.

### Mutation A — confinement des chemins neutralisé (`is_within()` renvoie toujours `True`)
```
FAILED (failures=10)
```
**10 tests échouent** : le confinement des chemins est couvert bien au-delà des 3 tests de liens symboliques.

### Mutation B — limite du corps HTTP désactivée (`if length > MAX_BODY_BYTES and False`)
```
FAIL: test_lecture_bornee_a_la_limite
FAIL: test_limite_depassee_refusee_en_413
Ran 9 tests — FAILED (failures=3)
```

### Mutation C — détection des liens symboliques restaurée à la version `/dev/null`
```
test_lien_symbolique_sortant_refuse … skipped
test_lien_symbolique_sortant_refuse_par_list_files … skipped
test_lien_symbolique_interne_accepte … skipped
OK (skipped=3)
```
Cette troisième mutation **prouve que mon correctif est précisément ce qui fait exécuter ces tests** : sans lui, ils sont de nouveau silencieusement ignorés.

Code de production et fichier de test restaurés après chaque mutation (`git diff` vide, worktree propre).

## 6. Défaut trouvé dans MON propre code de test (corrigé et publié)

**Constat : `tests/test_path_security.py` ignorait les tests de liens symboliques sur TOUTES les plateformes, y compris Debian 13.**

| Élément | Valeur |
|---------|--------|
| Fichier | `tests/test_path_security.py` (commit `91ed8c3`, S-005 — code de l'agent B) |
| Cause | La détection `os.symlink("cible", os.devnull)` tentait de créer le lien **à `/dev/null`** (chemin déjà existant) → `FileExistsError` (une `OSError`) → faux négatif « symlink non supporté ». |
| Preuve | Sur Debian 13 : `os.symlink("cible", os.devnull)` → `FileExistsError: [Errno 17] File exists: 'cible' -> '/dev/null'` ; alors qu'une création correcte (`dst` dans un temporaire) réussit et `os.path.realpath` résout bien le lien. |
| Impact | Les 3 tests de confinement par lien symbolique — **la preuve centrale de S-005** — n'avaient **jamais** été exécutés sur aucune plateforme. Mon rapport de révision 1 annonçait qu'ils seraient exécutés sous Debian 13 : c'était inexact, le skip aurait eu lieu malgré tout. |
| Correction | Détection via un répertoire temporaire (`_symlink_supported()`), `dst` correct, nettoyage garanti. Aucun fichier parasite. |
| Après correction (Debian 13) | `tests.test_path_security` → **OK, 0 ignoré** ; suite complète **302 tests, 0 ignoré**. La protection S-005 est **réellement vérifiée** sur Linux. |
| Correction appliquée | Sur la branche d'audit `audit/agent-b-v1-review`. **Publiée** dans le commit `3029f3f` (fusion) puis `c548e3b` (correction) — vérifié présent sur `origin/audit/agent-b-v1-review` par `git show origin/audit/agent-b-v1-review:tests/test_path_security.py`. |

**Aucune pollution du dépôt** : le lien de sonde est créé dans un temporaire, puis supprimé ; `git status` reste vide après la suite (vérifié sur Debian 13 et sur Windows).

## 7. Risques secondaires

| Risque | État | Preuve |
|--------|------|--------|
| **R2** — `/clear` laissait l'historique persisté (messages effacés réapparaissant au redémarrage) | ✅ **CORRIGÉ** | `clear()` supprime désormais les messages persistés (`delete_messages`) : 2 messages avant → **0 après** → restauration après redémarrage = **0 message**. La CLI distingue « Historique effacé. » de « effacé en mémoire, mais la suppression de l'historique persisté a échoué. » |
| **R3** — variables d'environnement non mappées (`HTTP_PROXY`) non appliquées | ⚠️ **CONFIRMÉ, assumé, testé — documentation manquante** | `HTTP_PROXY` du `.env` → absent de `os.environ` **et** non lu par `Settings`. Choix d'herméneuticité (Agent A l'a documenté et testé : `test_variables_env_non_mappees_non_injectees`). **Action transmise à Agent A** : message **M-006** dans `MESSAGES.md` avec la section « Sources de configuration et variables reconnues » **prête à coller** dans `INSTALL.md` (18 variables mappées listées, ordre de priorité, traitement des variables non mappées, procédure de configuration d'un proxy). La modification de `INSTALL.md` reste la responsabilité d'Agent A. |
| **R4** — chemin de base de données non autorisé | ✅ **CONFORME** | `/tmp/ailleurs/memoire.db` → **REFUSÉ** (`PathSecurityError`) ; la persistance se désactive avec un avertissement explicite sur stderr. |
| **R5** — transactions SQLite imbriquées | ✅ **RÉSOLU** | `isolation_level = None` (autocommit) ; `BEGIN IMMEDIATE` explicite ; **50 écritures consécutives sans échec** ; séquences contiguës et uniques (`1..50`). Rollback sur erreur. |
| **R6** — sortie de l'erreur fournisseur dans le terminal | ⚠️ **À SIGNALER (faible)** | Le terminal affiche le détail technique (`Erreur inattendue avec le fournisseur distant: Remote end closed connection…`). Le chemin **HTTP**, lui, reste générique (`public_provider_error()`). Le terminal est local et mono-utilisateur, mais le corps de réponse du fournisseur (200 premiers caractères) est recopié dans le terminal : un fournisseur qui ré-échoierait une clé la ferait apparaître. Recommandation : limiter ce détail aux logs techniques. |
| **R7** — `Server: BaseHTTP/0.6 Python/3.13.5` | ⚠️ Pré-existant, faible | Non corrigé par Agent A, hors périmètre V1. |

## 8. Scénario conversationnel de bout en bout (Debian 13, fournisseur **simulé local**)

Aucun appel à un fournisseur payant n'a été effectué. Le fournisseur simulé est un serveur HTTP local OpenAI-compatible ; les réponses affichées proviennent de vraies réponses HTTP.

| # | Étape | Résultat |
|---|-------|----------|
| 1 | Démarrage | ✅ Bannière MILES, « Conversation enregistrée sous l'identifiant … », code de sortie 0 |
| 2 | Message utilisateur | ✅ `REPONSE: Bonjour` (réponse HTTP réelle) |
| 3 | Réponse du fournisseur | ✅ Extraite de `choices[0].message.content` — **non simulée dans le code** |
| 4 | Plusieurs échanges + contexte | ✅ Contexte transmis : `['user','assistant','user','assistant','user']` (5 messages) |
| 5 | Sauvegarde | ✅ Messages en base (SQLite) |
| 6 | Fermeture propre | ✅ « Au revoir ! », code 0 |
| 7 | Redémarrage | ✅ Nouvelle session, même base |
| 8 | Restauration du contexte | ✅ « Conversation restaurée » ; contexte transmis : 7 messages |
| 9 | Panne de connexion | ✅ Erreur affichée, **code de sortie 0**, pas de crash, session continued |
| 10 | Changement de fournisseur | ✅ `--provider local` → « fournisseur local » affiché |
| 11 | Nombre d'appels HTTP réels reçus | **5** |

## 9. Couverture des exigences

| # | Exigence | État | Preuve |
|---|----------|------|--------|
| 1-2 | Démarrage terminal, saisie message | ✅ | Debian 13, session 1 |
| 3-4 | Appel réel du fournisseur, réponse affichée | ✅ | 5 requêtes HTTP reçues, réponses non simulées |
| 5-6 | Multi-échanges, contexte maintenu | ✅ | 5 puis 7 messages transmis |
| 7 | Changement de fournisseur | ✅ | `--provider local` |
| 8 | Erreurs utiles sans exposition sensible | ⚠️ | HTTP générique ✓ ; terminal détaillé (R6) |
| 9 | Fermeture propre | ✅ | « Au revoir ! », code 0 |
| 10-14 | Architecture fournisseurs homogène, pas de duplication | ✅ | Interface ABC identique ; `conversation.py` = contexte, `transcript.py` = stockage |
| 15-16 | Sauvegarde, ordre des échanges | ✅ | `sequence` + `UNIQUE` + tri |
| 17 | Restauration après redémarrage | ✅ | **D-B1 corrigé** : identifiant inconnu → vraie conversation créée |
| 18-19 | Reconstruction du contexte, séparation des conversations | ✅ | 7 messages restaurés |
| 20 | Doublons | ✅ | 50 écritures → séquences 1..50 contiguës et uniques |
| 21 | Erreurs d'accès à la base | ✅ | Dégradation gracieuse + `IntegrityError` traité |
| 22 | Comportement après échec réseau | ✅ | Erreur affichée, session continue |
| 23 | Absence de clés API en base / historique | ✅ | `sanitize_text()` avant écriture ; 3 tests dédiés ; **scan de l'arbre et de l'historique** : 125 fichiers suivis, 2 correspondances `sk-…` = exemples pédagogiques (`sk-1234567890abcdef` dans `QUICKSTART.md:136` et `tests/test_memory_persistent.py:84`) ; 42 commits, aucun vrai secret |
| 24 | Secrets suivis par Git | ✅ | `git ls-files` : aucun `.env`/`.db`/`.key` ; `data/*.db` et `__pycache__` ignorés par `.gitignore` |
| 25 | Journaux sans secret | ✅ | `test_aucun_secret_dans_les_logs` ; `sanitize_text('cle sk-FAUSSE')` → `cle [REDACTED]` |
| 26 | Validation des entrées | ✅ | `VALID_ROLES`, corps HTTP borné |
| 27 | Chemins de fichiers autorisés | ✅ | **Récursivement vérifié sous Debian 13** (3 tests symlink exécutés) ; mutation A → 10 échecs |
| 28 | Serveur web et restrictions réseau | ✅ | 127.0.0.1 imposé, refus explicite |
| 29 | Délais et taille des entrées | ✅ | 64 KiB / 413, `timeout=30 s` ; **mutation B testée** (3 échecs) |
| 30 | Exécution de commandes non autorisées | ✅ | 3 actions en registre, politique appliquée |
| 31 | Tests couvrant réellement les risques | ✅ | 3 mutations testées (A, B, C) + 27 tests dédiés d'Agent A |
| 32 | Validation Debian 13 | ✅ | **302 tests, 0 ignoré**, scénario E2E complet (révision 3) |

## 10. Problèmes qui persistent

| ID | Problème | Priorité | Statut |
|----|----------|----------|--------|
| R3 | Les variables d'environnement non mappées lues dans `.env` (ex. `HTTP_PROXY`) ne sont pas appliquées au processus | Moyenne | **Confirmé, assumé et testé** par Agent A. **Recommandation transmise à Agent A via M-006** (section de documentation prête à coller dans `INSTALL.md`). Correction à faire par Agent A, puis à revérifier. |
| R6 | Le terminal affiche le détail technique de l'erreur fournisseur (corps de réponse jusqu'à 200 caractères) | Faible | **Confirmé**. Le chemin HTTP reste générique. **Transmis à Agent A via M-007.** Recommandation : ne conserver ce détail que dans les journaux techniques. |
| R7 | En-tête `Server: BaseHTTP/0.6 Python/3.13.5` | Faible | Pré-existant, hors périmètre. |
| — | Défaut dans mon propre code de test (détection symlink) | ✅ **Corrigé et publié** | Corrigé dans `c548e3b`, publié dans `3029f3f` sur `origin/audit/agent-b-v1-review`. Reste à **fusionner** cette branche pour que la correction parvienne dans `main` et dans la branche V1. |

## 11. Verdict

# VALIDÉ POUR LE PÉRIMÈTRE ANNONCÉ

**Justification par les preuves.**
Les cinq défauts D-B1 à D-B5 sont **résolus et vérifiés par des scénarios indépendants** écrits par Agent B et exécutés sur **Debian 13** — pas seulement par les tests d'Agent A. Les correctifs L-007 à L-010, S-001, S-003, S-005 et S-006 sont préservés. **Trois tests de mutation** démontrent que les tests détectent réellement la suppression des protections (10 échecs pour le confinement des chemins, 3 pour la limite du corps HTTP, et la mutation C prouve que le correctif de détection est ce qui fait exécuter les tests de liens symboliques). La suite complète passe **302/302 avec 0 test ignoré sous Debian 13**, contre 4 ignorés sous Windows. Le scénario conversationnel de bout en bout est validé sur les 11 étapes, avec de **vrais échanges HTTP** vers un fournisseur simulé local explicitement identifié, et une restauration correcte du contexte après redémarrage. Aucun secret n'est exposé dans l'arbre ni dans l'historique (125 fichiers suivis, 42 commits).

**Réserves mineures (non bloquantes) :**
1. **R3** — les variables non mappées du `.env` (ex. `HTTP_PROXY`) ne sont pas appliquées : choix d'herméneuticité assumé, **documentation à faire par Agent A** (M-006 fourni).
2. **R6** — le terminal affiche le détail technique de l'erreur fournisseur (le chemin HTTP reste générique) : transmis à Agent A (M-007).
3. **R7** — en-tête `Server:` pré-existant, hors périmètre.
4. **Action requise** — la branche `audit/agent-b-v1-review` (qui porte le correctif de détection des liens symboliques) doit être **fusionnée** pour que ce correctif parvienne dans `main` et dans la branche V1. Sans cela, les 3 tests S-005 restent ignorés sur toutes les plateformes.

**Hors périmètre non évalué** (conformément à la consigne) : voix, actions autonomes, fournisseur local llama.cpp, **test d'inférence réel (non autorisé, coût API)**, performance.

## 12. Actions demandées à l'utilisateur

| # | Action | Responsable | État |
|---|--------|--------------|------|
| 0 | ~~Fusionner `audit/agent-b-v1-review` dans la branche V1~~ | Agent A | ✅ **Fait** — correctif rebasé en `8d30809`, intégré dans `9a53652` |
| 1 | Publier la branche `audit/agent-b-v1-review` (rapport) | Agent B (push automatique) | ✅ **Fait** — `9d8f9a4` publié, synchronisation confirmée |
| 2 | Fusionner `9a53652` (V1 complète : D-B1→D-B5, R3, R6, D-C1, D-C2) dans `main` | Utilisateur | ⏳ Requiert autorisation explicite |
| 3 | Documenter R3 dans `INSTALL.md` | Agent A | ✅ **Fait** dans `95dac41`, vérifié |
| 4 | Restreindre le détail d'erreur fournisseur au terminal (R6) | Agent A | ✅ **Fait** dans `95dac41`, vérifié |
| 5 | Nuance de formulation R3 (D-C2) | Agent A | ✅ **Fait** dans `9a53652`, vérifié |
| 6 | Test d'inférence réel (Groq) | Non autorisé — coût API | ⏳ Décision à votre main |
| 7 | Fusionner la branche V1 (`9a53652`) dans `main` **après** validation Debian 13 par l'agent | Utilisateur | ⏳ Recommandé avant intégration |

## 13. Références de branche et de commit

| Référence | Hash | Rôle |
|-----------|------|------|
| `origin/audit/agent-b-v1-review` | `3029f3f` (révision 3 : ce rapport + M-006/M-007) | Branche d'audit d'Agent B — **publiée et synchronisée** |
| `origin/feature/miles-v1-conversation-persistence` | `7dacdfe` | Branche de développement V1 d'Agent A — **inchangée** |
| `origin/fix/agent-b-s002-s004-s005-s006` | `e0886a7` | Correctifs S-002→S-006 d'Agent B |
| `origin/fix/agent-b-s001-s003-memory-config` | `f53cffc` | S-001/S-003 + configuration mémoire |
| `origin/review/agent-b-phase4-review` | `928410c` | Revue Phase 4 |
| `origin/review/phase4-security-fixes` | `4b6f515` | L-007→L-010 |
| `origin/work/agent-a-phase4-audit` | `632f27b` | Audit complémentaire d'Agent A (15 tests) |
| `origin/main` | `b5e1007` | **Ne contient pas** la V1 — inchangé par Agent B |

---

*Audit de finalisation réalisé par Agent B le 2026-10-20. Commit V1 audité : `7dacdfefe0717602d14144e98bc9bd326d227464`. Branche d'audit publiée : `audit/agent-b-v1-review`. Environnements : Windows (Python 3.14.7) et Debian GNU/Linux 13 trixie (Python 3.13.5, accès SSH autorisé). Fournisseur simulé local explicitement identifié ; aucun appel à un fournisseur payant, aucun téléchargement de modèle. Aucun push vers `main`, aucune fusion, aucune réécriture d'historique partagé, aucune suppression de branche.*
