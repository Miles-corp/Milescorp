# docs/reports/PHASE_4_DEFS_AGENT_B_FIXES.md — Corrections des défauts D-B1 à D-B5 (Agent A)

Suite à l'audit indépendant d'Agent B du commit `be9f31753bca77fd3bdc5d11e3dfa896d7404610`.

## 1. Synthèse

| ID | Priorité Agent B | Statut initial | Statut final |
|----|-------------------|-----------------|--------------|
| D-B1 | Moyenne | Confirmé (reproduit) | **Corrigé** |
| D-B2 | Moyenne | Confirmé (affaiblissement réel) | **Corrigé** (assertions strictes restaurées) |
| D-B3 | Faible | Confirmé (`PRAGMA foreign_keys = 0`) | **Corrigé** |
| D-B4 | Faible | Confirmé (lecture de code) | **Corrigé** |
| D-B5 | Faible | Confirmé (lecture de code) | **Corrigé** |
| Risque `/clear` | À confirmer | Confirmé (comportement trompeur) | **Corrigé** |
| Risque `.env` non mappé | À confirmer | Confirmé | **Documenté** (choix assumé) |
| Risque chemin non autorisé | À confirmer | Confirmé (déjà correct) | **Documenté + testé** |
| Risque transactions SQLite | À confirmer | Confirmé | **Corrigé** (transactions explicites) |

**Aucun défaut n'a été écarté sans justification.** Les 5 défauts sont corrigés, les 4 risques sont examinés et documentés.

## 2. D-B1 — Identifiant de conversation inexistant

### Cause

`Conversation.attach_transcript()` conservait l'identifiant fourni sans vérifier son existence, puis `miles.py` affichait « une nouvelle conversation est créée » **sans la créer**. Les messages étaient écrits dans une conversation fantôme, invisible dans `--list-conversations`.

Reproduction (avant correction) :
```
conversation_id apres attach : identifiant-inexistant-1234
messages charges : 1
conversations visibles : 0
-> message invisible (0 conversation, 1 message orphelin) : True
```

### Correction

- `app/core/conversation.py` : `attach_transcript()` vérifie l'existence via
  `transcript.get_conversation()`. Si l'identifiant est inconnu, une **vraie**
  conversation est créée et son nouvel identifiant est utilisé. `attach_transcript()`
  retourne désormais un statut explicite : `"unavailable"`, `"created"`,
  `"restored"`, `"recreated"`.
- `miles.py` : message utilisateur explicite indiquant l'identifiant demandé,
  l'identifiant réellement attribué et le fait qu'une nouvelle conversation a
  été créée.
- `app/memory/transcript.py` : avec `PRAGMA foreign_keys = ON` (D-B3), un message
  ne peut plus être écrit dans une conversation inexistante.

### Test de non-régression

`tests/test_defects_agent_b.py::TestDB1UnknownConversationId` (7 tests) :
- l'identifiant inconnu n'est jamais conservé ;
- les messages restent visibles dans la liste des conversations ;
- les messages sont restaurables après réouverture ;
- base vide + identifiant inconnu → comportement cohérent ;
- conversation supprimée puis restaurée → nouvelle conversation ;
- le CLI signale explicitement l'identifiant inconnu et le nouvel identifiant.

## 3. D-B2 — Tests de sécurité HTTP

### Cause

Quatre assertions acceptaient le statut `0` (réinitialisation TCP) en plus du
statut HTTP attendu. Agent B a raison : une réinitialisation de connexion
n'est pas une réponse HTTP 413/400 valide, et l'affaiblissement n'était pas
documenté.

### Correction

Le serveur conserve son comportement : il refuse **avant de lire** le corps
(invariant de sécurité, `test_lecture_bornee_a_la_limite` inchangé). C'est le
**test** qui a été repris, comme le proposait Agent B :

- `tests/test_web_security.py` : `_raw_post()` accepte un nouveau paramètre
  `send_body`. Avec `send_body=False`, les **en-têtes seuls** sont envoyés
  (`Content-Length: 65537`, sans corps) : le serveur refuse avant toute
  lecture, il ne reste rien à écrire côté client, la connexion n'est pas
  réinitialisée et le statut HTTP attendu est reçu de façon déterministe.
- Les 4 assertions sont **strictes** : `assertEqual(result["status"], 413)`
  ou `400`, plus la vérification du corps.

Le paramètre `send_body=True` (défaut) reste utilisé par les autres tests ;
une réinitialisation TCP y renvoie `{"status": 0}` et n'est plus acceptée par
aucune assertion de sécurité.

### Test de non-régression

Les 4 tests existants (`test_limite_depassee_refusee_en_413`,
`test_longueur_extremement_grande_refusee_sans_lecture`,
`test_longueur_negative_refusee`, `test_longueur_non_numerique_refusee`) sont
maintenus avec des assertions strictes.

Mesure de déterminisme : **0 échec sur 8 exécutions** du module
`tests.test_web_security` (contre 3 échecs sur 15 avant la correction d'Agent A
précédente, dus à l'affaiblissement).

> Note : une correction côté serveur (drain borné du corps avant le 413) avait
> été tentée puis **abandonnée** : elle violait l'invariant de sécurité
> d'Agent B (`test_lecture_bornee_a_la_limite` : le handler ne lit jamais plus
> de `MAX_BODY_BYTES`). Le comportement serveur n'a **pas** été modifié pour
> faire passer les tests.

## 4. D-B3 — Clés étrangères SQLite

### Cause

`ON DELETE CASCADE` était décoratif : SQLite désactive les clés étrangères par
défaut. Vérifié : `PRAGMA foreign_keys` → `0`.

### Correction

- `app/memory/transcript.py` : `PRAGMA foreign_keys = ON` exécuté sur **chaque**
  connexion créée.
- `app/memory/transcript.py` : `save_message()` distingue désormais
  `sqlite3.IntegrityError` (violation de clé étrangère) des autres erreurs
  SQLite ; les deux cas annulent la transaction (`rollback`) et retournent
  `None` — aucune écriture partielle.

### Test de non-régression

`tests/test_defects_agent_b.py::TestDB3ForeignKeys` (5 tests) :
- le PRAGMA est actif ;
- un message rattaché à une conversation inexistante est **refusé** (aucun orphelin) ;
- la suppression d'une conversation supprime ses messages ;
- aucune donnée orpheline ne subsiste (vérification SQL directe) ;
- l'état est cohérent après réouverture de la base.

## 5. D-B4 — Fermeture de la mémoire

### Cause

`miles.py` fermait `transcript` mais jamais `memory` : la connexion SQLite de la
mémoire persistante restait ouverte à la sortie du programme.

### Correction

- `miles.py` : bloc `finally` — `memory.close()` **puis** `transcript.close()`.
  L'ordre estrespecté : la mémoire n'est plus utilisée à ce stade, et la
  fermeture de la mémoire précède celle du transcripteur.
- La fermeture a lieu dans tous les cas : sortie normale, `KeyboardInterrupt`,
  `EOFError` et exception.

### Test de non-régression

`tests/test_defects_agent_b.py::TestDB4MemoryClose` (3 tests) :
- fermeture après sortie normale ;
- fermeture après exception ;
- le transcripteur est lui aussi fermé.

> Conséquence : deux tests d'Agent B (`test_memoire_active_transmise_au_cli`,
> `test_activation_cree_la_base`) vérifiaient `memory.is_available` **après**
> `miles.main()`. Cette assertion porte désormais sur une ressource
> légitimement fermée : elle a été remplacée par la vérification de l'effet
> observable (création du fichier de base). Le comportement de production est
> inchangé.

## 6. D-B5 — Erreurs de persistance

### Cause

`Conversation._persist()` laissait remonter `TranscriptError` : la session
pouvait se terminer sur une anomalie de persistance, et rien n'indiquait à
l'utilisateur qu'un message n'avait pas été enregistré.

### Correction

- `app/core/conversation.py` : `_persist()` attrape `TranscriptError` et
  retourne `False` au lieu de lever. `add_user_message()` et
  `add_assistant_message()` retournent désormais `bool` (True si persisté ou
  si aucune persistance n'est active, False si l'écriture a échoué).
- `app/interface/cli.py` : si l'enregistrement de la réponse échoue, un
  avertissement explicite est affiché — le programme ne prétend jamais que le
  message a été enregistré.
- `app/memory/transcript.py` : journalisation interne (logger `miles.transcript`
  avec `NullHandler`) ; **aucun secret** n'est journalisé (seuls le nom de la
  classe d'exception et un message générique).

### Test de non-régression

`tests/test_defects_agent_b.py::TestDB5PersistenceErrors` (5 tests) :
- un rôle inconnu lève `TranscriptError` au niveau du transcripteur ;
- `_persist` rattrape l'erreur et retourne `False`, la session survit ;
- un échec d'écriture est signalé ;
- aucun message n'est prétendu enregistré s'il ne l'a pas été ;
- aucun secret n'est divulgué lors d'une erreur ;
- le CLI avertit quand la réponse n'a pas pu être enregistrée.

## 7. Risques supplémentaires examinés (étape 7)

| Risque | Résultat de l'examen | Traitement |
|--------|----------------------|------------|
| `/clear` ne purge pas la persistance (messages effacés qui réapparaissent) | **Confirmé** — comportement trompeur | **Corrigé** : `Conversation.clear()` supprime aussi les messages persistés (nouvelle méthode `ConversationTranscript.delete_messages()`). La conversation reste sélectionnable mais vide. Test : `test_clear_purge_la_persistance` (2 emplacements) |
| Variables `.env` non mappées (ex. `HTTP_PROXY`) | **Confirmé** — le `.env` n'est plus injecté dans `os.environ` | **Documenté et assumé** : conséquence directe de la correction d'herméticité (D-A3). Seules les variables `MILES_*` mappées sont prises en compte. Test : `test_variables_env_non_mappees_non_injectees` |
| `MILES_CONVERSATION_DB_PATH` hors racines autorisées | **Confirmé correct** — avertissement sur stderr, persistance désactivée, aucune base créée hors racines | **Documenté + testé** : `test_chemin_de_base_non_autorise_desactive_la_persistance` |
| Transactions SQLite | **Confirmé** — `isolation_level=''` (transactions implicites) | **Corrigé** : `isolation_level=None` (autocommit) + `BEGIN IMMEDIATE`/`COMMIT` explicites dans `save_message()` et `delete_conversation()`. Tests : `test_transactions_sqlite_explicites`, `test_rollback_en_cas_d_erreur_d_ecriture` |

## 8. Fichiers modifiés

| Fichier | Modification |
|---------|--------------|
| `app/memory/transcript.py` | `PRAGMA foreign_keys = ON` ; `isolation_level=None` ; transactions explicites ; `delete_messages()` ; gestion `IntegrityError` ; journalisation interne sans secret |
| `app/core/conversation.py` | `attach_transcript()` vérifie l'existence et retourne un statut ; `_persist()` attrape `TranscriptError` et retourne `bool` ; `add_*_message()` retournent `bool` ; `clear()` purge la persistance |
| `app/memory/__init__.py` | Exports **paresseux** (PEP 562) pour éviter le cycle d'import `app.core.conversation` ↔ `app.memory.transcript` |
| `app/interface/cli.py` | Avertissement si l'enregistrement échoue ; message de `/clear` conforme à la nouvelle sémantique |
| `miles.py` | Message explicite pour identifiant inconnu ; fermeture de `memory` dans le `finally` |
| `tests/test_web_security.py` | `send_body` ; 4 assertions strictes restaurées |
| `tests/test_miles_entrypoint.py` | Assertion adaptée au cycle de vie (ressource fermée après `main()`) |
| `tests/test_settings_memory_config.py` | Idem |
| `tests/test_conversation_persistence.py` | `test_clear_purge_la_persistance` (nouvelle sémantique) |
| `tests/test_defects_agent_b.py` | **Nouveau** — 26 tests de non-régression D-B1 à D-B5 + risques |

## 9. Tests exécutés — résultats réels

```
$ python -m unittest discover -s tests
Ran 302 tests in 40.986s
OK (skipped=4)
```

| Mesure | Avant (be9f317) | Après corrections |
|---------|------------------|------------------|
| Tests découverts | 276 | **302** |
| Réussis | 276 | **302** |
| Échecs / erreurs | 0 | **0** |
| Ignorés (voix, 4) | 4 | 4 |
| Instabilité (suite complète, 4 exécutions) | non mesurée | **0 échec** |
| Instabilité (module web, 8 exécutions) | — | **0 échec** |

Les 4 tests ignorés sont les tests de voix nécessitant `pyttsx3` et
`speech_recognition` (non installés).

## 10. Limites restantes

| Limite | Gravité | Statut |
|--------|---------|--------|
| Validation Debian 13 non effectuée | Moyenne | Responsabilité Agent B (les 4 tests ignorés portent la preuve Linux : symlinks S-005, descripteurs S-006) |
| Test d'inférence réel non effectué | Moyenne | En attente d'accord (coût API) |
| Fournisseur local hors ligne non implémenté | Moyenne | TASK-DEV-007 |
| Le 413 peut être perdu si le client écrit encore son corps | Faible | Comportement assumé (invariant de sécurité préservé) ; contourné dans les tests par l'envoi d'en-têtes seuls |
| Variables `.env` non mappées non appliquées au processus | Faible | Choix assumé et documenté (herméneuticité de la suite) |

## 11. Commande de reproduction

```bash
python -m unittest discover -s tests -v
python -m unittest tests.test_defects_agent_b -v
```

## 12. Demande de vérification à Agent B

1. Exécuter la suite complète (**302 tests**) sur **Debian 13** — notamment les
   4 tests ignorés (symlinks S-005, descripteurs S-006).
2. Vérifier la correction de **D-B1** : `--conversation <inconnu>` doit créer une
   vraie conversation, visible dans `--list-conversations`, et ses messages
   doivent être restaurables.
3. Vérifier que **D-B2** n'a pas réintroduit d'affaiblissement : les 4
   assertions de refus doivent rester strictes et l'invariant
   `test_lecture_bornee_a_la_limite` doit rester inchangé.
4. Vérifier **D-B3** : `PRAGMA foreign_keys` actif sur chaque connexion, et
   aucun orphelin possible.
5. Vérifier **D-B4** : la mémoire et le transcripteur sont fermés à la sortie,
   y compris en cas d'exception.
6. Vérifier **D-B5** : une erreur de persistance ne termine pas la session et
   l'utilisateur est informé.
7. Vérifier la nouvelle sémantique de `/clear` (purge aussi la persistance).

---

*Aucun appel API réel, aucun téléchargement de modèle, aucune dépense. Les
modifications sont committées sur la branche de travail V1 et publiées pour
revue ; `main` n'est pas modifié.*
