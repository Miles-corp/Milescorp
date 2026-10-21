# docs/reports/PHASE_5_INTEGRATION_PREP_AND_CAPABILITIES_AGENT_A.md — Préparation d'intégration V1, inventaire des compétences et préparation de l'inférence (Agent A)

## 1. Synchronisation préalable

| Contrôle | Résultat |
|----------|----------|
| Dépôt | `Miles-corp/Milescorp` (le dépôt attendu) |
| `git fetch origin --prune` | `main` mis à jour (`b5e1007..b9b7e7d`) ; `audit/agent-b-v1-review` mis à jour (`9d8f9a4..77fa39b`) |
| Branche de travail | `feature/miles-v1-conversation-persistence` = `9a53652` = sa distante — **aucune divergence** |
| Modifications locales | Uniquement l'artefact parasite `tatus --short--branch` (préservé, non committé) |

### 1.1 Références vérifiées sur GitHub (et écart avec les références annoncées)

| Référence | Annoncée | **Réelle (vérifiée)** | Statut |
|-----------|----------|------------------------|--------|
| `main` | `b5e1007` | **`b9b7e7d`** — « Merge pull request #1 from Miles-corp/review/agent-b-phase4-review » | ⚠️ **A divergé** |
| Branche V1 | `9a53652` | `9a53652` | ✅ Conforme |
| Branche d'audit B | `77fa39b` | `77fa39b` | ✅ Conforme |

**`main` a avancé depuis la dernière session** : la PR #1 (rapport d'audit Phase 4 d'Agent B) y a été fusionnée. L'intégration doit donc se calculer sur `b9b7e7d`, pas sur `b5e1007`.

## 2. Partie A — Préparer l'intégration

### 2.1 Comparaison `main` ↔ branche V1

| Ensemble | Commits |
|----------|---------|
| `main` uniquement | `b9b7e7d` (merge PR #1), `928410c` (rapport d'audit Phase 4, Agent B) |
| Branche V1 uniquement | 16 commits : `e0886a7` → `9a53652` |
| `merge-base` | `4b6f515` (les correctifs L-007 à L-010) |

**Diff `main` → branche V1** : 40 fichiers, **+7148 / −291**.

### 2.2 Commits à intégrer (16)

| Commit | Nature |
|--------|--------|
| `e0886a7` | Production (Agent B) — S-006 fermeture des files multiprocessing |
| `91ed8c3` | Production (Agent B) — S-005 confinement des chemins |
| `552adfb` | Production (Agent B) — S-004 limite du corps HTTP |
| `7147dc0` | Production (Agent B) — S-002 serveur web strictement local |
| `f53cffc` | Audit (Agent B) — rapport S-001/S-003 + config mémoire |
| `97bbd90`, `bdee0f6`, `8b0e9dc` | Tests (Agent B) |
| `064f907` | Production (Agent B) — S-001/S-003 + configuration mémoire |
| `be9f317` | Production (Agent A) — V1 persistance de conversation + branchement du fournisseur distant |
| `63236a4` | Audit (Agent A) — rapports d'audit Phase 4 |
| `7dacdfe` | Production (Agent A) — corrections D-B1 à D-B5 |
| `95dac41` | Doc + production (Agent A) — R3 documentation, R6 erreurs fournisseur |
| `8d30809` | Audit (Agent B) — contre-audit Debian 13 + correctif D-C1 (cherry-pick) |
| `9a53652` | Doc + tests (Agent A) — D-C2 + tests de détection symlink |

### 2.3 Fichiers concernés

**Production (14 fichiers)** : `miles.py`, `app/config/settings.py`, `app/core/conversation.py`, `app/interface/cli.py`, `app/interface/web.py`, `app/memory/{__init__,history,persistent,transcript}.py`, `app/ai_providers/{base,local,public_errors,remote}.py`, `app/security/{__init__,paths,validator}.py`, `app/tools/{__init__,audit,engine,policy,registry,status_tool}.py`, `app/utilities/{gpu_info,redaction}.py`, `app/voice/base.py`, `app/connectors/computer/actions.py`

**Tests (13 fichiers)** : `tests/` — 338 tests au total

**Documentation (14 fichiers)** : `docs/installation/{INSTALL,QUICKSTART}.md`, `docs/reports/*` (8 rapports), `docs/coordination/{STATUS,TASKS}.md`

**Configuration (2 fichiers)** : `.env.example`, `config/config.json.example`

### 2.4 Conflits : **aucun**

Test de fusion exécuté sur une branche temporaire (`tmp/merge-test`, supprimée depuis) :
```
git merge --no-commit --no-ff origin/main
→ Automatic merge went well; stopped before committing as requested
```

**Point de vigilance analysé** : `docs/reports/PHASE_4_REVIEW_AGENT_B.md` diffère entre `main` et V1, mais il n'a été modifié que **côté `main`** (révision 2 du rapport, `+174/−59`) ; côté V1 il est inchangé depuis la base. Le merge retient donc la **version la plus récente** — aucune information n'est perdue, aucun conflit à arbitrer.

### 2.5 D-C1 et D-C2 : présence vérifiée dans la branche V1

| Correction | Vérification | Résultat |
|------------|-------------|----------|
| **D-C1** | `tests/test_path_security.py:30` : `def _symlink_supported()` ; plus de `os.symlink("cible", os.devnull)` | ✅ Présente |
| **D-C2** | `docs/installation/INSTALL.md:118` : « Variables de chemin de fichier (lues uniquement de l'environnement) » | ✅ Présente |

### 2.6 Rapport d'audit final : disponible, production et audit distingués

| Document | Type | Auteur |
|----------|------|--------|
| `docs/reports/MILES_V1_VERIFICATION_AGENT_B.md` | **Audit** — contre-audit Debian 13 (révision 2) | Agent B |
| `docs/reports/MILES_V1_DEVELOPMENT.md` | **Production** — rapport de développement V1 | Agent A |
| `docs/reports/PHASE_4_DEFS_AGENT_B_FIXES.md` | **Production** — corrections D-B1 à D-B5 | Agent A |
| `docs/reports/PHASE_4_R3_R6_AGENT_A.md` | **Production** — R3/R6 | Agent A |
| `docs/reports/PHASE_4_DC1_DC2_AGENT_A.md` | **Production** — D-C1/D-C2 | Agent A |
| `docs/reports/PHASE_4_FINAL_REVIEW_AGENT_A.md` | **Audit** — revue finale | Agent A |
| `docs/reports/PHASE_4_FINDINGS_TRIAGE_AGENT_A.md` | **Audit** — triage | Agent A |
| `docs/reports/PHASE_4_REVIEW_FIXES_AGENT_A.md` | **Audit** — revue des correctifs | Agent A |
| `docs/reports/PHASE_4_FIXES_S001_S003_MEMORY_CONFIG_AGENT_B.md` | **Audit** — revue initiale S-001/S-003 | Agent B |
| `docs/reports/PHASE_4_TOOL_ENGINE.md` | **Production** — architecture du moteur d'outils | Agent A |

### 2.7 Tests et état du dépôt

```
$ python -m unittest discover -s tests
Ran 338 tests in 36.753s
OK (skipped=4)
```

338 tests, 0 échec, 0 erreur, 4 ignorés (3 symlink — privilège Windows ; 1 descripteurs — spécifique Linux).

### 2.8 Procédure d'intégration définie (non exécutée)

1. `git checkout main && git pull --ff-only` → `b9b7e7d`
2. `git merge --no-ff feature/miles-v1-conversation-persistence` → fusion sans conflit (vérifié)
3. `python3 -m unittest discover -s tests -v` → attendu 338 OK, 0 ignoré sur Debian 13
4. `git push origin main`
5. Consigner dans `docs/coordination/` : TASK-DEV-009, TASK-DEV-010, TASK-DEV-011, TASK-DEV-012 → `DONE`

**Je n'ai pas exécuté la fusion** : `main` n'est pas modifié, conformément aux limites.

## 3. Partie B — Inventaire des compétences de MILES

> Fondé sur le **code réel** et les **tests réels**. Une capacité n'est pas « implémentée » parce qu'elle figure dans la vision du projet.

### 3.1 Synthèse

| Compétence | Statut | Niveau |
|------------|--------|--------|
| Conversation CLI | ✅ Implémentée | Complet |
| Persistance SQLite (transcriptions) | ✅ Implémentée | Complet |
| Fournisseurs IA (distant + local) | ✅ Implémentée | Complet |
| Gestion des erreurs fournisseur | ✅ Implémentée | Complet |
| Configuration et secrets | ✅ Implémentée | Complet |
| Mémoire de souvenirs | ✅ Implémentée | Complet |
| Outils (moteur) | ⚠️ Partiellement implémentée | Moteur testé, **non branché** |
| Actions locales | ⚠️ Partiellement implémentée | Code présent, **non appelées** |
| Vérification et reprise sur erreur | ✅ Implémentée | Complet |
| Exécution locale | ⚠️ Partiellement implémentée | Fournisseur local prêt, **runtime absent** |
| Planification de missions | ❌ Absente | `app/orchestration/` vide |
| Voix | ⚠️ Partiellement implémentée | Stubs, **aucune synthèse/reconnaissance** |
| Interface web | ✅ Implémentée | Complet (127.0.0.1 strict) |

### 3.2 Détail par compétence

#### Conversation CLI — ✅ Implémentée
- **Fichiers** : `miles.py`, `app/interface/cli.py`, `app/core/conversation.py`
- **Tests** : `test_conversation.py` (7), `test_conversation_persistence.py` (48), `test_cli_reliability.py` (5), `test_miles_entrypoint.py` (5)
- **Limites** : pas de streaming ; `/clear` purge la session et la persistance ; pas de multi-session simultanée
- **Prochaine tâche** : brancher le moteur d'outils sur la CLI (§3.6)

#### Persistance SQLite (transcriptions) — ✅ Implémentée
- **Fichiers** : `app/memory/transcript.py` (418 l.), `app/core/conversation.py`
- **Tests** : `test_conversation_persistence.py` (48), `test_defects_agent_b.py` (26)
- **Limites** : pas de recherche ni de résumé ; suppression d'une conversation = perte définitive ; un seul fichier, pas de chiffrement
- **Prochaine tâche** : recherche lexicale simple dans les transcriptions

#### Fournisseurs IA et gestion des erreurs — ✅ Implémentée
- **Fichiers** : `app/ai_providers/{base,remote,local,public_errors}.py`
- **Tests** : `test_providers.py` (4), `test_provider_selection.py` (9), `test_provider_errors.py` (15), `test_milestone_005.py` (11)
- **Limites** : pas de `max_tokens` (longueur de réponse non contrôlée) ; pas de réessai ; pas de gestion de `rate limit` distinguishable dans la requête
- **Prochaine tâche** : paramètre `max_tokens` configurable (§ Partie C)

#### Configuration et secrets — ✅ Implémentée
- **Fichiers** : `app/config/settings.py`, `app/utilities/redaction.py`, `.env.example`, `config/config.json.example`
- **Tests** : `test_settings.py` (9), `test_env_loading.py` (5), `test_settings_memory_config.py` (15), `test_docs_configuration.py` (15)
- **Limites** : 19 variables reconnues seulement ; pas de validation de format de l'URL ; pas de rotation de clé
- **Prochaine tâche** : validation de l'URL de base et du nom de modèle au démarrage

#### Outils (moteur) — ⚠️ Partiellement implémentée
- **Fichiers** : `app/tools/{registry,engine,policy,audit,status_tool}.py` (671 l.)
- **Tests** : `test_tool_engine.py` (26), `test_tool_policy.py` (11), `test_tool_audit.py` (4), `test_tool_registry.py` (6), `test_status_tool.py` (4)
- **Limites** : **le registre n'est alimenté nulle part** (`ToolRegistry().list_tools()` → `[]`) ; `status_read` n'est enregistré dans aucun registre ; **aucune route `/tool`** dans l'interface web ; le moteur n'est appelé ni par le CLI ni par le web
- **Prochaine tâche** : enregistrer `status_read` et exposer une commande `/tool` — le moteur est prêt et testé, seule l'intégration manque

#### Actions locales — ⚠️ Partiellement implémentée
- **Fichiers** : `app/security/validator.py`, `app/connectors/computer/actions.py`
- **Tests** : `test_actions.py` (7)
- **Limites** : 3 actions (`datetime`, `list_files`, `workdir`) ; `CLI.propose_action()` **n'est appelé nulle part** ; `list_files` a été durci (S-005) mais n'est pas exposé à l'utilisateur
- **Prochaine tâche** : exposer les actions via le moteur d'outils et une confirmation explicite

#### Planification de missions — ❌ Absente
- **Fichiers** : `app/orchestration/` — **vide** (`.gitkeep` seul)
- **Tests** : aucun
- **Limites** : MILES ne sait pas décomposer une demande en étapes ; c'est un besoin central pour le « boîtier »
- **Prochaine tâche** : `app/orchestration/planner.py` — décomposition d'un objectif en étapes, avec points de contrôle

#### Mémoire (souvenirs) — ✅ Implémentée
- **Fichiers** : `app/memory/persistent.py` (375 l.), `app/memory/history.py`
- **Tests** : `test_memory_persistent.py` (18)
- **Limites** : souvenirs explicites uniquement (pas de RAG) ; pas de similarité ni de résumé ; `max_memories_in_context = 5`
- **Prochaine tâche** : lien entre souvenirs et transcriptions (aujourd'hui deux bases distinctes)

#### Vérification et reprise sur erreur — ✅ Implémentée
- **Fichiers** : `app/ai_providers/public_errors.py`, `app/interface/{cli,web}.py`, `app/memory/transcript.py`
- **Tests** : `test_provider_errors.py` (15), `test_defects_agent_b.py` (26), `test_web_security.py` (33), `test_tool_resources.py` (8)
- **Limites** : pas de reprise automatique après échec réseau (choix : éviter de dupliquer un appel payant) ; pas de reprise après crash du processus
- **Prochaine tâche** : reprise explicite sur timeout, avec confirmation utilisateur

#### Compétences réutilisables — ✅ Implémentée (transverses)
- **Fichiers** : `app/utilities/redaction.py` (source unique de détection des secrets), `app/ai_providers/public_errors.py` (source unique de classification), `app/security/paths.py` (confinement des chemins), `app/memory/transcript.py` (schéma versionné)
- **Tests** : `test_symlink_detection.py` (6), `test_docs_configuration.py` (15)
- **Limites** : la.redaction ne couvre pas tous les formats (JWT sans préfixe) ; pas de glossaire central des permissions
- **Prochaine tâche** : registre central des permissions (aujourd'hui les permissions sont libres et non documentées globalement)

#### Exécution locale — ⚠️ Partiellement implémentée
- **Fichiers** : `app/ai_providers/local.py`, `app/utilities/gpu_info.py`
- **Tests** : `test_milestone_005.py` (11), `test_provider_selection.py` (9)
- **Limites** : **aucun runtime local installé** ; `LocalProvider` suppose un serveur OpenAI-compatible (Ollama, llama.cpp) ; le diagnostic GPU via `nvidia-smi` fonctionne (RTX 3050, 4 Go) mais aucun modèle n'est servi
- **Prochaine tâche** : TASK-DEV-007 — proposition moteur + modèle pour 4 Go de VRAM (déjà rédigée dans `MILES_V1_DEVELOPMENT.md` §9 : llama.cpp + Llama-3.2-1B-Instruct Q4_K_M)

#### Voix et interface — ⚠️ Partiellement implémentée (voix) / ✅ (interface)
- **Fichiers** : `app/voice/base.py`, `app/interface/web.py` (627 l.)
- **Tests** : `test_voice.py` (6, 4 ignorés), `test_web.py` (14), `test_web_security.py` (33)
- **Limites** : `speak()` et `listen()` lèvent **toujours** `VoiceUnavailableError` — aucune synthèse ni reconnaissance réelle ; le mode vocal n'est pas câblé au CLI ; **interface web** : complète (conversation, statut, mémoire), mais pas de route `/tool` et pas de vue `/conversations` côté web
- **Prochaine tâche** : implémenter la synthèse vocale (`pyttsx3`) sur Debian 13, après la livraison du moteur d'outils

## 4. Partie C — Préparation de l'inférence réelle (aucun appel effectué)

### 4.1 Fournisseur et modèle actuellement configurés

| Élément | Valeur lue dans `.env` (local, non versionné) |
|---|---|
| Fournisseur | `MILES_PROVIDER=remote` → `RemoteProvider` |
| Endpoint de base | `MILES_REMOTE_BASE_URL=https://api.groq.com/openai/v1` |
| Modèle | `MILES_REMOTE_MODEL=llama-3.3-70b-versatile` |
| Timeout | `MILES_REMOTE_TIMEOUT=30` |
| Clé API | `MILES_REMOTE_API_KEY` — **présente, valeur jamais affichée ni lue** |
| Historique | `MILES_HISTORY_LIMIT=10` |

**URL finale réellement construite par le code** (normalisation anti-doublon vérifiée) :
```
https://api.groq.com/openai/v1/chat/completions
```

### 4.2 Comment la clé est chargée (sans en révéler la valeur)

1. `Settings._load_env_file()` lit `.env` (chemin : `MILES_ENV_FILE`) **dans un dictionnaire local** — l'environnement du processus n'est **pas** modifié.
2. La boucle de lecture des variables mappe `MILES_REMOTE_API_KEY` → clé de configuration `remote_api_key`, **prioritairement** depuis `os.environ`, sinon depuis le dictionnaire `.env`.
3. `miles.py` construit `RemoteProvider(api_key=settings.get("remote_api_key"))`.
4. `RemoteProvider.chat()` l'envoie **uniquement** dans l'en-tête `Authorization: Bearer <clé>`.
5. La clé n'est **jamais** journalisée : `public_provider_error()` la remplace par un message générique, `technical_detail()` l'expurge, et l'historique de conversation passe par `sanitize_text()`.

### 4.3 Candidat `openai/gpt-oss-20b` : compatibilité

| Point | Verdict |
|---|---|
| Format d'API | ✅ Groq sert `openai/gpt-oss-20b` via l'API OpenAI-compatible `/openai/v1/chat/completions` — exactement le format du code |
| Identifiant de modèle | ✅ le code transmet `model` tel quel dans le corps de la requête |
| **Risque identifié** | ⚠️ le code envoie **inconditionnellement** `"temperature": 0.7`. Les modèles de raisonnement (gpt-oss) **rejettent souvent `temperature`** → HTTP 400 possible. **À tester avant de conclure.** |
| Coût | À vérifier : gpt-oss est un modèle open-weight, généralement gratuit ou très bon marché sur Groq — **à confirmer dans la console** |

**Recommandation** : commencer le test avec le modèle **déjà configuré** (`llama-3.3-70b-versatile`) pour valider la chaîne complète, puis tester `openai/gpt-oss-20b` séparément. Si `gpt-oss` refuse `temperature`, il faudra rendre ce paramètre configurable (ou omissible) dans `RemoteProvider`.

### 4.4 Paramètres de contrôle du contexte et de la longueur de réponse

| Paramètre | Où | État |
|-----------|-----|-------|
| Contexte (historique) | `MILES_HISTORY_LIMIT` (défaut 10) = nombre de **messages** transmis | ✅ Contrôlable |
| Prompt système | `Conversation(system_prompt=...)` | ⚠️ Non exposé en configuration |
| Température | `remote.py`, `temperature: 0.7` en dur | ⚠️ Non configurable |
| **Longueur de réponse** | — | ❌ **Absent** : aucun `max_tokens` n'est envoyé. La longueur dépend du fournisseur et du modèle |

**Action requise** avant de contrôler la longueur : ajouter `max_tokens` (et `temperature`) comme options de configuration, désactivables pour les modèles qui les refusent.

### 4.5 Coût estimé d'un échange de test (hypothèse de tokens explicite)

Le corps envoyé pour un échange = 1 message utilisateur + 1 réponse.

| Élément | Hypothèse | Justification |
|---------|-----------|---------------|
| Tokens d'entrée | ≈ 50 | 1 message utilisateur court + prompt système éventuel |
| Tokens de sortie | ≈ 200 | réponse conversationnelle typique |
| Total par échange | ≈ 250 | |

**Formule** : `coût = (tokens_entrée × prix_entrée + tokens_sortie × prix_sortie) / 1 000 000`

Les **prix unitaires par million de tokens doivent être lus dans la console Groq** (https://console.groq.com → Pricing / Usage) — ils varient selon le modèle et peuvent changer. Je ne les invente pas ici.

**Ordre de grandeur** : avec les tarifs publics couramment observés pour `llama-3.3-70b-versatile` (de l'ordre de ~0,60 $/M tokens en entrée et ~0,80 $/M tokens en sortie), un échange de 250 tokens coûterait **≈ 0,0002 $** (de l'ordre de 0,02 centime). **Valeur à confirmer dans la console** avant exécution.

Pour `openai/gpt-oss-20b` (open-weight), le coût est généralement nul ou très faible — **à confirmer**.

### 4.6 Ce qu'il faut vérifier dans la console du compte avant l'appel

| Vérification | Pourquoi |
|--------------|----------|
| Le modèle est **actif** pour le compte (`llama-3.3-70b-versatile` ou `openai/gpt-oss-20b`) | Un modèle non activé renvoie 400 |
| Le **solde / quota** et le **tier gratuit** restant | Éviter un blocage en cours d'appel |
| Le **tarif par million de tokens** du modèle retenu | Dimensionner le coût |
| Les **limites de débit** (requests/min, tokens/min) | Éviter un 429 sur le premier appel |
| La **clé API est active** et non expirée | Éviter un 401 |
| Le **mode de facturation** (payant vs gratuit) | Conditionne la décision d'exécuter |

### 4.7 Procédure d'exécution proposée (une fois autorisé)

```bash
# 1. Lancer MILES avec la configuration existante
python miles.py

# 2. Poser UNE seule question courte, par exemple :
#    "Réponds en une phrase : quel est ton nom ?"

# 3. Vérifier : réponse affichée, "Conversation enregistrée sous l'identifiant…",
#    puis Ctrl+C ou /quit (code de sortie 0)

# 4. Contrôler dans la console Groq : consommation de tokens et absence d'erreur
```

**Aucun appel n'a été effectué.** Le `.env` local n'a été lu que pour en extraire les **noms** de variables et les valeurs **non secrètes**.

## 5. Fichiers modifiés par cette session

| Fichier | Action |
|---------|--------|
| `docs/reports/PHASE_5_INTEGRATION_PREP_AND_CAPABILITIES_AGENT_A.md` | **Créé** — ce rapport |

Aucun fichier de production ni de test n'a été modifié : cette mission était d'analyse et de préparation.

## 6. Limites de validation

| Limite | Statut |
|--------|--------|
| VM Debian 13 inaccessible (`ssh -p 2222` → connection refused) | Les 3 tests symlink n'ont pas pu être exécutés sous Linux par Agent A. Mesurés par Agent B sur sa branche (302 tests, 0 ignoré). |
| Tests Windows | 338 OK, 4 ignorés (3 symlink, 1 descripteurs) |
| Fusion vers `main` | **Non exécutée** — préparation uniquement, conformément aux limites |
| Appel API réel | **Aucun** — procédure préparée, coût à confirmer dans la console |

## 7. Prochaines actions demandées

1. **Propriétaire** : décider la fusion de `feature/miles-v1-conversation-persistence` → `main` (procédure en §2.8, aucun conflit).
2. **Propriétaire** : confirmer le modèle et le coût dans la console Groq, puis autoriser l'appel de test.
3. **Agent B** : contre-audit du commit `9a53652` (révision 5 déjà annoncée comme `77fa39b`).
4. **Tâche suivante recommandée** : brancher le moteur d'outils sur la CLI et le web (seule l'intégration manque, le moteur est testé), puis `TASK-DEV-007` (fournisseur local).

---

*Aucun appel API réel, aucun téléchargement de modèle, aucune installation.
`main` n'a pas été modifié. L'artefact local `tatus --short--branch` est préservé.*
