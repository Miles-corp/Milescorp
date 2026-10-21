# docs/reports/PHASE_5_TOOL_ENGINE_INTEGRATION_AGENT_A.md — Intégration du moteur d'outils dans le CLI et l'interface web (Agent A)

- **Auteur** : Agent A
- **Date** : 2026-10-20
- **Branche** : `feature/miles-tool-engine-integration` (base `bccdc1c` = `feature/miles-v1-conversation-persistence`)
- **Tâche** : TASK-DEV-013
- **Environnement de validation** : Windows, Python 3.12.10

---

## 1. Résumé exécutif

Le moteur d'outils de la Phase 4 existait mais n'était **branché nulle part** : le registre n'était jamais alimenté en production, `CLI.propose_action()` n'était jamais appelé et l'interface web n'exposait aucune route d'outils.

Cette mission branche le moteur dans les **deux interfaces via une couche métier unique** (`ToolService`), sans duplication de logique et sans nouvelle dépendance. Quatre outils réellement implémentés sont enregistrés : `status_read`, `action_datetime`, `action_workdir`, `action_list_files`.

- **40 nouveaux tests** (`tests/test_tool_integration.py`) couvrant les 12 catégories exigées.
- **378 tests OK** au total sur Windows (338 antérieurs + 40 nouveaux), 0 échec, 4 ignorés (limites Windows : symlink, descripteurs de fichiers).
- Aucun appel API payant, aucun téléchargement de modèle, aucun accès shell arbitraire.

---

## 2. Synchronisation préalable et cartographie

| Contrôle | Résultat |
|----------|----------|
| `git fetch origin --prune` | `main` = `b9b7e7d`, branche V1 = `bccdc1c`, audit Agent B = `77fa39b` |
| Branche de travail | `feature/miles-tool-engine-integration` créée depuis `bccdc1c` (V1) |
| Modifications locales | Uniquement l'artefact parasite `tatus --short --branch` (préservé, non committé) |

### 2.1 Cartographie avant modification

| Élément | État constaté | Conséquence |
|---------|---------------|-------------|
| `app/tools/registry.py` | `ToolRegistry` n'était instancié que dans les tests | `ToolRegistry().list_tools()` retournait `[]` : aucun outil disponible en production |
| `app/interface/cli.py` | `propose_action()` présent mais **jamais appelé** ; utilisait l'ancien `ActionValidator` (logique parallèle, hors moteur) | Deux systèmes d'actions coexistaient |
| `app/interface/web.py` | Aucune route outil | Le web n'exposait pas le moteur |
| `app/tools/engine.py` | Validation, permissions, confirmation à jeton, timeout, audit déjà implémentés | Réutilisable tel quel, sans réécriture |
| `miles.py` | Instancie CLI et web séparément | Aucun service partagé à injecter |

**Décision structurante** : ne pas réécrire le moteur, ni rebrancher l'ancien `ActionValidator`. Le moteur existant devient le **seul** chemin d'exécution des outils ; l'ancien chemin est conservé en lecture seule pour compatibilité (jamais appelé).

---

## 3. Architecture retenue

```
        CLI (/tools, /tool)                 WebApp (GET /tools, POST /tool)
                 \                                    /
                  \          ToolService (unique)     /
                   \         - ToolRegistry           /
                    \        - ToolPolicy             /
                     \       - AuditLogger            /
                      \      - ToolEngine             /
                       \_____________________________/
```

- `ToolService` est la **façade unique** : `list_tools()`, `has_tool()`, `request_tool()`, `describe_result()`.
- Toute la logique métier (validation, permissions, confirmation, délai, audit) reste dans `ToolEngine`.
- CLI et web reçoivent **la même instance** : aucun doublon, comportement identique par construction (test de non-doublon : `assertIs(cli.tool_service, app.tool_service)`).
- `miles.py` construit **un seul** `ToolService` et l'injecte dans le CLI et le web.

### 3.1 Fichiers créés

| Fichier | Rôle |
|---------|------|
| `app/tools/local_actions.py` | Handlers locaux picklables : `datetime_handler`, `workdir_handler`, `list_files_handler` (chemins confinés) |
| `app/tools/builtin.py` | `build_default_registry()` : enregistre les 4 outils réellement implémentés ; `KNOWN_PERMISSIONS` |
| `app/tools/service.py` | `ToolService` : façade commune CLI/web |

### 3.2 Fichiers modifiés

| Fichier | Modification |
|---------|--------------|
| `app/interface/cli.py` | Commandes `/tools` et `/tool`, confirmation interactive, injection du `ToolService` |
| `app/interface/web.py` | Routes `GET /tools` et `POST /tool`, méthodes `WebApp.list_tools()` / `WebApp.run_tool()`, panneau « Outils » dans l'interface HTML, injection du `ToolService` |
| `app/tools/status_tool.py` | Précision de la docstring : état de **référence statique**, pas un état en direct |
| `miles.py` | Instanciation d'un `ToolService` unique, injecté dans le CLI |
| `tests/test_tool_integration.py` | 40 tests d'intégration (nouveau) |

---

## 4. Outils enregistrés (aucun outil fictif)

| Identifiant | Risque | Permission | Confirmation | Comportement réel |
|-------------|--------|------------|--------------|-------------------|
| `status_read` | LOW | — | non | Retourne un état de **référence statique** ; la description indique explicitement que ces valeurs ne reflètent pas l'instance en cours |
| `action_datetime` | LOW | — | non | Date et heure locales |
| `action_workdir` | LOW | — | non | Répertoire de travail courant |
| `action_list_files` | MEDIUM | `lecture_systeme` | **oui** | Liste un répertoire, chemin confiné aux racines autorisées (projet, `data/`) |

Le registre ne déclare aucun outil non implémenté : `status_read` est un état de référence explicitement étiqueté, pas une fausse promesse d'état live.

---

## 5. Sécurité

### 5.1 Périmètre couvert par le moteur existant (réutilisé, non réécrit)

| Contrôle | Comportement observé |
|----------|----------------------|
| Outil inconnu | Refus : `Outil inconnu : <id>` |
| Paramètre non déclaré / mauvais type | Refus avec message détaillant le paramètre |
| Permission manquante | Refus : `Permissions manquantes : ...` |
| Confirmation MEDIUM/HIGH | Jeton lié à l'outil **et** aux paramètres exacts, usage unique, TTL 300 s |
| Clé suspecte (`password`, `shell`, `token`…) | Refus par la politique de sécurité |
| Chemin hors racines autorisées | `PermissionError` → erreur d'exécution générique (`Erreur d'exécution.`) |
| Délai dépassé | Arrêt effectif du sous-processus : `Délai d'attente dépassé (10s). Exécution arrêtée.` |
| Exception du handler | Capturée, message brut **non divulgué** (`Erreur d'exécution.`) |
| Secret dans les logs/audit | Aucun secret n'apparaît dans la réponse, l'audit ou le catalogue |

### 5.2 Points de vigilance documentés

1. **Confirmation non liée à une identité** : le jeton est lié à l'outil et aux paramètres, mais pas à un utilisateur. Dans ce jalon, les routes `/tool` **ne sont pas exposées au modèle** (aucun appel d'outil depuis le LLM), la confirmation provient donc d'une action humaine explicite (touche `Entrée` au CLI, bouton « Confirmer » du navigateur). Toute mise à disposition d'outils au modèle exigera un binding du jeton à une session humaine.
2. **`status_read` statique** : choix assumé. Le moteur exécute les handlers dans un sous-processus (`spawn` sous Windows) qui ne partage pas l'état de l'application ; un état live exigerait un mécanisme de partage (fichier d'instantané ou `multiprocessing.Manager`) hors périmètre de cette mission. Le comportement est donc **documenté dans la description de l'outil** plutôt que présenté comme dynamique.
3. **Permissions accordées par l'application** : `ToolService` accorde par défaut `lecture_systeme` (lecture seule). Aucune permission d'écriture n'existe dans le registre.

### 5.3 Confirmation humaine

- **CLI** : `/tool action_list_files path=data` → message « Confirmation humaine requise », lecture clavier, acceptation par `o`/`oui`/`y`/`yes` ; toute autre réponse annule. En cas d'interruption clavier (`Ctrl+C`, `EOF`), l'action est annulée.
- **Web** : première requête → HTTP 200 + `confirmation_required: true` + jeton ; l'interface affiche une boîte de confirmation ; seule la confirmation déclenche un second appel avec `user_confirmed: true` et le jeton.

---

## 6. Tests

### 6.1 Nouveau fichier `tests/test_tool_integration.py` (40 tests)

| # | Catégorie exigée | Test(s) |
|---|------------------|---------|
| 1 | Découverte des outils | `test_registre_alimente_par_defaut`, `test_service_liste_le_catalogue`, `test_liste_des_outils` |
| 2 | Registre vide / outil inconnu | `test_registre_vide`, `test_outil_inconnu_refuse`, `test_outil_inconnu_refuse_via_cli` |
| 3 | Appel valide depuis le CLI | `test_appel_outil_valide_depuis_la_cli` |
| 4 | Paramètres invalides | `test_parametre_invalide_rejete`, `test_parametre_non_decl_refuse`, `test_parametre_mauvais_type_refuse`, `test_usage_sans_argument` |
| 5 | Permission absente | `test_permission_absente_refusee` |
| 6 | Confirmation obligatoire | `test_action_sensible_exige_confirmation`, `test_confirmation_valide_execute`, `test_confirmation_refusee_n_execute_pas`, `test_cli_demande_confirmation`, `test_cli_annule_si_confirmation_refusee` |
| 7 | Erreurs et exceptions | `test_exception_du_handler_capturee`, `test_erreur_de_timeout` |
| 8 | Invocation web | `test_route_tools_liste_le_catalogue`, `test_route_tool_execute_un_outil_valide`, `test_route_tool_outil_inconnu`, `test_route_tool_demande_confirmation`, `test_route_tool_confirmation_valide`, `test_route_tool_parametres_invalides`, `test_route_tool_jeton_invalide` |
| 9 | Comportement commun CLI/web | `test_cli_et_web_partagent_le_meme_service`, `test_meme_resultat_cli_et_web` |
| 10 | Non-divulgation des secrets | `test_parametre_secret_refuse`, `test_cle_shell_refusee`, `test_secret_absent_du_catalogue`, `test_secret_absent_de_la_reponse_web` |
| 11 | Régression conversation / persistance SQLite | `test_conversation_toujours_functionnelle`, `test_persistance_sqlite_intacte`, `test_outils_independants_de_la_conversation` |
| 12 | Aucune action réelle | `test_outil_liste_fichiers_ne_modifie_rien`, `test_outil_liste_fichiers_refuse_chemin_hors_racines`, `test_outil_datetime_est_sans_effet_de_bord`, `test_aucun_appel_reseau_par_les_outils`, `test_action_externe_refusee_sans_confirmation` |

Note d'implémentation : le moteur exécute les handlers dans un sous-processus, donc les handlers de test sont définis **au niveau du module** (une fonction locale n'est pas picklable sous `spawn`).

### 6.2 Résultats

| Contrôle | Commande | Résultat |
|----------|----------|----------|
| Suite complète | `python -m unittest discover -s tests` | **378 tests OK, 0 échec, 4 ignorés** (46–58 s) |
| Intégration outils | `python -m unittest tests.test_tool_integration` | **40 tests OK** |
| Web + sécurité web + intégration | `python -m unittest tests.test_web tests.test_web_security tests.test_tool_integration` | **87 tests OK** |
| Compilation | `python -m compileall app miles.py` | **OK** |

Les 4 tests ignorés sont des limites Windows connues (3 symlink, 1 descripteurs de fichiers), non des régressions.

---

## 7. Vérifications manuelles

**CLI**
```
/tools                                  -> 4 outils listés, risque et confirmation indiqués
/tool action_workdir                    -> [Outil exécuté] + chemin
/tool action_list_files path=data       -> "Confirmation humaine requise" puis exécution après "o"
/tool action_list_files path=data       -> "Action annulée" après "n"
/tool outil_inconnu                     -> [Outil refusé ou en échec] Outil inconnu : outil_inconnu
```

**Web** (serveur local, port éphémère)
```
GET  /                      -> 200, panneau « Outils » présent
GET  /tools                 -> 200, ['action_datetime','action_list_files','action_workdir','status_read']
POST /tool action_datetime  -> 200, success: true
POST /tool action_list_files-> 200, confirmation_required: true + jeton
POST /tool (confirmation)   -> 200, success: true
```

---

## 8. Limites et travail restant

| Limite | Impact | Suite |
|--------|--------|-------|
| Confirmation non liée à une identité utilisateur | Le jeton seul autorise la confirmation | À traiter avant toute exposition des outils au modèle |
| `status_read` statique | Pas d'état live | Snapshot partagé (fichier ou `Manager`) |
| Pas d'outils exposés au LLM | Les outils sont pilotés par l'utilisateur (CLI/web) | Phase ultérieure : function calling avec jeton lié à l'utilisateur |
| Pas d'écriture sur disque | `action_list_files` est en lecture seule | Ajouter un outil d'écriture class HIGH si nécessaire |
| Validation Debian 13 non faite | Tests validés sous Windows uniquement | À exécuter sur la VM par Agent B |
| 4 tests ignorés sous Windows | Limites plateforme (symlink, fd) | Validation Debian 13 |

---

## 9. Confidentialité

- Aucun secret, clé API, mot de passe ou donnée personnelle dans le code, les tests, la documentation ou les messages.
- L'artefact local parasite `tatus --short --branch` est **préservé et non committé**.
- Aucun appel API payant, aucun téléchargement de modèle, aucune nouvelle dépendance (bibliothèque standard uniquement).

---

## 10. Fichiers modifiés / ajoutés

**Ajoutés**
- `app/tools/local_actions.py`
- `app/tools/builtin.py`
- `app/tools/service.py`
- `tests/test_tool_integration.py`
- `docs/reports/PHASE_5_TOOL_ENGINE_INTEGRATION_AGENT_A.md`

**Modifiés**
- `app/interface/cli.py`
- `app/interface/web.py`
- `app/tools/status_tool.py`
- `miles.py`
- `docs/coordination/TASKS.md`
- `docs/coordination/STATUS.md`
- `docs/coordination/DECISIONS.md`
