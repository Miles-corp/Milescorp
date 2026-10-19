# docs/reports/PHASE_4_REVIEW_AGENT_B.md — Rapport de révision Phase 4 : Moteur d'outils (Agent A)

## 1. Contexte

Suite à la revue indépendante d'Agent B, quatre défauts (L-007 à L-010) ont été identifiés dans le moteur d'outils MILES. Ce rapport documente les corrections apportées et les résultats des tests.

## 2. Défaut L-007 : Arrêt effectif après timeout (critique)

### Problème
Dans `app/tools/engine.py`, la méthode `_execute_tool` utilisait `threading.Thread` avec `thread.join(timeout=...)`. Cela ne garantissait pas l'arrêt effectif du handler : le thread continuait à tourner en arrière-plan même après le dépassement du délai, pouvant modifier des données ou effectuer des appels réseau.

### Correction
Remplacement du `threading.Thread` par `multiprocessing.Process` avec une fonction de module niveau (`_run_handler_in_process`). En cas de dépassement du délai, le processus est terminé avec `process.terminate()` puis `process.kill()` si nécessaire, garantissant l'arrêt effectif.

### Tests ajoutés
- `test_depassement_delai` : vérifie qu'un délai est détecté.
- `test_depassement_delai_arret_effectif` : vérifie qu'après un timeout, une nouvelle tâche peut démarrer (le processus précédent a été arrêté).

## 3. L-008 : Application réelle de la politique de sécurité (critique)

### Problème
Les méthodes de validation de `ToolPolicy` (`validate_no_shell_access`, `validate_no_code_execution`, `validate_no_secret_access`) existaient mais n'étaient pas appelées dans `request_tool`.

### Correction
Appel des trois méthodes de validation dans `request_tool`, après validation des paramètres et avant exécution :
- `validate_no_shell_access(parameters)`
- `validate_no_code_execution(parameters)`
- `validate_no_secret_access(parameters)`

La politique a aussi été étendue pour vérifier récursivement les clés et valeurs dans les structures imbriquées (dict, list, tuple, set).

### Tests ajoutés
- `test_parametre_shell_refuse` : paramètre `shell` rejeté.
- `test_parametre_command_refuse` : paramètre `command` rejeté.
- `test_parametre_code_refuse` : paramètre `code` rejeté.
- `test_parametre_secret_refuse` : paramètre `api_key` rejeté.
- `test_valeur_secrete_refusee` : valeur contenant un secret rejetée.

## 4. L-009 : Expiration des confirmations (critique)

### Problème
Les jetons de confirmation n'avaient pas de durée de validité, ce qui permettait une utilisation indéfinie.

### Correction
Ajout d'un champ `expires_at` à `_PendingConfirmation`, calculé à partir d'une horloge injectable (`clock`) avec un TTL par défaut de 300 secondes (5 minutes). Les tokens expirés sont rejetés et supprimés du dictionnaire des confirmations en attente.

### Tests ajoutés
- `test_confirmation_expiree_refusee` : vérifie qu'un token expiré est rejeté.
- `test_confirmation_valide_dans_delai` : vérifie qu'un token valide dans le délai fonctionne.
- `test_confirmation_utilisee_uneseulefois` : vérifie qu'un token ne peut être utilisé qu'une seule fois.

## 5. L-010 : Protection des journaux d'audit (critique)

### Problème
Les exceptions brutes des handlers étaient journalisées dans `DECISIONS.md`, ce qui pouvait exposer des secrets ou des détails d'implémentation.

### Correction
Le journal d'audit enregistre désormais un message d'erreur générique ("Erreur d'exécution.") au lieu de l'exception brute. Les exceptions brutes ne sont jamais journalisées.

### Tests ajoutés
- `test_audit_sans_secret` : vérifie qu'aucune clé API ou secret n'apparaît dans les entrées d'audit.
- `test_exception_handler` : vérifie qu'aucune exception brute n'apparaît dans le message d'erreur.

## 6. Résultats des tests

```
Ran 137 tests in 16.715s
OK
```

Tous les 137 tests passent, dont :
- 67 tests préexistants (non modifiés)
- 70 nouveaux tests pour Phase 4 (registre, politique, audit, moteur, outil status)

## 7. Limites restantes

| Limite | Explication |
|--------|-------------|
| Arrêt effectif sous Windows | Le `multiprocessing.Process` avec `daemon=True` fonctionne, mais le processus enfant peut prendre jusqu'à 5 secondes pour s'arrêter après `process.terminate()`. |
| Confirmation par jeton | Le jeton est stocké en mémoire vive ; il est perdu en cas de redémarrage du processus. |
| Pas d'exécution réelle de fournisseur IA | Aucun appel API n'a été effectué (pas de clé API configurée pour les tests). |

## 8. Risque non résolu

Aucun risque de sécurité critique non résolu à ce stade. Les quatre défauts identifiés (L-007 à L-010) ont été corrigés.

## 9. Prochaine étape

Agent B doit effectuer la revue indépendante de ces modifications et valider les tests avant publication sur GitHub.
