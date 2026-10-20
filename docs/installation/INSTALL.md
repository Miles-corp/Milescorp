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
