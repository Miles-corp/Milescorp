# docs/reports/PHASE_4_FINDINGS_TRIAGE_AGENT_A.md — Triage des constats de sécurité S-001 à S-006 (Agent A)

## 1. Cadre de la vérification

| Élément | Valeur |
|---------|--------|
| Auteur | Agent A |
| Date | 2026-10-19 |
| Commit examiné | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` (correctifs L-007 à L-010) |
| Branche de travail | `work/agent-a-phase4-audit` (locale, **non publiée**) |
| Commit local | `632f27b` (5 ajouts : 4 rapports + 1 fichier de tests) |
| `origin/main` | `b5e1007` — **non modifiée** |
| Méthode | Analyse AST / `inspect` sur le code source, exécution de scénarios isolés sur `127.0.0.1` (port éphémère), aucun appel réseau externe |
| Hors périmètre | Validation Debian 13 (Agent B), appels réels à Groq, téléchargement de modèle |

### 1.1 Contrôles d'intégrité du dépôt (Étape 1)

| Contrôle | Résultat |
|----------|----------|
| Branche courante | `work/agent-a-phase4-audit` ✅ |
| HEAD | `632f27b` ✅ |
| Working tree | Propre (aucune modification non committée) ✅ |
| `git diff 4b6f515` (correctifs L-007 à L-010) | **Vide** → correctifs intacts ✅ |
| `origin/main` | `b5e1007` → inchangée ✅ |
| Contenu de `632f27b` | 5 ajouts (`A`), **aucune modification** de fichier existant ✅ |
| Rapport Agent B `PHASE_4_REVIEW_AGENT_B.md` | Non modifié par Agent A (`git diff` vide) ✅ |
| Branche `review/agent-b-phase4-review` (commit `928410c`) | Intacte ✅ |

### 1.2 Vérification des 15 tests supplémentaires (Étape 3)

| Contrôle | Résultat |
|----------|----------|
| Fichier `tests/test_tool_engine_security_extra.py` présent | ✅ |
| Nombre de fonctions `test_` | **15** ✅ |
| Correspondance avec les cas annoncés dans `PHASE_4_ADDITIONAL_TESTS_AGENT_A.md` | ✅ 4 expiration + 8 politique récursive + 3 confidentialité |
| Commande | `python -m unittest discover -s tests` |
| Résultat **reproductible** | `Ran 161 tests in 19.970s` → `OK` (0 échec, 0 erreur) |
| Effets externes | Aucun (SQLite temporaire, port éphémère local) ✅ |

> **Le décompte « 146 tests sous Debian 13 » provient du rapport d'Agent B** ; Agent A ne l'a pas exécuté et ne le revendique pas. Le seul chiffre vérifié par Agent A est **161 tests sous Windows (Python 3.12.10)**.

### 1.3 Point à actualiser

Si la validation Debian 13 est confirmée, `docs/reports/PHASE_4_RELEASE_CHECKLIST_AGENT_A.md` doit être mis à jour : la section 2 (résultats de tests) porte encore « ⏳ EN ATTENTE » pour Debian 13 et la condition bloquante n°8 doit être levée. **Cette mise à jour n'a pas été faite** (autorisation distincte requise, et dépend du rapport Agent B).

---

## 2. Tableau de triage

| ID | Constat | Gravité annoncée | Statut de vérification | Gravité confirmée | Bloquant production |
|----|---------|-------------------|-----------------------|-------------------|--------------------|
| S-001 | `PersistentMemoryError` référencé sans import dans `miles.py` | Moyenne | **Confirmé** (analyse AST) | Moyenne | **Oui** (dysfonctionnement) |
| S-002 | Aucune authentification sur `/memory`, `/forget`, `/remember`, `/message` | Moyenne / Haute si exposé | **Confirmé** | Moyenne (Haute hors loopback) | **Oui** si exposition réseau |
| S-003 | Divulgation d'exceptions brutes dans les réponses HTTP | Moyenne | **Confirmé** (reproduit) | Moyenne | **Oui** |
| S-004 | `Content-Length` non borné | Moyenne | **Confirmé** | Moyenne | Non (DoS local) |
| S-005 | Traversée de répertoires via symlink dans `list_files` | Moyenne | **Confirmé par analyse de code**, non reproduit sur ce poste | Moyenne → **Faible à Moyenne** | Non (contextuel) |
| S-006 | `multiprocessing.Queue` jamais fermée | Faible | **Confirmé** | Faible | Non |

---

## 3. Examen détaillé

### S-001 — `PersistentMemoryError` référencé sans import dans `miles.py`

| | |
|---|---|
| **Fichier** | `miles.py`, import ligne 11, usage ligne 72 |
| **Statut** | **Confirmé** |
| **Gravité confirmée** | Moyenne |

**Preuve** (analyse AST de `miles.py`) :
```
symbols importes depuis app.memory.persistent : ['PersistentMemory']
PersistentMemoryError utilise dans le code : True
PersistentMemoryError importe : False
-> NameError au runtime si la branche except est atteinte : True
```

**Conditions d'exploitation / de dysfonctionnement** : la clause `except PersistentMemoryError` (ligne 72) n'est atteinte que si `PersistentMemory(...)` lève cette exception. Depuis la correction L-006, `_initialize` n'attire plus d'exception : le défaut est donc **latent** aujourd'hui. Il redevient actif si :
- une version future réintroduit un `raise PersistentMemoryError` dans `PersistentMemory.__init__` ;
- un sous-constructeur non couvert lève cette exception.

**Ré评估 de la gravité** : le scénario le plus réaliste n'est pas l'exploitation mais le **dysfonctionnement** : le programme affiche une trace `NameError` au lieu du message d'avertissement prévu, et le handler de `miles.py` (qui intercepte `Exception` pour la configuration) ne rattrape pas ce `NameError` — il se produit donc après la phase de configuration, au moment de la construction de la mémoire. L'utilisateur voit un crash. Gravité **Moyenne** (fiabilité), pas critique.

**Correction ciblée proposée** :
```python
from app.memory.persistent import PersistentMemory, PersistentMemoryError
```
ou, plus robuste (élimine la dépendance à un nom de classe) :
```python
except Exception:  # noqa: BLE001 — la mémoire reste optionnelle
    print("Avertissement : mémoire persistante non disponible.", file=sys.stderr)
```

**Tests de régression nécessaires** :
1. `test_miles_importe_persistent_memory_error` : vérifier par AST ou `import miles` que le nom est résolvable (détecte le `NameError` latent sans déclencher d'erreur).
2. `test_miles_demarre_avec_memoire_indisponible` : monkeypatcher `PersistentMemory` pour lever une exception et vérifier que `miles.main()` retourne un code de sortie propre (0) et n'émet pas de `NameError`.

---

### S-002 — Absence d'authentification sur les routes web

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, routage lignes 172-196, handlers 335-378 |
| **Statut** | **Confirmé** |
| **Gravité confirmée** | Moyenne en loopback, **Haute** si le serveur écoute hors `127.0.0.1` |

**Preuve** (analyse de `app/interface/web.py`) :
```
do_GET  -> ['if path == "/":', 'elif path == "/status":', 'elif path == "/memory":']
do_POST -> ['if path == "/message":', 'elif path == "/remember":', 'elif path == "/forget":']

'Authorization' : False | 'auth_token' : False | 'session' : False
'Origin' : False | 'Referer' : False | 'csrf' : False | 'X-Api-Key' : False
-> aucune route n est protegee : True

_handle_forget exige un controle d acces : False
_handle_remember exige un controle d acces : False
_handle_list_memories exige un controle d acces : False
```

**Conditions d'exploitation** : toute application exécutée sur le poste de l'utilisateur (navigateur, extension, script local) peut, sans aucune authentification :
- lire l'intégralité des souvenirs personnels via `GET /memory` ;
- en supprimer un via `POST /forget` ;
- écrire un souvenir via `POST /remember` ;
- **déclencher un appel au fournisseur IA** via `POST /message`, donc une dépense.

**Facteur atténuant important** : `MilesWebServer.__init__` utilise `host="127.0.0.1"` par défaut, ce qui **restreint l'accès aux seuls processus de la machine**. L'exposition au réseau local n'est possible que si l'utilisateur passe explicitement une autre adresse — non fait aujourd'hui, mais rien ne l'interdit ni ne l'avertit.

**Correction ciblée proposée** :
- Générer un jeton aléatoire à la startup (`secrets.token_urlsafe(32)`), le transmettre via la variable d'environnement `MILES_WEB_TOKEN` ou en argument `--web-token`, et le stocker dans une variable d'instance du handler (et non en attribut de classe).
- Comparer le jeton reçu (en-tête `Authorization: Bearer` ou paramètre) avec `hmac.compare_digest`.
- Refuser toute requête sans jeton valide sur `/memory`, `/remember`, `/forget`, `/message`.
- Refuser de démarrer si `host` n'est pas une adresse de loopback **et** qu'aucun jeton n'est fourni.
- Réserver `/` et `/status` à un usage non sensible, ou les protéger également pour ne rien divulguer.

**Tests de régression nécessaires** :
1. `test_route_sans_jeton_refusee` : `GET /memory` sans jeton → 401/403.
2. `test_route_avec_mauvais_jeton_refusee` : jeton erroné → 401/403.
3. `test_route_avec_jeton_valide_acceptee` : jeton correct → 200.
4. `test_jeton_compare_en_temps_constant` : vérification statique de l'usage de `hmac.compare_digest` (ou assertion de non-régression).
5. `test_refus_demarrage_hors_loopback_sans_jeton` : `MilesWebServer(host="0.0.0.0")` sans jeton → refus.
> Ces tests doivent rester sur `127.0.0.1` avec un port éphémère : **ne pas exposer de service sur le réseau**.

---

### S-003 — Divulgation d'exceptions brutes dans les réponses HTTP

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 82, 88 (`send_message`), 125 (`add_memory`), 133 (`delete_memory`) ; aggravant `app/ai_providers/remote.py` lignes 73-76 et 79-82 |
| **Statut** | **Confirmé — reproduit** |
| **Gravité confirmée** | Moyenne |

**Preuve (reproduction locale, serveur sur `127.0.0.1` port éphémère)** :
```
POST /message  ->  HTTP 400
corps : {"error": "Erreur du fournisseur IA : Erreur HTTP 401 du fournisseur distant: sk-FAUSSE-CLE-XYZ", ...}
-> la fausse cle du fournisseur apparait dans la reponse : True
```

**Conditions d'exploitation** : il suffit qu'un appel au fournisseur IA échoue (clé invalide → 401, quota dépassé → 429, modèle inexistant → 404) pour que le corps de réponse HTTP du fournisseur — tronqué à 200 caractères mais **non filtré** — soit renvoyé au navigateur. Le corps peut contenir :
- un extrait de la clé d'authentification renvoyée par le fournisseur dans son message d'erreur ;
- un identifiant de requête ou d'organisation ;
- des détails de configuration du compte.

De plus, `add_memory` et `delete_memory` renvoient `str(exc)` : une exception SQLite ou une `PersistentMemoryError` partent directement au client.

**Correction ciblée proposée** :
- Dans `WebApp.send_message` : remplacer `f"Erreur du fournisseur IA : {exc}"` et `f"Erreur inattendue : {exc}"` par des messages génériques, en journalisant le détail technique uniquement dans les journaux locaux.
- Dans `WebApp.add_memory` / `delete_memory` : remplacer `str(exc)` par un message générique.
- Ne jamais propager le corps brut de la réponse du fournisseur vers le client.

**Tests de régression nécessaires** :
1. `test_erreur_fournisseur_sans_fuite_de_secret` : fournisseur levant une exception contenant une fausse clé → la réponse HTTP ne contient ni la clé ni le type d'exception.
2. `test_erreur_memoire_sans_fuite_interne` : exception mémoire → réponse générique.
3. `test_reponse_contient_la_cause_en_journal_local` : le détail reste disponible côté journalisation (via `unittest.mock` sur le logger).

---

### S-004 — `Content-Length` non borné

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 159-165 (`_read_body`) |
| **Statut** | **Confirmé** |
| **Gravité confirmée** | Moyenne |

**Preuve** :
```python
def _read_body(self) -> dict[str, Any]:
    length = int(self.headers.get("Content-Length", 0))
    raw = self.rfile.read(length) if length > 0 else b""
```
```
-> aucun plafond de taille : True
-> lecture integrale en memoire : True
```

**Conditions d'exploitation** : un client local annonce un `Content-Length` important (par exemple 2 Go) ; `rfile.read(length)` tente d'allouer cette quantité. Effets : `MemoryError` dans le thread de traitement (le serveur `ThreadingHTTPServer` le contient, la connexion est fermée), ou dégradation des performances de la machine par pression mémoire. Requiert un client local (le serveur étant lié à `127.0.0.1`).

**Réévaluation de la gravité** : c'est un **déni de service local**, pas une divulgation ni une prise de contrôle. La robustesse du processus est affectée mais l'intégrité des données ne l'est pas. Gravité **Moyenne** en tant que disponibilité, **sans** risque de sécurité classique. La même correction doit traiter le `Content-Length` absent ou invalide (une valeur non numérique lève `ValueError` non capturée → 500).

**Correction ciblée proposée** :
```python
MAX_BODY_BYTES = 64 * 1024  # à fixer

length_raw = self.headers.get("Content-Length", "0")
try:
    length = int(length_raw)
except ValueError:
    self._send_json(400, {"error": "Content-Length invalide."})
    return
if length < 0 or length > MAX_BODY_BYTES:
    self._send_json(413, {"error": "Corps de requête trop volumineux."})
    return
```

**Tests de régression nécessaires** :
1. `test_content_length_negatif_refuse` → 400.
2. `test_content_length_non_numerique_refuse` → 400 (et non 500).
3. `test_content_length_au_dessus_du_plafond_refuse` → 413.
4. `test_corps_valide_accepte` → 200.

---

### S-005 — Traversée de répertoires via lien symbolique dans `list_files`

| | |
|---|---|
| **Fichier** | `app/security/validator.py`, lignes 83-89 (`_action_list_files`) |
| **Statut** | **Confirmé par analyse de code — non reproduit sur ce poste** (création de symlink exigeant des privilèges administrateur sous Windows) |
| **Gravité confirmée** | **Faible à Moyenne** (réévaluée) |

**Preuve** :
```
--- GARDE UTILISEE ---
    target = os.path.abspath(path)
    cwd = os.path.abspath(os.getcwd())
    if not target.startswith(cwd + os.sep) and target != cwd:
abspath utilise dans la garde : True
realpath utilise dans la garde : False
```
`os.path.abspath` est une normalisation **lexicale** : il résout `..` mais **ne résout pas les liens symboliques**. `os.path.realpath` le fait.

**Réévaluation importante — la garde est globalement efficace** (vérifié par exécution) :
```
list_files(chemin absolu externe) -> 'Accès refusé : ...'
-> chemin absolu correctement refuse : True
list_files('../outside')          -> 'Accès refusé : ...'
-> traversee .. correctement refusee : True
```
La seule voie restante est un **symlink placé dans le répertoire de travail** pointant vers un répertoire externe.

**Conditions d'exploitation** : l'attaquant doit pouvoir créer un symlink dans le répertoire de travail de MILES (donc disposer d'un accès en écriture à ce répertoire) **et** connaître ou cibler un répertoire dont il veut la liste. Cela suppose déjà un accès local en écriture, ce qui constitue une barrière d'arbitrage élevée. Le résultat est une **divulgation de noms de fichiers** (pas de contenu), dans le périmètre du compte exécutant.

**Gravité réévaluée : Faible à Moyenne** — l/constants de compromission sont significativement plus élevées que pour S-002/S-003 ; l'impact est limité à la liste de noms d'un répertoire. Je maintiens le constat, en abaissant la criticité.

**Note de reproductibilité** : la création de symlink sous Windows exige des privilèges administrateur (`OSError` constaté). Sous Debian 13 (Agent B), le symlink est trivial à créer : la reproduction est **possible et recommandée** dans l'environnement de l'agent B.

**Correction ciblée proposée** :
```python
target = os.path.realpath(path)
cwd = os.path.realpath(os.getcwd())
if not (target == cwd or target.startswith(cwd + os.sep)):
    return "Accès refusé : ..."
```

**Tests de régression nécessaires** :
1. `test_list_files_refuse_symlink_exterieur` (sous Linux/Debian) : créer un symlink vers un répertoire externe, vérifier le refus.
2. `test_list_files_refuse_chemin_absolu_externe` : déjà couvert fonctionnellement, à formaliser en test.
3. `test_list_files_refuse_traversee_parent` : déjà couvert fonctionnellement, à formaliser en test.
4. `test_list_files_accepte_repertoire_courant` : non-régression.

---

### S-006 — `multiprocessing.Queue` jamais fermée

| | |
|---|---|
| **Fichier** | `app/tools/engine.py`, lignes 367-368 (création), 394-412 (lecture) |
| **Statut** | **Confirmé** |
| **Gravité confirmée** | Faible |

**Preuve** :
```
creation de 2 Queue : 2
appel a .close() : False
appel a join_thread() : False
-> aucune fermeture : True
-> try/finally sur les files : False
```

**Conditions de dysfonctionnement** : chaque appel d'outil fuit 2 files. Sous Windows, chaque `multiprocessing.Queue` conserve un handle de tube nommé et un thread de arrière-plan ; sous Unix, des descripteurs de pipe. L'accumulation est progressive et n'affecte le fonctionnement qu'après un très grand nombre d'appels (centaines à milliers).

**Correction ciblée proposée** :
```python
result_queue = multiprocessing.Queue()
error_queue = multiprocessing.Queue()
try:
    process = multiprocessing.Process(...)
    process.start()
    process.join(timeout=...)
    ...
finally:
    result_queue.close()
    result_queue.join_thread()
    error_queue.close()
    error_queue.join_thread()
```
Il faut également faire attention à ne pas lire une queue après `close()` : la lecture doit avoir lieu avant le `finally`.

**Tests de régression nécessaires** :
1. `test_queues_fermees_apres_execution` : après un appel d'outil, vérifier que les files ne sont pas ouvertes (par exemple via un compteur de handles ou un attribut interne de test).
2. Alternative plus simple et portable : `test_pas_de_fuite_de_descripteurs` : mesurer la variation du nombre de descripteurs ouverts avant/après N appels (sous Linux : `/proc/self/fd`). Sous Windows, l'équivalent est le nombre de handles du processus.
> Un test de ce type est **dépendant de la plateforme** ; Agent B peut l'exécuter sous Debian 13.

---

## 4. Synthèse et décision de mise en production

### 4.1 Constats bloquants recommandés

| ID | Pourquoi bloquant | Gravité |
|----|-------------------|---------|
| **S-001** | Dysfonctionnement garanti si la branche d'erreur de la mémoire est atteinte : `NameError` au lieu d'un avertissement. Correction d'une ligne, risque de régression nul. | Moyenne |
| **S-003** | Divulgation **reproduite** de fragments de réponse du fournisseur (clé d'authentification potentielle) vers le navigateur. Même logique que la correction L-010 déjà appliquée au moteur d'outils : l'incohérence entre le moteur (`app/tools/`) et l'interface web (`app/interface/web.py`) est en soi un défaut d'homogénéité. | Moyenne |
| **S-002** | Aucune authentification sur des routes qui lisent, suppriment des données personnelles et **déclenchent des dépenses**. Le serveur est lié à `127.0.0.1` par défaut, ce qui réduit fortement l'exposition : le constat est bloquant **à partir du moment où l'on envisage une exposition réseau** (boîtier physique accessible depuis un autre appareil du réseau local), ce qui est la direction annoncée du projet. | Moyenne → Haute selon l'usage |

### 4.2 Constats pouvant être suivis séparément

| ID | Justification du suivi séparé |
|----|------------------------------|
| **S-004** | Déni de service **local** uniquement, sans impact sur la confidentialité ni l'intégrité. La correction est triviale mais peut être groupée avec une amélioration plus large du serveur web (timeouts, limites de threads, S-009). |
| **S-005** | Constat réel mais barrière d'arbitrage élevée (accès en écriture au répertoire de travail), impact limité à la liste de noms de fichiers. La correction d'une ligne (`realpath`) est à faire, mais elle n'a pas à bloquer la fusion si le mode local `list_files` n'est pas exposé à des entrées non fiables. |
| **S-006** | Fuite de ressources lente, sans impact fonctionnel à court terme. À traiter dans une passe de fiabilisation. |

### 4.3 Recommandation d'ensemble

**Ne pas fusionner `4b6f515` vers `main` avant d'avoir traité S-001 et S-003**, qui sont des corrections courtes, sans risque de régression, et qui restaurent l'homogénéité de la politique de confidentialité entre le moteur d'outils et l'interface web.

**S-002 doit être traité avant toute exposition réseau** (boîtier accessible depuis le LAN). Si le boîtier reste strictement en loopback, une correction intermédiaire (avertissement explicite au démarrage + jeton local) est acceptable en attendant une solution d'authentification plus complète.

S-004, S-005 et S-006 peuvent être suivis dans une tâche distincte, en documentant la limite.

### 4.4 État de la validation globale

| Élément | Statut |
|---------|--------|
| Correctifs L-007 à L-010 | ✅ Vérifiés sur Windows (161 tests) |
| Tests Debian 13 | ✅ **Confirmés par le rapport d'Agent B** (146 tests) — non exécutés par Agent A |
| Constats S-001, S-003 | ❌ Ouverts, correction recommandée avant fusion |
| Constats S-002, S-004, S-005, S-006 | ⚠️ Ouverts, suivi possible séparément (S-002 bloquant avant exposition réseau) |
| Checklist Agent A | ⏳ **À actualiser** si la validation Debian est confirmée |

**La Phase 4 n'est pas déclarée validée globalement par ce document** : la décision de fusion appartient au propriétaire du projet, après arbitrage des constats ci-dessus.

---

## 5. Modifications apportées par cette mission de triage

| Fichier | Action |
|---------|--------|
| `docs/reports/PHASE_4_FINDINGS_TRIAGE_AGENT_A.md` | Créé (ce document) |

**Aucun fichier applicatif n'a été modifié.** Les correctifs L-007 à L-010 (`4b6f515`), `main` (`b5e1007`) et le rapport d'Agent B sont intacts. Aucun commit n'a été poussé, aucune branche publiée, aucune Pull Request ouverte, aucune fusion effectuée.
