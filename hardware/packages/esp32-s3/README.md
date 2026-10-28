# Paquet ESP32-S3 — Capteurs du boîtier MILES

## Contenu
| Fichier | Rôle |
|---|---|
| `src/main.cpp` | Firmware : WiFi client + télémétrie → backend box |
| `platformio.ini` | Configuration de build (esp32-s3-devkitc-1) |
| `README.md` | Ce fichier |

## Rôle du firmware
Le firmware de l'ESP32-S3 relève les capteurs physiques (température,
humidité, bouton) et les pousse vers le backend box local
(`POST http://<PC>/box/ingest`) toutes les 10 s.

**Aucun port n'est ouvert sur l'ESP32** : le module est **client uniquement**
→ surface réseau minimale (conforme au mode C WiFi).

## Câblage
| Broche | Signal |
|---|---|
| GPIO 0 (BOOT) | Bouton (actif bas) |
| GPIO 2 | LED d'état (active haute) |
| GPIO 4 + GPIO 5 | DHT22 Data (optionnel) |
| GND → GND, 3V3 → 3V3 | Alimentation |

## Configuration du WiFi
À la compilation, définir :
```ini
[env]
build_flags =
    -DWIFI_SSID=\"votre_ssid\"
    -DWIFI_PASS=\"votre_mdp\"
    -DBACKEND_URL=\"http://<IP_du_PC>:8095\"
    -DBOX_KEY=\"<cle_partagee>\"
```
Les identifiants sont dans le `.env` du backend box (`MILES_BOX_KEY`).
**Ne jamais commiter les identifiants WiFi** — ils sont injectés à la compilation.

## Build et flash (à faire par toi, hors de cette mission)
```bash
pio run -t upload    # via USB
pio device monitor   # journal série
```
La LED passe au **vert** quand le backend box répond, **rouge** sinon.

## État de la vérification
- **Code source livré** (README, platformio.ini, main.cpp) ;
- **Compilation et flash NON VÉRIFIÉS ici** (pas d'outil ESP32 dans le périmètre actuel) ;
- **Tests backend** : `tests/test_boxtelemetry.py` (7/7 OK, Windows).
