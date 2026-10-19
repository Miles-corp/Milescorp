# docs/reports/PHASE_4_SUPPLEMENTARY_SECURITY_AUDIT_AGENT_A.md — Audit de sécurité complémentaire (Agent A)

## 1. Cadre de l'audit

| Élément | Valeur |
|---------|--------|
| Auditeur | Agent A |
| Date | 2026-10-19 |
| Base auditée | `4b6f5158bf72887c9ab4d04ce3f05e12ef71e76a` (branche `review/phase4-security-fixes`) |
| Branche de travail de l'audit | `work/agent-a-phase4-audit` (créée depuis `4b6f515`, non publiée) |
| Périmètre | Tout le dépôt, en lecture seule, hors défauts L-007 à L-010 déjà corrigés |
| Méthode | Lecture statique du code + exécution de scripts de vérification non destructifs (aucun appel réseau, aucun secret manipulé) |
| Hors périmètre | Validation Debian 13 (responsabilité Agent B), appels réels à Groq, téléchargement de modèle |

**Commandes de vérification exécutées** (toutes locales, sans effet externe) :
- `git status --short --branch`, `git fetch origin`, `git log`, `git cat-file -t <sha>`
- `Select-String` sur `miles.py`, `app/tools/engine.py` (recherche de motifs)
- Script `inspect` sur `app/interface/web.py` et `app/security/validator.py` (analyse de la source des méthodes)
- Lecture intégrale de `app/interface/web.py`, `app/security/validator.py`, `app/memory/persistent.py`, `app/ai_providers/remote.py`

---

## 2. Vulnérabilités démontrées

### S-001 — `NameError` latent dans le point d'entrée : `PersistentMemoryError` non importé

| | |
|---|---|
| **Fichier** | `miles.py`, ligne 72 (bloc `except`), import manquant ligne 11 |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Vulnérabilité démontrée (par inspection + vérification statique) |

**Description** : `miles.py` importe uniquement `PersistentMemory` (ligne 11) mais référence `PersistentMemoryError` dans la clause `except` (ligne 72). Si cette branche d'erreur est atteinte, Python lève `NameError: name 'PersistentMemoryError' is not defined`, ce qui **crashe le programme** au lieu de dégrader gracieusement (l'intention du code était un simple avertissement sur `stderr`).

**Preuve** :
```
$ Select-String -Path "miles.py" -Pattern "import|PersistentMemoryError"
  11: from app.memory.persistent import PersistentMemory
  72:         except PersistentMemoryError as exc:
```
Aucune ligne `from app.memory.persistent import PersistentMemoryError` n'existe.

**Conditions de reproduction** : la branche est atteinte si `PersistentMemory(...)` lève `PersistentMemoryError`. Depuis la correction L-006, `_initialize` n'attire plus d'exception ; la branche est donc **latente** aujourd'hui, mais redeviendra active si `PersistentMemory.__init__` retrouve un chemin levant (ou si une future version réintroduit un `raise`).

**Recommandation** : importer `PersistentMemoryError` dans `miles.py`, ou remplacer la clause par `except Exception` avec un message générique. Correction triviale, hors périmètre de cette mission (fichier `miles.py` non listé dans les correctifs L-007 à L-010 — à traiter par le propriétaire du fichier).

---

### S-002 — Interface web sans authentification sur des routes sensibles

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 172-196 (routage), 335-378 (handlers) |
| **Gravité estimée** | **Moyenne en local / Haute si exposé hors 127.0.0.1** |
| **Classification** | Vulnérabilité démontrée (par inspection + vérification) |

**Description** : aucune route de l'interface web n'est protégée. `GET /memory` liste l'intégralité des souvenirs persistants, `POST /forget` supprime un souvenir, `POST /remember` écrit en base, `POST /message` déclenche un appel au fournisseur IA (donc une **dépense**). Aucune notion de jeton, session ni contrôle d'origine.

**Preuve** (recherche dans la source complète de `web.py`) :
```
'Authorization' present : False
'Origin'        present : False
'Referer'       present : False
'session'       present : False
```

**Conditions de reproduction** : toute application locale (navigateur, extension, autre processus) peut interroger `http://127.0.0.1:8080/memory` et lire les données personnelles de l'utilisateur, ou `POST /forget` pour les supprimer. Le serveur est bien lié à `127.0.0.1` par défaut (`MilesWebServer.__init__`, `host="127.0.0.1"`), ce qui limite l'exposition au réseau local, mais pas aux processus locaux.

**Recommandation** : introduire un jeton d'accès local (généré à la startup, transmis par argument de ligne de commande ou variable d'environnement, vérifié par un comparateur à temps constant) sur toutes les routes mutantes (`/remember`, `/forget`, `/message`) et sur `/memory`. Envisager un refus d'écoute si `host` n'est pas une adresse de loopback sans jeton.

---

### S-003 — Divulgation d'exceptions brutes dans les réponses HTTP

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 82, 88, 125, 133 |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Vulnérabilité démontrée (par inspection + vérification) |

**Description** : les exceptions remontent telles quelles dans les réponses JSON destinées au navigateur.

**Preuve** :
```
WebApp.add_memory      -> ['return {"error": str(exc)}']
WebApp.delete_memory   -> ['return {"error": str(exc)}']
WebApp.send_message    -> ['"error": f"Erreur du fournisseur IA : {exc}",',
                           '"error": f"Erreur inattendue : {exc}",']
```

Aggravant : `app/ai_providers/remote.py` (lignes 73-76 et 79-82) place dans le message d'erreur le **corps de la réponse HTTP du fournisseur tronqué à 200 caractères**. Ce corps peut contenir des messages du fournisseur IA, un identifiant de requête, ou des extraits d'authentification. Il est ensuite renvoyé tel quel au navigateur via `/message`.

**Conditions de reproduction** : provoquer une erreur HTTP 4xx/5xx sur l'endpoint du fournisseur (clé invalide, quota dépassé, modèle inexistant) et lire la réponse JSON de `POST /message`.

**Recommandation** : remplacer les interpolations d'exception par des messages génériques côté web, comme cela a été fait pour le moteur d'outils (correction L-010). Le détail technique doit rester dans les journaux locaux, jamais dans la réponse HTTP.

---

### S-004 — Taille de corps de requête non bornée (déni de service local)

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 159-165 (`_read_body`) |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Vulnérabilité démontrée (par inspection + vérification) |

**Description** : `Content-Length` est lu puis passé tel quel à `rfile.read(length)`. Aucune limite supérieure. Un client local peut déclarer une taille arbitrairement grande, provoquant une allocation mémoire proportionnelle dans le processus serveur.

**Preuve** :
```
length = int(self.headers.get("Content-Length", 0))
raw = self.rfile.read(length) if length > 0 else b""
-> plafond MAX present : False
```

**Conditions de reproduction** : `curl -X POST http://127.0.0.1:8080/message -H "Content-Length: 2000000000" --data-binary @fichier` — ou un corps minimal avec un en-tête `Content-Length` surdimensionné.

**Recommandation** : plafonner `Content-Length` (par exemple 64 Ko) et renvoyer `413 Payload Too Large` au-delà. Vérifier également que le nombre de lignes lues correspond à l announcing.

---

### S-005 — Garde de traversée de répertoires par `abspath` au lieu de `realpath`

| | |
|---|---|
| **Fichier** | `app/security/validator.py`, lignes 83-89 (`_action_list_files`) |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Vulnérabilité démontrée (par inspection de code ; reproduction directe bloquée sous Windows par la création de symlink requérant des privilèges admin) |

**Description** : la protection contre la traversée de répertoires compare `os.path.abspath(path)` à `os.path.abspath(os.getcwd())`. `abspath` est une normalisation **purement lexicale** : il résout `..` mais **ne résout pas les liens symboliques**. Un lien symbolique placé dans le répertoire de travail et pointant vers un répertoire externe passe la garde, et `os.listdir` suit le lien.

**Preuve** :
```
--- GARDE UTILISEE ---
    target = os.path.abspath(path)
    cwd = os.path.abspath(os.getcwd())
    if not target.startswith(cwd + os.sep) and target != cwd:
realpath dispo : True
abspath utilise dans la garde : True
realpath utilise dans la garde : False
```

**Conditions de reproduction** (Linux/Debian 13) :
```bash
mkdir -p /tmp/cible && echo secret > /tmp/cible/secret.txt
cd /tmp/cwd && ln -s /tmp/cible lien
# depuis MILES : action list_files avec path="lien" → liste /tmp/cible
```

**Recommandation** : utiliser `os.path.realpath()` des deux côtés (`target` et `cwd`) avant la comparaison. Sous Windows, `realpath` résout également les junctions.

---

### S-006 — Fuite de descripteurs : `multiprocessing.Queue` jamais fermée

| | |
|---|---|
| **Fichier** | `app/tools/engine.py`, lignes 367-368 (création), 394-412 (lecture) |
| **Gravité estimée** | **Faible** |
| **Classification** | Vulnérabilité démontrée (par inspection) |

**Description** : chaque appel d'outil crée **deux** `multiprocessing.Queue`. Elles ne sont jamais fermées (`close()` / `join_thread()` absents). Sous Windows, chaque queue non fermée conserve des handles système et un thread de fondification ; sous Unix, des descripteurs de pipe restent ouverts.

**Preuve** :
```
367: result_queue: "multiprocessing.Queue[Any]" = multiprocessing.Queue()
368: error_queue: "multiprocessing.Queue[str]" = multiprocessing.Queue()
→ aucune occurrence de .close() dans engine.py
```

**Conditions de reproduction** : appeler un outil plusieurs milliers de fois et surveiller le nombre de handles ouverts du processus (Gestionnaire des tâches → onglet Détails) ou `len(os.listdir('/proc/self/fd'))` sous Linux.

**Recommandation** : encadrer l'usage des queues par un `try/finally` appelant `close()` puis `join_thread()` sur les deux files. Correctif local, sans impact fonctionnel.

---

### S-007 — Absence de verrou sur la conversation partagée entre threads du serveur web

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 66-98 (`WebApp.send_message`) |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Risque plausible (concurrence) |

**Description** : `MilesWebServer` utilise `ThreadingHTTPServer` (un thread par requête). `WebApp.conversation` est un objet `Conversation` unique partagé entre tous ces threads, sans verrou. `add_user_message()` (append) puis `get_context()` (lecture) ne sont pas atomiques : deux requêtes simultanées peuvent s'intercaler, produisant un contexte incohérent — par exemple le message d'un utilisateur présent dans le contexte transmis pour la réponse d'un autre.

**Preuve** :
```
verrou dans send_message : False
MilesWebServer utilise ThreadingHTTPServer : True
```

**Conditions de reproduction** : deux requêtes `POST /message` simultanées depuis deux onglets ; comparer le contexte réellement envoyé au fournisseur (non observable aujourd'hui sans instrumentation, d'où le classement « risque plausible »).

**Recommandation** : protéger `add_user_message` + `get_context` + `add_assistant_message` par un `threading.Lock` dans `WebApp`, ou donner à chaque requête/session sa propre conversation.

---

## 3. Risques plausibles (non reproduits, à confirmer)

### S-008 — CSRF sur les routes POST de l'interface web

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 184-196 et 159-165 |
| **Gravité estimée** | **Moyenne** |
| **Classification** | Risque plausible — non reproduit |

**Description** : les routes POST ne vérifient ni `Origin`, ni `Referer`, ni jeton. Le corps est lu et analysé en JSON **sans vérifier l'en-tête `Content-Type`**. Un site web tiers pourrait donc envoyer une requête inter-origine vers `http://127.0.0.1:8080/forget` et déclencher la suppression d'un souvenir, voire `POST /message` pour consommer des crédits API.

**Preuve** : l'absence de tout contrôle est établie par inspection (cf. S-002). La faisabilité pratique d'une requête `no-cors` avec `Content-Type: text/plain` n'a **pas** été testée dans cette mission.

**Recommandation** : vérifier l'en-tête `Content-Type: application/json` sur les routes POST, et ajouter un contrôle `Origin`/jeton. Ce point est lié à S-002 et sera résolu par la même correction.

### S-009 — Absence de limitation de threads et de timeout de connexion sur le serveur web

| | |
|---|---|
| **Fichier** | `app/interface/web.py`, lignes 381-399 (`MilesWebServer`) |
| **Gravité estimée** | **Faible à moyenne** |
| **Classification** | Risque plausible |

**Description** : `ThreadingHTTPServer` crée un thread par connexion sans limite. `BaseHTTPRequestHandler` n'a pas d'attribut `timeout` fixé, donc une connexion ouverte sans requête complète reste active. Un client local peut ouvrir de nombreuses connexions et épuiser les threads ou la mémoire.

**Recommandation** : fixer `timeout` sur la classe du handler, limiter le nombre de threads ou utiliser une pool, et documenter que le serveur est destiné au loopback.

---

## 4. Recommandations (améliorations, sans vulnérabilité caractérisée)

### S-010 — `Settings.as_dict()` expose les clés API

| | |
|---|---|
| **Fichier** | `app/config/settings.py`, lignes 158-160 |
| **Gravité** | Faible (recommandation) |

`as_dict()` retourne toutes les valeurs, **y compris** `remote_api_key` et `local_api_key`. La docstring l'indique (« ne pas journaliser »), mais rien ne l'empêche. Toute utilisation future de `as_dict()` dans un log ou une réponse HTTP divulguera les secrets.

**Recommandation** : retirer les clés de `as_dict()`, ou fournir un `as_public_dict()` sans secrets et conserver `as_dict()` comme usage interne explicite.

### S-011 — La politique rejette des sous-chaînes dans les valeurs : faux positifs

| | |
|---|---|
| **Fichier** | `app/tools/policy.py`, lignes 82-87, 100-105, 116-121 |
| **Gravité** | Faible (recommandation) |

La validation des valeurs recherche des sous-chaînes (`"token" in valeur`, `"code" in valeur`…). Un souvenir légitime comme « mon tokenizer de laboratory » ou « le code postal de ma rue » est refusé. Le filtre est conservateur (c'est acceptable côté sécurité) mais produira des refus frustrants, et un futur assouplissement serait risqué.

**Recommandation** : distinguer les clés (correspondance exacte, actuelle) des valeurs (motifs plus précis : `sk-[A-Za-z0-9]{20,}`, `-----BEGIN ... PRIVATE KEY-----`).

### S-012 — Le fichier `.env` est chargé depuis le répertoire courant

| | |
|---|---|
| **Fichier** | `app/config/settings.py`, lignes 120-122 |
| **Gravité** | Faible (recommandation) |

`MILES_ENV_FILE` ou `.env` est résolu relativement au répertoire courant. Lancer MILES depuis un répertoire non maîtrisé permet à un tiers de fournir une configuration (y compris une fausse `MILES_REMOTE_BASE_URL` pointant vers un endpointcontrôlé par lui, et une fausse clé API).

**Recommandation** : résoudre le chemin par rapport au répertoire de l'application plutôt qu'au répertoire courant, ou exiger un chemin absolu.

---

## 5. Points positifs constatés

- Aucune clé API n'est codée en dur ; les secrets viennent exclusivement de `os.environ`.
- `.env` est ignoré par Git (`.gitignore`, lignes 10 et 13) ; `data/*.db` également.
- `RemoteProvider` n'expose pas la clé dans ses exceptions (seul le corps de réponse tronqué est inclus).
- `ActionValidator` n'exécute aucune commande shell : liste blanche stricte de trois actions.
- Le moteur d'outils (après L-007 à L-010) applique bien la politique avant exécution, expire les confirmations, arrête le processus au timeout et n journals jamais d'exception brute.
- La記憶 persistante refuse les contenus ressemblant à des secrets et dégrade gracieusement sur base corrompue.
- Le serveur web n'expose aucune exécution de commande et n'a aucune route d'exécution d'outil.

---

## 6. Synthèse

| ID | Objet | Gravité | Statut |
|----|-------|----------|--------|
| S-001 | `NameError` latent dans `miles.py` | Moyenne | Démontré |
| S-002 | Interface web sans authentification | Moyenne / Haute si exposé | Démontré |
| S-003 | Divulgation d'exceptions brutes dans les réponses HTTP | Moyenne | Démontré |
| S-004 | `Content-Length` non borné | Moyenne | Démontré |
| S-005 | Traversée par symlink dans `list_files` | Moyenne | Démontré (code) |
| S-006 | `multiprocessing.Queue` jamais fermée | Faible | Démontré |
| S-007 | Conversation partagée sans verrou entre threads | Moyenne | Plausible |
| S-008 | CSRF sur les routes POST | Moyenne | Plausible |
| S-009 | Pas de limite de threads ni timeout de connexion | Faible/moyenne | Plausible |
| S-010 | `as_dict()` expose les clés API | Faible | Recommandation |
| S-011 | Faux positifs de la politique sur les valeurs | Faible | Recommandation |
| S-012 | `.env` chargé depuis le répertoire courant | Faible | Recommandation |

**Aucun correctif n'a été appliqué dans cette mission** : les fichiers `app/tools/engine.py`, `app/tools/policy.py` et `tests/test_tool_engine.py` (contenant les correctifs L-007 à L-010) n'ont pas été modifiés. S-001 à S-012 sont signalés pour traitement par le propriétaire de chaque fichier.

**La Phase 4 n'est pas validée globalement** : la validation Debian 13 (Agent B) et l'intégration de ces corrections restent à effectuer.
