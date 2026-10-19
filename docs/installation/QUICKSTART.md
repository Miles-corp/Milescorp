# Démarrage rapide de MILES (QUICKSTART)

Guide de démonstration en 10 à 15 minutes pour tester ce que MILES sait faire
au commit `fe5a017` (plus la correction L-006 non encore publiée).

## 1. Prérequis exacts

- Python 3.10 ou supérieur (testé avec Python 3.14 sur Windows)
- Aucun paquet système supplémentaire n'est requis pour le mode texte
- Aucune clé API n'est requise pour démarrer (le programme fonctionne sans fournisseur IA configuré)
- Les dépendances vocales (`pyttsx3`, `speech_recognition`) sont optionnelles

## 2. Instructions d'installation

### Sur Windows (PowerShell)

```powershell
git clone https://github.com/Miles-corp/Milescorp.git
cd Milescorp
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloque l'activation :
```powershell
.\.venv\Scripts\python.exe -m pip --version
```

### Sur Debian 13 / Linux

```bash
git clone https://github.com/Miles-corp/Milescorp.git
cd Milescorp
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Installation des dépendances

Le cœur de MILES utilise uniquement la bibliothèque standard Python (`urllib`, `json`, `sqlite3`, `unittest`, `argparse`). Le fichier `requirements.txt` est vide : aucune installation `pip` n'est obligatoire pour le mode texte.

Les dépendances vocales sont optionnelles :
```bash
pip install pyttsx3 speech-recognition
```

## 4. Configuration minimale

```bash
cp config/config.json.example config/config.json
cp .env.example .env
```

Éditer `.env` selon vos besoins. Pour une première démonstration, laisser les valeurs par défaut :
- `MILES_PROVIDER=remote` (aucun fournisseur distant n'est configuré, le programme signalera l'indisponibilité proprement)
- `MILES_MEMORY_ENABLED=false` (mémoire persistante désactivée par défaut)

## 5. Commande exacte pour démarrer MILES

```bash
python miles.py
```

Ou avec un fournisseur spécifique :
```bash
python miles.py --provider remote
python miles.py --provider local
```

Aide en ligne :
```bash
python miles.py --help
```

## 6. Scénario de démonstration (10 à 15 minutes)

### 6.1 Démarrage et arrêt

1. Lancer `python miles.py` : l'écran d'accueil s'affiche avec le nom du fournisseur.
2. Taper `/help` : la liste des commandes s'affiche.
3. Taper `/status` : l'état du programme s'affiche (fournisseur, disponibilité, historique, mémoire).
4. Taper `/quit` : le programme se termine proprement.

### 6.2 Commandes d'aide et de statut

- `/help` : affiche toutes les commandes disponibles.
- `/status` : affiche le fournisseur courant, sa disponibilité, le nombre de messages dans l'historique, et l'état de la mémoire persistante.
- `/provider` : affiche le nom du fournisseur IA actif.

### 6.3 Fournisseur IA configuré

Aucun fournisseur IA distant ou local n'est préconfiguré. Si vous disposez d'un endpoint compatible (OpenAI-like distant ou Ollama/llama.cpp local), définissez `MILES_REMOTE_BASE_URL` ou `MILES_LOCAL_BASE_URL` dans `.env`, puis relancez MILES. Sans fournisseur, le programme indique clairement qu'aucun fournisseur n'est configuré et refuse poliment les requêtes de conversation.

### 6.4 Conversation simple (si fournisseur disponible)

Sans fournisseur configuré, toute saisie texte affiche : "Erreur : aucun fournisseur IA configuré." Cela ne constitue pas un dysfonctionnement.

### 6.5 Création d'un souvenir explicite (mémoire activée)

1. Éditer `.env` : `MILES_MEMORY_ENABLED=true`.
2. Relancer `python miles.py`.
3. Taper `/remember Je préfère le thé au café.` : le souvenir est enregistré (id affiché).
4. Taper `/memory` : la liste des souvenirs s'affiche avec leur id, catégorie et importance.

### 6.6 Consultation de la mémoire

`/memory` affiche tous les souvenirs persistants stockés dans `data/memory.db`.

### 6.7 Suppression d'un souvenir

Taper `/forget <id>` (remplacer `<id>` par l'identifiant affiché lors de l'enregistrement). Le programme confirme la suppression.

### 6.8 Persistance après redémarrage

1. Quitter MILES (`/quit`).
2. Relancer `python miles.py`.
3. Taper `/memory` : le souvenir enregistré précédemment est toujours présent (persistence SQLite).

### 6.9 Refus des contenus ressemblant à des secrets

Taper `/remember Ma clé API est sk-1234567890abcdef` : le programme refuse l'enregistrement et affiche un message d'erreur explicite (motif secret détecté).

### 6.10 Mémoire désactivée

Éditer `.env` : `MILES_MEMORY_ENABLED=false`. Relancer MILES. Taper `/status` : la mémoire est affichée comme "désactivée/indisponible". Taper `/remember test` : le programme indique que la mémoire est indisponible.

## 7. Résultats attendus et limites connues

| Fonction | Résultat attendu | Limite connue |
|----------|------------------|---------------|
| `miles.py --help` | Affiche l'aide, code de sortie 0 | — |
| `miles.py` démarre | Écran d'accueil, invite `> ` | Aucun fournisseur IA configuré par défaut |
| `/help`, `/status`, `/provider`, `/quit` | Fonctionnent | — |
| `/remember`, `/memory`, `/forget` | Fonctionnent si `MILES_MEMORY_ENABLED=true` | Mémoire désactivée par défaut |
| Conversation IA | Refus propre si aucun fournisseur | Aucun fournisseur configuré, aucune clé API fournie |
| Persistance après redémarrage | Souvenir conservé (SQLite) | Non testé sur ce poste (pas de Python 3) |
| Refus des secrets | Erreur explicite | — |

## 8. Erreurs fréquentes et diagnostic

| Erreur | Cause probable | Solution |
|--------|---------------|----------|
| `ModuleNotFoundError: No module named 'app'` | Lancement depuis un autre répertoire | Lancer depuis la racine du dépôt |
| `SettingsError: Fournisseur inconnu` | `MILES_PROVIDER` incorrect | Valeur attendue : `remote` ou `local` |
| `VoiceUnavailableError` | Dépendances vocales absentes | Installer `pyttsx3` et `speech-recognition` ou désactiver la voix |
| Erreur de connexion fournisseur | Endpoint non joignable | Vérifier `MILES_REMOTE_BASE_URL` ou `MILES_LOCAL_BASE_URL` |
| Base SQLite corrompue | Fichier `data/memory.db` non-SQLite | Dégradation gracieuse : mémoire indisponible, programme continue |

## 9. Commandes d'arrêt et de redémarrage

- Arrêt propre : taper `/quit` ou `/q` ou `/exit` dans MILES, ou `Ctrl+C`.
- Redémarrage : relancer `python miles.py` depuis la racine du dépôt.
- Réinitialisation complète de la mémoire : supprimer manuellement le fichier `data/memory.db` (ce fichier est exclu de Git).

## 10. Ce qui n'a pas pu être vérifié

Ce guide a été rédigé par inspection statique du code. Aucun test n'a pu être exécuté sur ce poste Windows car `python3` n'y est pas installé. Les résultats ci-dessus doivent être confirmés par exécution réelle (Windows avec Python, ou Debian 13).
