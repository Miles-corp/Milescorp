# docs/reports/PHASE_4_PULL_REQUEST_DRAFT_AGENT_A.md — Brouillon de Pull Request (Agent A)

> **BROUILLON LOCAL — NE PAS OUVRIR TEL QUE LA PR EST PRÊTE À ÊTRE FUSIONNÉE.**
> Ce document n'a pas été publié sur GitHub. La Pull Request n'a pas été ouverte.
> La fusion vers `main` reste bloquée tant que la validation Debian 13 (Agent B)
> et la revue du rapport Agent B ne sont pas examinées.

---

## Titre proposé

```
fix(tools): corriger les défauts de sécurité L-007 à L-010 du moteur d'outils
```

## Branche source

`review/phase4-security-fixes`

## Branche cible

`main`

## Contexte et objectif

Le moteur d'outils MILES (`app/tools/`) a été soumis à une revue de sécurité
indépendante par Agent B. Quatre défauts ont été relevés :

| ID | Défaut | Impact |
|----|--------|--------|
| L-007 | Le timeout d'exécution reposait sur `threading.Thread` + `join(timeout)`, sans arrêt effectif : le handler continuait à s'exécuter en arrière-plan (modifications de données, appels réseau) | Critique |
| L-008 | Les trois validations de `ToolPolicy` existaient mais n'étaient **jamais appelées** par le moteur : la politique de sécurité n'était pas appliquée | Critique |
| L-009 | Les jetons de confirmation n'avaient aucune durée de validité : utilisation illimitée | Critique |
| L-010 | Les exceptions brutes des handlers étaient journalisées, risques de divulgation de secrets | Critique |

Cette PR corrige ces quatre défauts sans modifier le comportement public de
l'API du moteur (`ToolEngine.request_tool`, `ToolResult`, `ToolRegistry`,
`ToolPolicy`, `AuditLogger`).

## Fichiers concernés

| Fichier | Nature | Contenu |
|---------|--------|---------|
| `app/tools/engine.py` | Modifié | Arrêt effectif via `multiprocessing.Process` (`terminate()` / `kill()`) ; application de la politique avant exécution ; expiration des confirmations (TTL 300 s, horloge injectable) ; messages d'erreur génériques dans l'audit |
| `app/tools/policy.py` | Modifié | Validation récursive des clés **et** des valeurs dans les structures imbriquées (dict, list, tuple, set) |
| `tests/test_tool_engine.py` | Modifié | 18 tests du moteur, incluant les cas L-007 à L-010 |
| `docs/reports/PHASE_4_REVIEW_AGENT_B.md` | Créé | Rapport de revue Phase 4 |

**Hors périmètre de cette PR** (constats de l'audit complémentaire Agent A, à traiter séparément) :
S-001 à S-012 de `docs/reports/PHASE_4_SUPPLEMENTARY_SECURITY_AUDIT_AGENT_A.md`.

## Tests réellement exécutés

### Agent A — Windows, Python 3.12.10

```
$ python -m unittest discover -s tests
Ran 161 tests in 20.081s
OK
```

| Mesure | Valeur |
|--------|--------|
| Tests découverts | 161 |
| Réussis | 161 |
| Échecs | 0 |
| Erreurs | 0 |
| Ignorés | 0 |

Dont 15 tests complémentaires ajoutés par Agent A sur sa branche de travail
locale (`work/agent-a-phase4-audit`, non publiée) : expiration déterministe
des confirmations, validation récursive de la politique, confidentialité de
l'audit face à une exception contenant une fausse clé API, preuve que le
handler n'est pas invoqué après un refus de politique.

### Agent B — validation en cours

| Plateforme | Résultat | Statut |
|-----------|----------|--------|
| Windows, Python 3.14.7 | 146 tests, 146 OK (commit `4b6f515`) | ✅ |
| Debian 13 | — | ⏳ **EN ATTENTE** |

## Rapports à consulter avant fusion

| Rapport | Emplacement | Contenu |
|---------|-------------|---------|
| Revue Phase 4 (Agent B) | `docs/reports/PHASE_4_REVIEW_AGENT_B.md` (branche `review/agent-b-phase4-review`, commit `928410c`) | Constats de la revue, validation Windows, limites |
| Audit complémentaire (Agent A) | `docs/reports/PHASE_4_SUPPLEMENTARY_SECURITY_AUDIT_AGENT_A.md` | 12 constats supplémentaires (S-001 à S-012) |
| Tests complémentaires (Agent A) | `docs/reports/PHASE_4_ADDITIONAL_TESTS_AGENT_A.md` | Lacunes comblées, résultats, limites |
| Checklist de livraison (Agent A) | `docs/reports/PHASE_4_RELEASE_CHECKLIST_AGENT_A.md` | Critères d'acceptation, conditions bloquantes |
| Rapport Phase 4 initial | `docs/reports/PHASE_4_TOOL_ENGINE.md` | Architecture d'origine |

## Risques résiduels

| Risque | Description | Mitigation en place |
|--------|-------------|---------------------|
| Effets de bord avant timeout | Un handler peut avoir déjà écrit un fichier ou émis une requête avant d'être arrêté par `terminate()`. | Arrêt effectif du processus ; la garantie porte sur l'arrêt, pas sur l'annulation des effets déjà produits. Documenté. |
| Mode `spawn` sous Windows | Les handlers doivent être picklables : pas de closure, pas de lambda dans un `ToolDefinition`. | Documenté dans le rapport. Comportement `fork` sous Linux **non validé** (en attente Debian 13). |
| Fuite de descripteurs | Les `multiprocessing.Queue` ne sont jamais fermées (2 par appel d'outil). | Constat S-006 ; non corrigé dans cette PR, à traiter. |
| CSRF sur les routes web | Les routes POST de l'interface web n'ont ni jeton ni contrôle d'origine. | Constat S-002 / S-008 ; hors périmètre de cette PR, mais bloquant pour une exposition réseau. |
| Divulgation d'erreurs HTTP | Les exceptions du fournisseur IA (corps de réponse tronqué) sont renvoyées au navigateur. | Constat S-003 ; hors périmètre de cette PR. |
| Traversée par symlink | `list_files` compare des `abspath` (non `realpath`). | Constat S-005 ; hors périmètre de cette PR. |
| `NameError` latent | `miles.py` référence `PersistentMemoryError` sans l'importer. | Constat S-001 ; hors périmètre de cette PR. |

## Critères d'acceptation

- [x] Les tests existants (67 d'origine, 146 au total sur `4b6f515`) restent verts
- [x] L-007 : le processus est arrêté après expiration du délai
- [x] L-008 : la politique est appliquée avant toute exécution, structures imbriquées comprises
- [x] L-009 : les confirmations expirent, sont liées aux paramètres exacts et à usage unique
- [x] L-010 : aucune exception brute n'est journalisée
- [x] Aucune clé API ni donnée privée n'est introduite
- [x] Les fournisseurs distants et locaux existants restent inchangés
- [ ] **Résultats de la validation Debian 13 (Agent B)**
- [ ] **Revue du rapport Agent B `928410c` intégrée**
- [ ] **Décision sur les constats S-001 à S-006 de l'audit complémentaire**

## Vérifications restant à effectuer avant fusion

1. Exécuter `python3 -m unittest discover -s tests -v` sur Debian 13 sur le commit candidat.
2. Vérifier le comportement `fork` de `multiprocessing` sous Debian 13 (handlers picklables, arrêt effectif).
3. Lire et arbitrer les constats du rapport Agent B `928410c`.
4. Arbitrer les constats S-001 à S-006 de l'audit complémentaire Agent A (au minimum S-001 à S-005, bloquants).
5. Vérifier l'absence de secrets : `git ls-files | grep -iE '\.env$|\.db$'` doit être vide.
6. Compléter la documentation (`INSTALL.md`, `QUICKSTART.md`) sur les outils et la mémoire persistante.
7. Mettre à jour `docs/coordination/TASKS.md` et `STATUS.md` pour acter la clôture de la Phase 4.

## Note de procédure

Cette branche a été poussée **dans le seul but de permettre la revue indépendante**
par Agent B. La publication d'une branche de revue ne constitue ni une
approbation de sécurité, ni une autorisation d'intégrer automatiquement les
changements dans `main`. La fusion fera l'objet d'une Pull Request distincte,
ouverte après examen des rapports.
