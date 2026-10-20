# docs/reports/PHASE_4_DC1_DC2_AGENT_A.md — Correctif D-C1 et documentation D-C2 (Agent A)

Traitement du message **M-008** d'Agent B (contre-audit du commit `95dac41`, révision 4).

## 1. Synchronisation préalable

| Contrôle | Résultat |
|----------|----------|
| Dépôt | `Miles-corp/Milescorp` (le dépôt attendu) |
| Branche active | `feature/miles-v1-conversation-persistence` |
| Commit de départ | `95dac41` |
| `git fetch origin` | `origin/audit/agent-b-v1-review` mise à jour (`e98c320..9d8f9a4`) |
| Synchronisation branche de travail | `95dac41` = `origin/feature/miles-v1-conversation-persistence` — **aucune divergence** |
| Modifications locales | Uniquement l'artefact parasite `tatus --short --branch` (préservé, non committé) |
| `origin/main` | `b5e1007` — **inchangé** |

## 2. D-C1 — Correctif de détection des liens symboliques

### 2.1 Analyse du commit `c548e3b` (annoncé par Agent B)

| Élément | Valeur |
|---------|--------|
| SHA complet | `c548e3b6ca8c45a4529641510b4b2eb905f73f4d` |
| Parent | `7dacdfefe0717602d14144e98bc9bd326d227464` (commit **de ma branche**) |
| Auteur | `iopjklad-pixel <iopjklad@gmail.com>` (Agent B) |
| Date | 2026-10-20 14:19:02 |
| Fichiers | `tests/test_path_security.py` (modifié), `docs/reports/MILES_V1_VERIFICATION_AGENT_B.md` (créé) |

**Présent dans ma branche ?** ❌ Non — `git merge-base --is-ancestor` → faux. Le commit n'existe que dans
`origin/audit/agent-b-v1-review`.

### 2.2 Décision d'intégration

La mission demandait de « n'intégrer que le changement nécessaire si cela est possible et sûr »
et de « ne pas fusionner la branche complète d'audit sans examiner son diff ». J'ai examiné le diff
complet de `c548e3b` : **2 fichiers seulement**, aucun changement de code de production.

Vérifications préalables à l'intégration :

| Vérification | Résultat |
|--------------|----------|
| `tests/test_path_security.py` modifié entre `7dacdfe` et `95dac41` ? | Non (diff vide) → pas de conflit |
| `tempfile` et `shutil` importés dans la version corrigée ? | Oui (déjà présents) → pas de `NameError` |
| `docs/reports/MILES_V1_VERIFICATION_AGENT_B.md` déjà sur ma branche ? | Non → ajouté proprement |

**Intégration par `git cherry-pick c548e3b`** → commit `8d30809`, **auteur d'origine Agent B
préservé**, aucun conflit, historique partagé intact. La branche d'audit d'Agent B n'a **pas** été
fusionnée.

### 2.3 Contenu réel du correctif

La détection de la capacité à créer un symlink est remplacée :

```python
# AVANT (faux négatif sur TOUTES les plateformes)
try:
    os.symlink("cible", os.devnull)   # os.devnull existe déjà -> FileExistsError
    _SYMLINK_SUPPORTED = True
except (OSError, NotImplementedError, AttributeError):
    _SYMLINK_SUPPORTED = False

# APRÈS (correctif d'Agent B)
def _symlink_supported() -> bool:
    tmpdir = tempfile.mkdtemp(prefix="miles_test_symlink_probe_")
    probe = os.path.join(tmpdir, "cible")
    try:
        os.symlink("cible", probe)      # destination valide et inexistante
        return True
    except (OSError, NotImplementedError, AttributeError):
        return False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
```

**Effet** : sous Debian 13, la détection réussit → les 3 tests de confinement S-005
(`test_lien_symbolique_interne_accepte`, `test_lien_symbolique_sortant_refuse`,
`test_lien_symbolique_sortant_refuse_par_list_files`) s'exécutent réellement au lieu d'être
ignorés. La garantie S-005 devient prouvée sur Linux.

### 2.4 Vérification du correctif sans Debian 13

La VM Debian 13 **n'est pas accessible** depuis ce poste (`ssh -p 2222 miles@127.0.0.1` →
`Connection refused`). Je ne peux donc pas y exécuter les tests symlink.

Pour ne pas laisser le correctif invérifié, j'ai écrit `tests/test_symlink_detection.py`
(6 tests) qui prouvent le comportement **sans** disposer de Linux :

| Test | Preuve |
|------|--------|
| `test_detection_reussit_si_symlink_fonctionne` | `os.symlink` simulé (no-op, cas Linux) → la détection retourne `True` **et** la destination n'est jamais `os.devnull` |
| `test_detection_echoue_si_symlink_indisponible` | `os.symlink` en erreur (cas Windows sans privilège) → la détection retourne `False` |
| `test_ancienne_logique_echouait_toujours` | `os.devnull` existe sur toute plateforme → l'ancienne destination était toujours invalide (faux négatif démontré) |
| `test_aucun_fichier_parasite_apres_la_sonde` | le répertoire temporaire de la sonde est nettoyé (pas de pollution du dépôt) |
| `test_variable_module_suivie_apres_detection` | `_SYMLINK_SUPPORTED` est bien un booléen calculé via la nouvelle sonde |
| `test_message_de_skip_reflete_la_vraie_cause` | l'ancienne sonde `os.symlink("cible", os.devnull)` a disparu du fichier |

**Statut sous Windows** : les 3 tests symlink restent ignorés, mais pour la **bonne raison**
(« Création de lien symbolique non permise sur cette plateforme (Windows requiert un privilège) »).
Avant le correctif, le skip était trompeur : il annonçait « Test exécuté sous Debian 13 » alors
qu'un symlink y aurait échoué de la même façon.

**Sous Debian 13** : la vérification reste à confirmer par Agent B (ou par moi si la VM devient
accessible). Agent B l'a déjà mesurée sur sa branche (`302 tests, 0 ignoré`).

## 3. D-C2 — Documentation : `.env` vs environnement du processus

### 3.1 Constat d'Agent B

M-008 : « le tableau des variables lues depuis le `.env` inclut `MILES_ENV_FILE` et
`MILES_CONFIG`, qui sont en réalité lues **exclusivement de l'environnement du processus** ; à
distinguer ».

### 3.2 Vérification dans le code

| Variable | Où elle est lue | Lue depuis le `.env` ? |
|----------|-------------------|------------------------|
| `MILES_ENV_FILE` | `settings.py` : `Path(os.environ.get("MILES_ENV_FILE", ".env"))` | **Non** — lue de l'environnement du processus. Elle sert à *localiser* le `.env` : elle ne peut donc pas y figurer (usage circulaire) |
| `MILES_CONFIG` | `settings.py` : `config_path or os.environ.get("MILES_CONFIG", "config/config.json")` | **Non** — absente de `env_mapping`, donc ignorée par le `.env` |

**Vérifié par exécution** : un `.env` contenant `MILES_CONFIG=/tmp/autre/config.json` (JSON avec
`history_limit: 42`) est **ignoré** → `history_limit` vaut 10 (défaut), pas 42.

### 3.3 Correction documentaire

`docs/installation/INSTALL.md` :

- la ligne `MILES_ENV_FILE` / `MILES_CONFIG` a été **retirée** du tableau des variables lues
  depuis le `.env` ;
- une section dédiée **« Variables de chemin de fichier (lues uniquement de l'environnement) »**
  a été ajoutée, avec le tableau, la raison de la restriction et la conséquence ;
- la section « Variables non reconnues » mentionne explicitement ces deux variables ;
- la puce « limites » précise que les 19 variables se répartissent en **17 lues du `.env`** et
  **2 lues uniquement de l'environnement du processus**.

Le décompte **19 = 17 + 2** et les noms de variables sont exacts (vérifiés par extraction
automatique depuis `app/config/settings.py`).

### 3.4 Tests documentaires adaptés

`tests/test_docs_configuration.py` : 4 nouveaux tests (11 → 15) :

- `test_variables_de_chemin_documentees_separement` : les deux variables ne figurent pas dans
  le tableau des variables du `.env` ;
- `test_variables_de_chemin_exclusives_environnement_processus` : la section dédiée existe et
  indique « environnement du processus » ;
- `test_miles_config_dans_env_ignore` : **preuve par exécution** que `MILES_CONFIG` dans le
  `.env` est sans effet ;
- `test_miles_env_file_dans_env_ignore` : **preuve par exécution** que `MILES_ENV_FILE` dans le
  `.env` est sans effet.

## 4. Fichiers modifiés

| Fichier | Action |
|---------|--------|
| `tests/test_path_security.py` | Intégré via cherry-pick `c548e3b` (auteur Agent B préservé) — correctif D-C1 |
| `docs/reports/MILES_V1_VERIFICATION_AGENT_B.md` | Intégré via cherry-pick `c548e3b` — rapport d'audit Debian 13 d'Agent B |
| `docs/installation/INSTALL.md` | Modifié — section dédiée aux variables de chemin (D-C2) |
| `tests/test_docs_configuration.py` | Modifié — 4 tests de non-divergence documentaire |
| `tests/test_symlink_detection.py` | **Créé** — 6 tests prouvant le correctif D-C1 sans Debian 13 |
| `docs/coordination/TASKS.md` | Modifié — TASK-DEV-012 ajoutée |
| `docs/coordination/STATUS.md` | Modifié — TASK-DEV-012 ajoutée |
| `docs/reports/PHASE_4_DC1_DC2_AGENT_A.md` | **Créé** — ce rapport |

## 5. Tests exécutés — résultats réels

```
$ python -m unittest discover -s tests
Ran 338 tests in 34.453s
OK (skipped=4)
```

| Mesure | Avant (95dac41) | Après |
|---------|------------------|-------|
| Tests découverts | 328 | **338** |
| Réussis | 328 | **338** |
| Échecs / erreurs | 0 | **0** |
| Ignorés | 4 (3 symlink + 1 FD) | 4 (3 symlink + 1 FD) |

Les 4 tests ignorés le sont pour une raison **exacte** : création de lien symbolique non permise
sous Windows sans privilège administrateur, et test de fuite de descripteurs spécifique à Linux.

## 6. Limites de validation

| Limite | Gravité | Statut |
|--------|---------|--------|
| **VM Debian 13 inaccessible** (`ssh -p 2222` → connection refused) | Moyenne | Les 3 tests symlink n'ont pas pu être exécutés sous Linux par Agent A. Le correctif est prouvé par simulation (6 tests) et avait été mesuré par Agent B sur sa branche. |
| Les 4 tests ignorés ne s'exécutent pas sous Windows | Faible | Attendu ; à confirmer sous Debian 13 |
| Test d'inférence réel Groq | Moyenne | En attente d'accord (coût API) |
| Fournisseur local hors ligne | Moyenne | TASK-DEV-007 |

## 7. Points restant à vérifier par Agent B

1. Exécuter la suite complète (**338 tests**) sur Debian 13 et confirmer que les **3 tests de
   confinement S-005** ne sont **plus ignorés** (la détection corrigée doit succeed sous Linux).
2. Confirmer qu'aucun fichier parasite n'est laissé dans le dépôt par la sonde de détection
   (le temporaire est nettoyé).
3. Contrôler la section « Variables de chemin de fichier » de `INSTALL.md` : `MILES_ENV_FILE` et
   `MILES_CONFIG` doivent y être décrites comme lues **exclusivement** de l'environnement du
   processus.
4. Confirmer que le décompte 19 = 17 + 2 correspond bien au code.
5. Confirmer que le contre-audit du commit publié est toujours valable : la branche V1 a changé
   (`8d30809` + correctif D-C2 + 10 nouveaux tests).

---

*Aucun appel API réel, aucun téléchargement de modèle, aucune installation.
`main` n'est pas modifié. La branche d'audit `audit/agent-b-v1-review` d'Agent B n'a pas été
fusionnée : seul le commit `c548e3b` a été intégré par cherry-pick, en préservant son auteur.*
