# docs/reports/PHASE_4_ADDITIONAL_TESTS_AGENT_A.md — Tests complémentaires de sécurité (Agent A)

## 1. Cadre

| Élément | Valeur |
|---------|--------|
| Auteur | Agent A |
| Date | 2026-10-19 |
| Branche de travail | `work/agent-a-phase4-audit` (créée depuis `4b6f515`, **non publiée**) |
| Fichier de tests ajouté | `tests/test_tool_engine_security_extra.py` |
| Fichiers applicatifs modifiés | **Aucun** |

## 2. Lacunes identifiées dans la suite existante

| Lacune | Couverture existante | Justification d'un test complémentaire |
|---------|---------------------|------------------------------------------|
| Expiration des confirmations | `test_confirmation_expiree_refusee` (engine) utilise `time.sleep(0.2)` | Le test existant dépend du temps réel : il peut être instable sous forte charge ou sur une machine lente. Un test à horloge déterministe est plus fiable et couvre la frontière exacte du TTL. |
| Validation récursive de la politique | Aucune | La correction L-008 a introduit la récursion (`_iter_keys` / `_iter_values`) dans `app/tools/policy.py`. Aucun test ne vérifie le comportement sur structures imbriquées. |
| Insensibilité à la casse | Aucune | La politique compare `key.lower()`. Le comportement sur majuscules n'était pas vérifié. |
| Clés de dictionnaire non textuelles | Aucune | `key.lower()` levée sur une clé non-`str` planterait. La version actuelle est protégée par `isinstance(key, str)` mais rien ne le vérifie. |
| Confidentialité de l'audit face à une exception sensible | `test_audit_sans_secret` utilise un *paramètre* contenant `sk-` | Le test existant ne couvre pas le cas d'une **exception de handler** contenant une fausse clé. C'est précisément le scénario corrigé par L-010. |
| Preuve que le handler n'est pas appelé après refus | Aucune | L'008 exige que l'outil ne soit pas exécuté. Aucun test ne prouve l'absence d'appel au handler. |
| Consommation du jeton quand l'exécution échoue | Aucune | Un jeton doit être à usage unique, y compris si le handler échoue. |
| Absence de paramètres bruts dans l'audit | `test_audit_sans_secret` vérifie `error_message` | Le champ `parameters_hash` n'est pas vérifié (présence et longueur). |

## 3. Tests ajoutés (15 tests)

Fichier : `tests/test_tool_engine_security_extra.py`

### 3.1 `TestConfirmationExpirationDeterministic` (4 tests)

| Test | Objet |
|------|-------|
| `test_jeton_valide_avant_expiration` | À 299 s (TTL = 300 s), le jeton est encore accepté |
| `test_jeton_expire_apres_ttl` | À 301 s, le jeton est refusé et une nouvelle confirmation est exigée |
| `test_jeton_expire_inexistant_apres_expiration` | Le jeton expiré est invalidé (un nouveau jeton est proposé, différent) |
| `test_jeton_consomme_meme_si_execution_echoue` | Après consommation, le même jeton ne peut pas être ré-employé |

Horloge : classe `_FakeClock` injectable via le paramètre `clock` de `ToolEngine` (aucune attente réelle).

### 3.2 `TestRecursivePolicyValidation` (8 tests)

| Test | Objet |
|------|-------|
| `test_cle_shell_dans_dict_imbrique` | `{"options": {"shell": ...}}` → refusé |
| `test_cle_code_dans_liste_imbriquee` | `{"options": [{"code": ...}]}` → refusé |
| `test_cle_code_dans_tuple_imbrique` | `{"options": ({"code": ...},)}` → refusé |
| `test_valeur_shell_en_majuscules_refusee` | Valeur `"SHELL"` → refusée (casse insensible) |
| `test_valeur_secret_en_majuscules_refusee` | Valeur `"PASSWORD"` → refusée |
| `test_cle_non_textuelle_ne_provoque_pas_erreur` | Clé entière → pas de `AttributeError` |
| `test_parametre_imbrique_valide_est_accepte` | Un texte sans motif interdit n'est pas refusé par la politique |
| `test_handler_non_appele_apres_refus_politique` | **Preuve directe** : le handler n'est jamais invoqué après un refus de politique (liste d'appels vide) |

### 3.3 `TestAuditConfidentiality` (3 tests)

| Test | Objet |
|------|-------|
| `test_audit_ne_contient_pas_la_fausse_cle` | Un handler qui lève `RuntimeError("... sk-FAUSSE-CLE-12345 password=hunter2")` : ni le message utilisateur ni l'audit ne contiennent la fausse clé, le mot de passe, ni le type d'exception |
| `test_audit_ne_contient_pas_de_parametres_bruts` | La valeur du paramètre n'apparaît pas dans l'audit ; `parameters_hash` est un SHA-256 de 64 caractères |
| `test_entree_audit_refus_politique_sans_secret` | Le refus de politique est journalisé avec `result == "refused"` et sans secret |

## 4. Commande et résultats réels

```
$ python -m unittest discover -s tests
Ran 161 tests in 20.081s
OK
```

| Mesure | Avant | Après |
|--------|-------|--------|
| Tests découverts | 146 | 161 |
| Réussis | 146 | 161 |
| Échecs | 0 | 0 |
| Erreurs | 0 | 0 |
| Tests ignorés | 0 | 0 |

**Environnement** : Windows, Python 3.12.10, `unittest` (bibliothèque standard).

Aucun appel réseau, aucune clé API, aucun effet externe, aucun fichier personnel touché : tous les tests utilisent une base SQLite en mémoire ou un répertoire temporaire supprimé en `tearDown`.

## 5. Tests non exécutés et raisons

| Test | Raison |
|------|--------|
| Validation complète sur Debian 13 | Environnement non disponible sur ce poste. **Responsabilité d'Agent B.** |
| Comportement des symlinks sous Linux (défaut S-005) | La création d'un symlink exige des privilèges administrateur sous Windows. Le test serait pertinent sous Debian 13 ; non ajouté ici pour ne pas produire un test conditional non exécuté. |
| Test réel de fournisseur IA (distant ou local) | Aucun endpoint configuré, aucune clé API. Aucun appel possible ni autorisé. |
| Test de fuite de descripteurs (défaut S-006) | Exigerait une mesure du nombre de handles sur une longue série d'appels ; le défaut est documenté dans l'audit S-006 plutôt que codé dans un test (un test passant validerait un défaut). |

## 6. Limites de l'environnement de test

- **Windows** : `multiprocessing` utilise le mode `spawn`. Les handlers de test doivent être des fonctions de niveau module (pas de closure), ce qui est le cas ici. Le comportement sous Linux (`fork`) diffère sur ce point : les closures y seraient acceptées. **Non validé sous Linux** — à confirmer par Agent B.
- La détection du nombre de tests (`161`) est dépendante de la découverte `unittest` ; le même code sous Debian 13 peut découvrir un nombre identique ou légèrement différent selon la version de Python.
- Aucun test ne dépend d'une resource clockante réelle (le test d'expiration existant dans `test_tool_engine.py` en dépend toujours).

## 7. Conclusion

Les 15 tests ajoutés couvrent les lacunes identifiées et **passent tous**. Ils n'apportent aucune modification au code applicatif : les correctifs L-007 à L-010 restent inchangés.

Ils ne valident **pas** la Phase 4 sur Debian 13 : cette responsabilité appartient à Agent B.
