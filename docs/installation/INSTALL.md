# Installation et configuration de MILES

Ce document explique comment installer, configurer et lancer le prototype MILES sur Debian 13 (ou tout système avec Python 3).

## 1. Prérequis

- Python 3.10 ou supérieur (testé avec Python 3.14)
- Aucun paquet système supplémentaire n'est requis pour le mode texte
- Les dépendances vocales (`pyttsx3`, `speech_recognition`) sont optionnelles

## 2. Installation

### Cloner le dépôt

```bash
git clone https://github.com/Miles-corp/Milescorp.git
cd Milescorp
```

### Créer et activer un environnement virtuel (recommandé)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Sur Windows (PowerShell) :
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 3. Configuration

### Fichier de configuration JSON (optionnel)

Copiez l'exemple et adaptez si nécessaire :

```bash
cp config/config.json.example config/config.json
```

Éditez `config/config.json` selon vos besoins. Ce fichier est optionnel : si absent, les valeurs par défaut sont utilisées.

### Variables d'environnement (optionnel)

Copiez l'exemple et adaptez :

```bash
cp .env.example .env
```

Éditez `.env` pour définir les clés API et les URLs des fournisseurs. Les variables sont chargées automatiquement par `Settings`.

Exemple `.env` :
```env
MILES_PROVIDER=remote
MILES_REMOTE_BASE_URL=http://localhost:8000
MILES_REMOTE_MODEL=miles-default
MILES_REMOTE_TIMEOUT=30
# MILES_REMOTE_API_KEY=votre_cle_api_ici
MILES_HISTORY_LIMIT=10
MILES_VOICE_ENABLED=false
```

> **Sécurité** : ne jamais commettre de vraies clés API dans `.env`. Le fichier `.env` est ignoré par Git (voir `.gitignore`).

## 3bis. Persistance de l'historique de conversation (V1)

Depuis la version V1, MILES enregistre l'historique de la conversation dans une
base SQLite locale (`data/conversations.db` par défaut) afin que la conversation
survive à un redémarrage du programme.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `MILES_CONVERSATION_PERSIST` | `true` | Enregistrer l'historique de conversation sur disque |
| `MILES_CONVERSATION_DB_PATH` | `data/conversations.db` | Emplacement de la base de transcription |

Le chemin de la base est **confiné aux racines autorisées** (répertoire du
projet et dossier `data/`) : un chemin hors de ces racines est refusé.

Les secrets ne sont jamais écrits dans l'historique : le contenu des messages
est expurgé des motifs de clé API, mot de passe et jeton avant écriture
(marqueur `[REDACTED]`).

Options de ligne de commande :
```bash
python miles.py                       # restaure la dernière conversation
python miles.py --new-conversation    # démarre une nouvelle conversation
python miles.py --conversation <id>   # restaure une conversation précise
python miles.py --list-conversations  # liste les conversations enregistrées
python miles.py --no-persist          # mode éphémère, rien n'est écrit
```

## 3ter. Sources de configuration et variables reconnues

MILES lit sa configuration depuis quatre sources. En cas de conflit, la
priorité est la suivante (de la plus forte à la plus faible) :

1. **Variables d'environnement du processus** (priorité la plus haute)
2. **Fichier `.env`** (chemin : `MILES_ENV_FILE`, défaut `.env` à la racine du projet)
3. **Fichier JSON** (`--config <chemin>`, sinon `MILES_CONFIG`, sinon `config/config.json`)
4. **Valeurs par défaut** intégrées au code

### Variables reconnues

Seules les variables `MILES_*` listées ci-dessous sont lues depuis le fichier `.env` :

| Catégorie | Variables |
|-----------|-----------|
| Fournisseur (7) | `MILES_PROVIDER`, `MILES_REMOTE_BASE_URL`, `MILES_REMOTE_MODEL`, `MILES_REMOTE_TIMEOUT`, `MILES_LOCAL_BASE_URL`, `MILES_LOCAL_MODEL`, `MILES_LOCAL_TIMEOUT` |
| Secrets (2) | `MILES_REMOTE_API_KEY`, `MILES_LOCAL_API_KEY` |
| Contexte (1) | `MILES_HISTORY_LIMIT` |
| Voix (facultative) (1) | `MILES_VOICE_ENABLED` |
| Mémoire de souvenirs (4) | `MILES_MEMORY_ENABLED`, `MILES_MEMORY_DB_PATH`, `MILES_MEMORY_MAX_MEMORIES_IN_CONTEXT`, `MILES_MEMORY_MAX_CONTENT_LENGTH` |
| Historique de conversation (2) | `MILES_CONVERSATION_PERSIST`, `MILES_CONVERSATION_DB_PATH` |

### Variables de chemin de fichier (lues uniquement de l'environnement)

Deux variables pilotent le chemin des fichiers de configuration. Elles sont lues
**exclusivement depuis l'environnement du processus** et ne sont **jamais**
lues depuis le fichier `.env` :

| Variable | Rôle | Valeur par défaut |
|----------|------|--------------------|
| `MILES_ENV_FILE` | Chemin du fichier `.env` | `.env` à la racine du projet |
| `MILES_CONFIG` | Chemin du fichier de configuration JSON | `config/config.json` |

Pourquoi cette restriction ? `MILES_ENV_FILE` sert à *localiser* le fichier
`.env` : il doit être connu avant que le `.env` ne soit lu, il ne peut donc
pas y figurer. `MILES_CONFIG` suit la même logique de cohérence.

Conséquence : écrire `MILES_ENV_FILE` ou `MILES_CONFIG` dans le `.env` est
**sans effet** — ces valeurs sont ignorées. Pour changer le chemin du JSON
depuis le `.env`, il faut définir `MILES_CONFIG` dans l'environnement du
processus (ou passer `--config` au lancement).

### Variables non reconnues

Toute autre variable présente dans le `.env` est **ignorée** : elle n'est ni
lue par MILES, ni injectée dans l'environnement du processus, ni transmise
aux sous-processus. Ce comportement est volontaire (herméneuticité et
isolation des tests) : le `.env` ne peut pas modifier l'environnement du
programme.

Sont concernées au premier chef les deux variables de chemin de fichier
(`MILES_ENV_FILE`, `MILES_CONFIG`) : même écrites dans le `.env`, elles
restent sans effet.

### Proxy HTTP/HTTPS

Le proxy doit être défini dans l'**environnement du processus**, pas dans le
`.env` : les requêtes HTTP de MILES passent par `urllib`, qui lit les
variables `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` de l'environnement.

```bash
# Linux / Debian
export HTTP_PROXY=http://proxy.exemple:3128
export HTTPS_PROXY=http://proxy.exemple:3128
python3 miles.py
```

```powershell
# Windows
$env:HTTP_PROXY="http://proxy.exemple:3128"
$env:HTTPS_PROXY="http://proxy.exemple:3128"
python miles.py
```

Une variable `HTTP_PROXY` écrite dans `.env` sera **sans effet**. Si un proxy
doit être configuré de façon persistante sans passer par le shell, il faut
utiliser la variable d'environnement du système ou un wrapper qui l'exporte
avant de lancer MILES.

### Limites de la prise en charge des variables d'environnement

- MILES lit au total 19 variables `MILES_*` : 17 variables de configuration
  lues depuis le `.env` (tableau ci-dessus) et 2 variables de chemin de fichier
  (`MILES_ENV_FILE`, `MILES_CONFIG`) lues **uniquement** depuis
  l'environnement du processus. Aucune autre variable n'est prise en compte.
- Le fichier `.env` ne sert qu'à fournir ces variables : il ne modifie pas
  l'environnement du processus.
- Les secrets (`MILES_REMOTE_API_KEY`, `MILES_LOCAL_API_KEY`) ne sont jamais
  journalisés ni écrits dans l'historique de conversation.
- Une variable booléenne doit valoir l'une des valeurs `true` / `1` / `yes` /
  `on` (ou `false` / `0` / `no` / `off`) ; toute autre valeur provoque une
  erreur de configuration explicite au démarrage.

## 4. Lancement

### Mode texte (dépendances standard uniquement)

```bash
python miles.py
```

Ou avec un fournisseur spécifique :
```bash
python miles.py --provider remote
python miles.py --provider local
```

Avec un fichier de configuration personnalisé :
```bash
python miles.py --config config/config.json
```

### Aide en ligne

```bash
python miles.py --help
```

### Commandes dans l'interface terminal

| Commande | Action |
|----------|--------|
| `/help` | Afficher l'aide des commandes |
| `/quit`, `/q`, `/exit` | Quitter le programme |
| `/clear` | Effacer l'historique de la conversation |
| `/provider` | Afficher le fournisseur IA courant |
| `/remember` | Enregistrer un souvenir explicite (usage : `/remember <texte>`) |
| `/memory` | Lister les souvenirs persistants |
| `/forget` | Supprimer un souvenir (usage : `/forget <id>`) |
| `/conversations` | Lister les conversations enregistrées |
| `/new` | Démarrer une nouvelle conversation |
| `/status` | Afficher l'état du programme |

## 5. Dépendances vocales (optionnelles)

La voix est désactivée par défaut (`MILES_VOICE_ENABLED=false`). Pour l'activer :

1. Installer les dépendances :
   ```bash
   pip install pyttsx3 speech-recognition
   ```
2. Définir `MILES_VOICE_ENABLED=true` dans `.env`

Si les dépendances sont absentes et que la voix est demandée, `VoiceUnavailableError` est levé et le programme continue en mode texte.

## 6. Exécution des tests

Tous les tests utilisent uniquement la bibliothèque standard `unittest` d'Aucune dépendance externe n'est requise.

```bash
python -m unittest discover -s tests -v
```

Sur Debian 13 :
```bash
python3 -m unittest discover -s tests -v
```

## 7. Répertoire de travail

- `app/` — code source du prototype (Agent A)
- `tests/` — tests automatisés (Agent B)
- `config/` — exemples de configuration
- `docs/` — documentation
- `scripts/` — scripts utilitaires (vide)
- `data/` — données utilisateur (vide)
- `logs/` — journaux (vide)
- `experiments/` — expérimentations (vide)

## 8. Dépannage

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| `ModuleNotFoundError: app` | Mauvaise exécution depuis un autre répertoire | Lancer depuis la racine du dépôt |
| `SettingsError: Fournisseur inconnu` | `MILES_PROVIDER` incorrect | Valeur attendue : `remote` ou `local` |
| `VoiceUnavailableError` | Dépendances vocales absentes | Installer `pyttsx3` et `speech-recognition` ou désactiver la voix |
| Erreur de connexion fournisseur | Endpoint non joignable | Vérifier `MILES_REMOTE_BASE_URL` ou `MILES_LOCAL_BASE_URL` |

## 9. Répertoire des logs et données

Les répertoires `logs/`, `data/` et `experiments/` existent mais sont vides. Ils sont prévus pour l'extension future (mémoire persistante, journaux d'exécution).
