# Paquet backend-box — télémétrie matérielle du boîtier

Service local qui expose les mesures réelles de la machine et reçoit les
relevés du boîtier ESP32-S3. Il ne fait **aucun appel réseau sortant** et
n'écrit qu'un fichier d'état local.

## Contenu

| Fichier | Rôle |
|---|---|
| `boxtelemetry.py` | Serveur HTTP local (bibliothèque standard uniquement) |
| `box_state.json` | Dernier relevé reçu (créé à l'exécution, **non versionné**) |

## Lancement

```bash
python3 boxtelemetry.py          # http://127.0.0.1:8095
```

Écoute **`127.0.0.1` par défaut**. Écouter ailleurs exige `MILES_BOX_HOST`
(adresse privée) **et** `MILES_BOX_KEY` : sans clé, le service refuse de
démarrer. C'est ce qui permet au boîtier WiFi de joindre le PC sans exposer
un service ouvert.

## Routes

| Route | Méthode | Contenu |
|---|---|---|
| `/box/telemetry` | GET | Mesures de l'hôte (`/proc`, `/sys/class/hwmon`) + état du dernier relevé ESP32 |
| `/box/ingest` | POST | Relevé envoyé par l'ESP32 ; clé partagée exigée (`MILES_BOX_KEY`) |

Ce qui n'existe pas n'est **jamais inventé** : un capteur absent répond
`{"etat": "non disponible"}`. Un relevé ESP32 plus vieux que 60 s est signalé
`recu mais perime` avec son âge, et le cockpit affiche cet âge.

## Configuration

| Variable | Rôle |
|---|---|
| `MILES_BOX_HOST` | Adresse d'écoute (défaut `127.0.0.1`) |
| `MILES_BOX_PORT` | Port d'écoute (défaut `8095`) |
| `MILES_BOX_KEY` | Clé partagée avec le firmware ; obligatoire hors local |

Générer la clé, puis la reporter dans le `.env` du paquet PC et dans
`platformio.local.ini` du firmware :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Vérification

```bash
python3 -m unittest tests.test_boxtelemetry -v
```
