# docs/reports/MILES_V1_VERIFICATION_AGENT_B.md — Vérification indépendante MILES V1 (Agent B)

## 1. Périmètre et commit audité

| Élément | Valeur |
|---------|--------|
| Dépôt | `https://github.com/Miles-corp/Milescorp` |
| **Commit audité** | `be9f31753bca77fd3bdc5d11e3dfa896d7404610` (`feat: MILES V1 - persistance de conversation et branchement du fournisseur distant`) |
| Branche auditée | `origin/feature/miles-v1-conversation-persistence` |
| Branche locale d'audit | `audit/agent-b-v1-review` (créée depuis le commit audité, **non poussée**) |
| Base de la branche V1 | `e0886a7b926861788805cf69cfdca3ab0a408a30` (correctifs S-002/S-004/S-005/S-006 d'Agent B) |
| `origin/main` | `b5e100725efe3886a742d2eb13c2bd4bf185733f` — **ne contient pas** la V1 |
| Environnement de vérification | **Windows**, Python 3.14.7 (le seul accessible) |
| Vérification Debian 13 | **Non effectuée** — see §9 |

**Périmètre réel établi.** MILES V1 = persistance locale de l'historique de conversation (SQLite) + branchement du fournisseur distant dans le terminal + interface web existante. Le commit V1 modifie 33 fichiers (+5287/−136) et ajoute 48 tests.

## 2. Résumé — état global et niveau de confiance

| Domaine | État | Confiance |
|---------|-------|-----------|
| Scénario conversationnel de bout en bout | ✅ Fonctionnel, **reproduit par moi** | Élevée |
| Architecture des fournisseurs | ✅ Interface homogène, aucune duplication | Élevée |
| Persistance (sauvegarde, ordre, séparation, doublons) | ✅ Conforme | Élevée |
| Persistance — restauration d'un identifiant inexistant | ❌ **Perte silencieuse de données** | Élevée (reproduit) |
| Sécurité — secrets, chemins, serveur, entrées | ⚠️ 1 lot d'assertions affaibli | Élevée |
| Qualité des tests | ✅ 48 tests V1, couverture large | Élevée |
| Validation Debian 13 | ❌ **Absente** | Aucune |

**Niveau de confiance global : élevé sur Windows, nul sur Debian 13** (aucune preuve d'exécution de ma part sur cette plateforme).

## 3. Défauts confirmés

### D-B1 — Restauration d'une conversation inexistante : perte silencieuse de messages

| Champ | Contenu |
|---|---|
| **Priorité** | **Moyenne** (perte de données silencieuse) |
| **Fichier / emplacement** | `app/core/conversation.py:97-115` (`Conversation.restore`) et `app/core/conversation.py:76-95` (`attach_transcript`) ; symptomatique en `miles.py:156-166` |
| **Scénario de reproduction** | `python miles.py --conversation ID-INEXISTANT` puis saisir un message, puis `python miles.py --list-conversations` |
| **Comportement attendu** | L'identifiant inexistant est détecté, une nouvelle conversation est créée, les messages sont visibles et restaurables |
| **Comportement observé** | `stderr` affiche « Avertissement : conversation 'ID-QUI-EXISTE-PAS' introuvable, **une nouvelle conversation est créée**. » — **mais aucune conversation n'est créée**. `conversation_id` reste l'identifiant fantôme ; le message est écrit dans `transcript_messages` sous cet identifiant ; la table `conversations` reste vide ; `--list-conversations` affiche « Aucune conversation enregistrée ». |
| **Preuve disponible** | Exécution réelle, deux niveaux :<br>• API : `conversation_id=ID-INEXISTANT-1234`, `is_persistent=True`, `count_messages=2`, `list_conversations()=0`<br>• CLI : `conversations visibles : 0`, `messages ecrits : 1` → `('ID-QUI-EXISTE-PAS','user','mon message important')` |
| **Correction recommandée** | Dans `Conversation.attach_transcript`, lorsque `conversation_id` est fourni mais `restore()` renvoie 0 et que la conversation n'existe pas : créer réellement une nouvelle conversation (`self.conversation_id = transcript.create_conversation()`) au lieu de conserver l'identifiant fantôme. À défaut, propager l'échec pour que `miles.py` appelle `attach_transcript(transcript)` (nouvelle conversation). |
| **Test de non-régression requis** | `test_conversation_inexistante_cree_nouvelle_conversation` : après `attach_transcript(t, "INEXISTANT")`, vérifier que `conversation_id != "INEXISTANT"`, que `list_conversations()` contient cette conversation, et que les messages écrits afterwards y figurent. Test d'intégration CLI de l'option `--conversation` avec un identifiant inconnu. |

### D-B2 — 4 assertions de sécurité affaiblies, sans mention dans le rapport

| Champ | Contenu |
|---|---|
| **Priorité** | **Moyenne** (masquage d'une régression potentielle) |
| **Fichier / emplacement** | `tests/test_web_security.py` — `test_limite_depassee_refusee_en_413`, `test_longueur_extremement_grande_refusee_sans_lecture`, `test_longueur_negative_refusee`, `test_longueur_non_numerique_refusee` |
| **Scénario de reproduction** | `git diff e0886a7..be9f317 -- tests/test_web_security.py` |
| **Comportement attendu** | Le refus par 413 (corps trop volumineux) et 400 (en-tête invalide) est vérifié de façon déterministe |
| **Comportement observé** | `assertEqual(status, 413)` et `assertEqual(status, 400)` ont été remplacés par `_assert_refused()`, qui **accepte aussi le statut 0** (réinitialisation TCP). La vérification du message public (« volumineuse », « Content-Length ») n'est plus effectuée que conditionnellement (`if status == 413`). Un serveur qui fermerait la connexion sans vérifier quoi que ce soit passerait ces 4 tests. |
| **Preuve disponible** | Diff `e0886a7..be9f317` (lecture directe). Le rapport `MILES_V1_DEVELOPMENT.md` §7 D-A1 ne mentionne que `test_lecture_bornee_a_la_limite` comme « inchangé » — il ne signale pas l'affaiblissement des 4 autres assertions. |
| **Correction recommandée** | Rendre le test **déterministe** : émettre uniquement les en-têtes (`Content-Length: 65537`) **sans corps**. Le serveur refuse avant toute lecture → il n'a aucun corps en attente dans la socket → la fermeture ne provoque pas de RST → le 413 est reçu systématiquement. On peut alors réaffirmer `assertEqual(result["status"], 413)` et `assertIn("volumineuse", body)`. |
| **Test de non-régression requis** | Le test restauré dans sa forme stricte constitue lui-même la non-régression. À conserver tel quel. |

### D-B3 — Clauses étrangères non appliquées (PRAGMA absent)

| Champ | Contenu |
|---|---|
| **Priorité** | **Faible** |
| **Fichier / emplacement** | `app/memory/transcript.py:101-114` (schéma `FOREIGN KEY … ON DELETE CASCADE`) |
| **Scénario de reproduction** | `grep -n "PRAGMA" app/memory/transcript.py app/memory/persistent.py` → aucune occurrence |
| **Comportement attendu** | La contrainte `ON DELETE CASCADE` est appliquée par SQLite |
| **Comportement observé** | SQLite **désactive les clés étrangères par défaut** ; sans `PRAGMA foreign_keys = ON`, la contrainte est purement décorative. Le chemin principal reste correct car `delete_conversation` supprime explicitement les messages. |
| **Preuve disponible** | Absence de `PRAGMA` dans les deux modules de persistance (lecture du code) |
| **Correction recommandée** | Ajouter `self._conn.execute("PRAGMA foreign_keys = ON")` juste après `sqlite3.connect(...)` dans `_initialize()`. |
| **Test de non-régression requis** | Insérer un message avec un `conversation_id` inexistant → doit lever `sqlite3.IntegrityError` (et non créer un orphelin). |

### D-B4 — La connexion de la mémoire de souvenirs n'est jamais fermée

| Champ | Contenu |
|---|---|
| **Priorité** | **Faible** |
| **Fichier / emplacement** | `miles.py:195-197` (bloc `finally`) |
| **Scénario de reproduction** | Lecture du code : `transcript.close()` est appelé, `memory.close()` ne l'est pas |
| **Comportement attendu** | Les deux ressources SQLite sont fermées en fin d'exécution |
| **Comportement observé** | La connexion `PersistentMemory` reste ouverte jusqu'à la fin du processus (le système d'exploitation la ferme), asymétrie avec le transcripteur |
| **Preuve disponible** | Lecture du code |
| **Correction recommandée** | Dans le `finally` de `miles.py`, appeler `memory.close()` sous condition de non-nullité. |
| **Test de non-régression requis** | Vérifier qu'après `main()`, `memory` n'est plus `is_available` (connexion fermée). |

### D-B5 — `TranscriptError` non rattrapée lors de la persistance

| Champ | Contenu |
|---|---|
| **Priorité** | **Faible** (chemin latent) |
| **Fichier / emplacement** | `app/core/conversation.py:138-144` (`_persist`) → `app/memory/transcript.py:268-271` (`save_message` lève `TranscriptError`) |
| **Scénario de reproduction** | Lecture de code : `_persist` n'attrape pas `TranscriptError` |
| **Comportement attendu** | Un rôle invalide ne doit pas interrompre la session |
| **Comportement observable** | Aujourd'hui inatteignable (les rôles sont codés en dur : « user » / « assistant »), mais toute évolution ajoutant un rôle non enregistré ferait remonter l'exception jusqu'à la CLI |
| **Correction recommandée** | Attraper `TranscriptError` dans `_persist` et ne pas persister le message (dégradation gracieuse, cohérente avec le reste). |
| **Test de non-régression requis** | Forcer un rôle invalide via un double de test et vérifier que la session continue. |

## 4. Risques à confirmer (hypothèses, non démontrés)

| # | Risque | Ce qui est établi | Ce qui reste à confirmer |
|---|--------|-------------------|---------------------------|
| R1 | Le 413 n'est pas livré de façon fiable au client (reset TCP si le client écrit encore son corps) | Le comportement est réel (observé par Agent A, confirmé par le diff) | Contrat API attendu : un 413 fiable ou un refus suffit ? |
| R2 | `/clear` efface l'historique en mémoire mais pas le persisté : après redémarrage, les messages effacés réapparaissent | Choix explicite, documenté dans le code et testé (`test_clear_ne_supprime_pas_la_persistance`) | Acceptable pour l'utilisateur ? Risque de confusion élevé |
| R3 | Le `.env` n'est plus injecté dans `os.environ` | Seules les clés de `env_mapping` sont lues depuis le fichier | Les variables **non mappées** (ex. `HTTP_PROXY`) ne sont plus appliquées au processus : impact sur les utilisateurs derrière un proxy |
| R4 | `MILES_CONVERSATION_DB_PATH` hors racines autorisées → persistance désactivée | Vérifié par moi (1re exécution E2E : avertissement sur stderr, aucune persistance) | Le message d'avertissement est-il sufficiently explicite pour l'utilisateur final ? |
| R5 | `BEGIN IMMEDIATE` explicite alors que `sqlite3` en mode legacy démarre implicitement les transactions | `OperationalError` → message perdu silencieusement (`return None`) | Le cas « transaction déjà ouverte » est-il atteignable en production ? |
| R6 | `timeout = 30 s` + 64 KiB : un client local peut saturer les threads du serveur | `ThreadingHTTPServer` sans limite de concurrence | Un limite de threads serait-elle pertinente pour un usage local ? |
| R7 | Validation Debian 13 | Aucune preuve de ma part | Les 4 tests ignorés (3 liens symboliques + 1 fuite de descripteurs) doivent passer sous Debian 13 |

## 5. Couverture des exigences

| # | Exigence | État | Preuve |
|---|----------|------|--------|
| 1 | Démarrage depuis le terminal | ✅ | `python miles.py` → bannière, invite `> `, code de sortie 0 |
| 2 | Acceptation des messages utilisateur | ✅ | 3 messages saisis, 3 appels HTTP reçus par le serveur simulé |
| 3 | Appel réel du fournisseur configuré | ✅ | `RemoteProvider` → 3 requêtes `POST /v1/chat/completions` reçues ; réponses **non simulées** dans le code (extraction réelle de `choices[0].message.content`) |
| 4 | Affichage de la réponse reçue | ✅ | `REPONSE_REELLE: Bonjour` etc. affichés en sortie standard |
| 5 | Conversation à plusieurs échanges | ✅ | Contexte transmis : `['user','assistant','user']` au 2ᵉ appel |
| 6 | Maintien du contexte | ✅ | Après redémarrage : `['user','assistant','user','assistant','user']` |
| 7 | Changement de fournisseur | ✅ | `--provider remote\|local` explicite ; `test_changement_de_fournisseur` |
| 8 | Erreurs utiles sans exposition sensible | ⚠️ | Messages publics génériques ✓ ; **mais** 4 assertions de code HTTP affaiblies (D-B2) |
| 9 | Fermeture propre | ✅ | `/quit` → « Au revoir ! », code 0 ; EOF et Ctrl+C gérés (tests dédiés) |
| 10 | Interface fournisseurs homogène | ✅ | `base.py` ABC `chat/is_available/name` ; `remote.py` et `local.py` signatures identiques |
| 11 | Normalisation des erreurs | ✅ | `AIProviderError` ; `public_provider_error()` pour le web |
| 12 | Configuration fournisseur et modèle | ✅ | `MILES_REMOTE_BASE_URL` / `MILES_REMOTE_MODEL` / `MILES_REMOTE_API_KEY` |
| 13 | Séparation des responsabilités | ✅ | `conversation.py` = contexte ; `transcript.py` = stockage pur (pas de duplication) |
| 14 | Fournisseur local ajoutable plus tard | ✅ | `LocalProvider` intact ; l'endpoint llama.cpp proposé est OpenAI-compatible (non vérifié hors périmètre) |
| 15 | Sauvegarde des messages | ✅ | `save_message` + `UNIQUE(conversation_id, sequence)` |
| 16 | Ordre des échanges | ✅ | `sequence` + `ORDER BY sequence ASC` ; `test_ordre_des_messages_preserve` |
| 17 | Restauration après redémarrage | ✅ **et** ❌ | ✅ vérifié par moi (4 messages restaurés) ; ❌ **cassée** si l'identifiant est inconnu (D-B1) |
| 18 | Reconstruction du contexte | ✅ | `get_context()` = historique restauré |
| 19 | Séparation des conversations | ✅ | `test_separation_des_conversations` ; chaque `conversation_id` distinct |
| 20 | Traitement des doublons | ✅ | `MAX(sequence)+1` sous `BEGIN IMMEDIATE` + `UNIQUE` ; `test_pas_de_doublon_de_sequence` |
| 21 | Erreurs d'accès à la base | ✅ | `sqlite3.Error` → dégradation gracieuse ; `test_base_corrompue…`, `test_base_inaccessible…` |
| 22 | Comportement après échec réseau | ✅ | `test_comportement_apres_echec_de_requete` |
| 23 | Absence de clés API en base / historique | ✅ | `sanitize_text()` avant écriture ; 3 tests dédiés (clé, mot de passe, jeton Bearer) |
| 24 | Secrets suivis par Git | ✅ | `git ls-files` : aucun `.env`, `.db`, `.key` ; `.gitignore` couvre `data/*.db` et `.env` |
| 25 | Journaux sans secret | ✅ | `test_aucun_secret_dans_les_logs` ; `log_message` désactivé côté web |
| 26 | Validation des entrées | ✅ | `VALID_ROLES`, validation des paramètres d'outils, corps HTTP borné |
| 27 | Chemins de fichiers autorisés | ✅ | `app/security/paths.py` : résolution canonique + racines projet/`data/` ; appliqué à `list_files` **et** aux deux bases SQLite |
| 28 | Serveur web et restrictions réseau | ✅ | `127.0.0.1` imposé, refus explicite de `0.0.0.0`/LAN/`::` |
| 29 | Délais et taille des entrées | ✅ | Corps ≤ 64 KiB (413 au-delà) ; `timeout = 30 s` sur le handler |
| 30 | Risques d'exécution de commandes | ✅ | `ActionValidator` : 3 actions en registre, politique appliquée, aucun shell |
| 31 | Tests couvrant réellement les risques | ⚠️ | 48 tests V1 + 228 antérieurs ; **4 assertions affaiblies** (D-B2) ; 4 tests ignorés sous Windows |
| 32 | Validation Debian 13 | ❌ | **Aucune preuve d'exécution de ma part** |

## 6. Vérification de la section « Traitement des constats » d'Agent A

| Constat d'Agent A | Vérification par Agent B | Résultat |
|---|---|---|
| S-002 / S-004 / S-005 / S-006 intégrés via la base `e0886a7` | Présents dans l'ancêtre de la branche | ✅ Confirmé |
| S-005 « utilisé pour la base de conversations » | `miles.py:83` `resolve_authorized_path(settings.conversation_db_path)` | ✅ Confirmé |
| Motifs de rédaction déplacés vers `app/utilities/redaction.py` | Comparaison ligne à ligne avec `web.py` (base `e0886a7`) | ✅ **Motifs rigoureusement identiques** — extraction pure, aucun affaiblissement |
| D-A1 (instabilité de `test_web_security`) | Cause identifiée : le serveur refuse sans lire → RST | ✅ Cause correcte ; **mais** le remède affine 4 assertions (D-B2) |
| D-A2 (herméneuticité de la suite) | `tests/__init__.py` redirige `MILES_ENV_FILE` | ✅ Confirmé |
| D-A3 (effet de bord global de `_load_env_file`) | `.env` lu dans un dictionnaire local | ✅ Confirmé — amélioration réelle, `os.environ` n'est plus modifié |

## 7. Points à signaler à Agent A

| Priorité | Constat | Fichier | Test de non-régression demandé |
|----------|---------|---------|-------------------------------|
| **Moyenne** | **D-B1** — restauration d'un identifiant inexistant : perte silencieuse de messages, message d'erreur mensonger | `app/core/conversation.py:76-115`, `miles.py:156-166` | `test_conversation_inexistante_cree_nouvelle_conversation` + test d'intégration de `--conversation` |
| **Moyenne** | **D-B2** — 4 assertions de code HTTP affaiblies (statut 0 accepté) sans mention dans le rapport | `tests/test_web_security.py` | Test strict restauré via l'envoi d'en-têtes seuls (sans corps) |
| Faible | **D-B3** — `PRAGMA foreign_keys` absent : contrainte `ON DELETE CASCADE` décorative | `app/memory/transcript.py:71` | Insertion avec `conversation_id` inexistant → `sqlite3.IntegrityError` |
| Faible | **D-B4** — connexion de la mémoire de souvenirs non fermée | `miles.py:195-197` | `memory.is_available` faux après `main()` |
| Faible | **D-B5** — `TranscriptError` non rattrapée dans `_persist` | `app/core/conversation.py:138-144` | Rôle invalide → la session continue |
| À arbitrer | R2 — `/clear` ne purge pas l'historique persisté | `app/core/conversation.py:161-167` | Décision de produit à trancher |

**Agent A reste responsable de l'implémentation.** Agent B n'a modifié aucun fichier de production, de test ou de rapport de la branche auditée.

## 8. Verdict

# VALIDÉ SOUS RÉSERVES

**Justification.** Le périmètre fonctionnel annoncé de MILES V1 est **réel et vérifié par moi** : le programme démarre, appelle un fournisseur HTTP réel, affiche les réponses reçues, maintient le contexte, persiste l'historique et le restaure après redémarrage. L'architecture est saine (interface fournisseurs homogène, aucune duplication du moteur conversationnel, secrets correctement expurgés avant écriture, chemins confinés, serveur strictement local). La suite de 276 tests passe sur Windows, et les trois défauts que j'avais signalés en Phase 4 (S-001, S-003, L-007→L-010) sont bien préservés.

**Réserves :**
1. **D-B1** — un défaut confirmé de perte silencieuse de données sur le chemin `--conversation <identifiant inconnu>`, avec un message d'erreur qui annonce une action non réalisée. À corriger avant mise en production.
2. **D-B2** — 4 assertions de sécurité ont été affaiblies sans être signalées dans le rapport ; la correction proposée (test déterministe par envoi d'en-têtes seuls) est réalisable et préserve l'invariant de sécurité.
3. **Absence de preuve Debian 13** — je n'ai accès qu'à Windows. Les 4 tests ignorés (3 liens symboliques, 1 fuite de descripteurs) portent la preuve spécifique à Linux et doivent être exécutés sur la VM Debian 13.
4. **D-B3 / D-B4 / D-B5** — trois défauts de faible gravité, à corriger en même temps que D-B1.

**Hors périmètre non évalué** (conformément à la consigne) : voix, actions autonomes, fournisseur local llama.cpp, appel réel Groq (coût), performance.

## 9. Preuves manquantes — Debian 13

| Preuve | Statut | Ce qu'il faut faire |
|--------|--------|---------------------|
| Version Python et installation des dépendances | Non vérifiée par moi | `python3 --version`, `pip list` sur la VM |
| Suite complète (276 tests) | Non exécutée par moi | `python3 -m unittest discover -s tests -v` |
| 3 tests de liens symboliques (S-005) | **Ignorés sous Windows** — doivent passer sous Debian 13 | Exécution sur la VM |
| 1 test de fuite de descripteurs (S-006) | **Ignoré sous Windows** — doit passer sous Debian 13 | Exécution sur la VM |
| Démarrage du programme, restauration après redémarrage | Non exécuté par moi | Lancer `miles.py` puis relancer |
| Instructions d'installation | Partiellement lues (`INSTALL.md`, `QUICKSTART.md` mis à jour) | Suivre la procédure depuis une VM vierge |
| Comportement réseau dégradé | Non testé hors Windows | Sur la VM, sans accès réseau |

## 10. Commande de reproduction de D-B1

```bash
# Sur une VM ou un poste de développement, dans le dépôt :
python miles.py --conversation ID-INEXISTANT
# saisir : mon message important
# puis :
python miles.py --list-conversations
# Constat : 0 conversation listée, alors que 1 message a été écrit sous
# l'identifiant 'ID-INEXISTANT' dans data/conversations.db (table
# transcript_messages, sans ligne correspondante dans conversations).
```

---

*Audit réalisé par Agent B le 2026-10-20. Commit audité : `be9f31753bca77fd3bdc5d11e3dfa896d7404610`. Environnement de vérification : Windows, Python 3.14.7. Aucun fichier de production, de test ou de rapport de la branche auditée n'a été modifié. Aucun commit, push, PR, merge, rebase ni suppression de branche.*
