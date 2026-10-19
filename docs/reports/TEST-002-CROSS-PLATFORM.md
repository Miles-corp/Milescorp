# docs/reports/TEST-002-CROSS-PLATFORM.md — Rapport TEST-002 : Campagne de tests Windows + Debian 13 (Agent A)

## 1. Contexte et objectif

Tester MILES sur Windows (Agent A) et organiser une comparaison avec les tests réalisés par Agent B sur Debian 13. Connaître les fonctions réellement utilisables, les erreurs, les différences entre systèmes et les prochaines corrections prioritaires.

## 2. Commits testés sur chaque système

| Système | Commit testé | Message |
|---------|-------------|---------|
| Windows (Agent A) | `fe5a017` + correction L-006 (non publiée au moment du test) | MILESTONE-006 + correction dégradation gracieuse |
| Debian 13 (Agent B) | `5c63332` | MILESTONE-005 (avant MILESTONE-006) |

**Attention** : les deux systèmes n'ont pas testé exactement le même commit. Agent B a testé `5c63332` (MILESTONE-005), tandis que le dépôt actuel est à `fe5a017` (MILESTONE-006) plus la correction L-006 non publiée. Cette différence doit être prise en compte dans toute comparaison.

## 3. Systèmes et versions Python

| Système | Version Python | Environnement virtuel | Dépendances vocales |
|---------|---------------|----------------------|---------------------|
| Windows (Agent A) | **Non installé** | Non créé | Non installées |
| Debian 13 (Agent B) | Python 3.14.7 | Créé | Non installées |

## 4. Dépendances et configuration utilisées

Le cœur de MILES utilise uniquement la bibliothèque standard Python (`urllib`, `json`, `sqlite3`, `unittest`, `argparse`, `os`, `datetime`, `tempfile`, `shutil`). Aucune dépendance externe n'est requise pour le mode texte.

Fichiers de configuration utilisés :
- `config/config.json.example` → copié en `config/config.json`
- `.env.example` → copié en `.env`
- Aucune vraie clé API n'a été utilisée (tests avec mocks uniquement)

## 5. Commandes réellement exécutées

### Sur Windows (Agent A)

**Aucune commande n'a pu être exécutée** car `python3` n'est pas installé sur ce poste.

### Sur Debian 13 (Agent B, rapport transmis)

| Commande | Résultat |
|----------|----------|
| `python -m unittest discover -s tests -v` | 67 tests, 66 OK, 1 erreur |

## 6. Résultats des tests automatisés

### Résultats déclarés par Agent B (Debian 13, commit `5c63332`)

| Fichier de tests | Nombre de tests | Résultat |
|------------------|-----------------|----------|
| `tests/test_conversation.py` | 7 | Tous OK |
| `tests/test_actions.py` | 7 | Tous OK |
| `tests/test_providers.py` | 5 | Tous OK |
| `tests/test_cli_reliability.py` | 5 | Tous OK |
| `tests/test_settings.py` | 9 | Tous OK |
| `tests/test_voice.py` | 6 | Tous OK |
| `tests/test_memory_persistent.py` | 18 | 17 OK, 1 erreur |
| `tests/test_milestone_005.py` | 10 | Tous OK |
| **Total** | **67** | **66 OK, 1 erreur** |

### Erreur détectée (L-006)

| Test | Fichier | Erreur |
|------|---------|--------|
| `test_corrupt_database_raises` | `tests/test_memory_persistent.py` | `sqlite3.DatabaseError: file is not a database` au lieu de dégradation gracieuse (`is_available = False`, pas d'exception) |

**Note** : le nom du test (`test_corrupt_database_raises`) suggère qu'une exception doit être levée, mais le corps du test attend une dégradation gracieuse. Cette contradiction doit être clarifiée avec Agent A.

### Résultats sur Windows (Agent A)

**Aucun résultat** (pas de Python 3 installé).

## 7. Résultats des essais manuels

### Sur Windows (Agent A)

**Aucun essai manuel n'a pu être réalisé** (pas de Python 3).

### Sur Debian 13 (Agent B)

Agent B a déclaré avoir exécuté les essais manuels suivants (d'après son rapport) :
- Démarrage et arrêt : OK
- `/help`, `/status`, `/provider` : OK
- Mémoire persistante : OK (sauf base corrompue → erreur L-006)
- Suppression : OK
- Filtre de secrets : OK

Ces résultats n'ont pas pu être vérifiés de manière indépendante par Agent A.

## 8. Tableau PASS / FAIL / BLOCKED

| Critère | Windows (Agent A) | Debian 13 (Agent B) | Preuve |
|---------|-------------------|---------------------|--------|
| Tests automatisés passent | BLOCKED (pas de Python 3) | 66/67 OK | Rapport Agent B |
| `miles.py --help` | BLOCKED | Non documenté | — |
| Conversation IA | BLOCKED | Non testé (pas de fournisseur) | — |
| Mémoire persistante | BLOCKED | OK (sauf L-006) | Rapport Agent B |
| Persistance après redémarrage | BLOCKED | Non documenté | — |
| Refus des secrets | BLOCKED | OK | Rapport Agent B |
| Dégradation gracieuse voix | BLOCKED | OK | Rapport Agent B |
| Dégradation gracieuse base corrompue | BLOCKED | FAIL (L-006) | Rapport Agent B |
| Pas de secrets dans le dépôt | Vérifié (statique) | Vérifié (statique) | Inspection du code |

## 9. Différences entre Windows et Debian

| Élément | Windows (Agent A) | Debian 13 (Agent B) |
|---------|-------------------|---------------------|
| Python 3 | Non installé | Python 3.14.7 installé |
| Tests exécutés | Aucun | 67 tests, 66 OK, 1 erreur |
| Essais manuels | Aucun | Déclarés par Agent B |
| Environnement virtuel | Non créé | Créé |
| Dépendances vocales | Non installées | Non installées |

## 10. Défauts reproduits et étapes de reproduction

| ID | Défaut | Étapes de reproduction | Statut |
|----|--------|----------------------|--------|
| L-006 | Base SQLite corrompue lève `sqlite3.DatabaseError` au lieu de dégradation gracieuse | 1. Créer un fichier non-SQLite à l'emplacement `data/memory.db`<br>2. `PersistentMemory(enabled=True, db_path=...)`<br>3. Exception levée au lieu de `is_available = False` | Corrigé par Agent A (pas d'exception, `is_available=False`), **non re-vérifié par exécution** |

## 11. Fonctions utilisables aujourd'hui (par inspection statique)

- Interface terminal avec commandes `/help`, `/status`, `/provider`, `/quit`
- Sélection explicite fournisseur distant/local
- Mémoire persistante locale SQLite (`/remember`, `/memory`, `/forget`)
- Détection et refus des secrets
- Dégradation gracieuse : fournisseur indisponible, voix absente
- Dégradation gracieuse : base corrompue (L-006 corrigé, non re-vérifié)

## 12. Limitations connues

- Aucun test n'a pu être exécuté sur Windows (pas de Python 3).
- Les résultats de Debian 13 proviennent du rapport d'Agent B, non vérifiés indépendamment.
- Aucun fournisseur IA réel n'a été testé (pas d'endpoint, pas de clé API).
- La persistance après redémarrage n'a pas été testée manuellement.
- Validation sur Debian 13 incomplète (1 erreur L-006, maintenant corrigée mais non re-testée).

## 13. Corrections prioritaires

1. **Publier la correction L-006** sur GitHub (dégradation gracieuse sur base corrompue).
2. **Re-exécuter les tests** sur Debian 13 après la correction L-006 pour confirmer 67/67 OK.
3. **Clarifier le test `test_corrupt_database_raises`** : le nom suggère qu'une exception doit être levée, mais le corps attend une dégradation gracieuse. À aligner.
4. **Tester avec un fournisseur IA réel** pour valider la conversation.
5. **Valider la persistance après redémarrage** par un test manuel réel.

## 14. Bilan final

- **Sur Windows** : MILES ne peut pas être testé (pas de Python 3). Aucune fonction n'a pu être vérifiée par exécution.
- **Sur Debian 13** : 66/67 tests passent. La seule erreur (L-006) est corrigée dans le code mais n'a pas été re-vérifiée par exécution.
- **MILES n'est pas encore prêt pour un usage quotidien** : la conversation IA n'a pas été testée avec un vrai fournisseur, et la validation sur Debian 13 est incomplète.

---

*Aucun commit ni push n'a été effectué pour ce rapport. Il sera publié avec le rapport TEST-001 après autorisation.*
