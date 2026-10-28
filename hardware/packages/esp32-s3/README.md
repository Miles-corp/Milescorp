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

**Convention de nom obligatoire** : le fichier personnel doit s'appeler
`platformio.local.ini`. Le suffixe `.local` est exclu des archives par
`scripts/build_release.py` ; un fichier `.ini` ordinaire, lui, partirait dans
le livrable avec ses secrets. Le `platformio.ini` versionné ne contient que
des marqueurs.

## Build et flash (à faire par toi, hors de cette mission)
```bash
pio run -t upload    # via USB
pio device monitor   # journal série
```
La LED passe au **vert** quand le backend box répond, **rouge** sinon.

## Sécurité et honnêteté des mesures

- **Aucune valeur inventée** : si aucun capteur de température n'est lu, le
  champ n'est pas envoyé du tout (le backend enregistre le relevé sans
  température). Il n'existe plus de `-1` ni de `-99` envoyé comme une mesure.
- **Configuration incomplète = arrêt net** : si un marqueur `REPLACE_ME`
  subsiste, le firmware affiche la raison et n'ouvre aucune connexion.
- **URL de bouclage refusée** : `http://127.0.0.1:8095` (ou `localhost`,
  `0.0.0.0`) désignerait l'ESP32 lui-même ; le firmware refuse de démarrer.
- **Aucun port ouvert** : client uniquement, aucun serveur embarqué.

## État de la vérification

- **Compilation réelle effectuée le 2026-10-28** (Windows, chaîne installée
  pour l'occasion) :

  | Élément | Valeur |
  |---|---|
  | Plateforme | `espressif32@8.0.0` |
  | Toolchain | `toolchain-xtensa-esp-elf@14.2.0+20260121` |
  | Framework | `framework-arduinoespressif32@4.30312.261024` |
  | Résultat | `[SUCCESS] Took 1227.56 seconds` |
  | Image | `firmware.bin`, 1 103 072 octets |
  | RAM / Flash | 14,2 % (46 576 / 327 680 o) · 32,5 % (1 087 133 / 3 342 336 o) |

  Commande exacte : `pio run -d hardware/packages/esp32-s3`.

- **Flash et comportement sur matériel : NON VÉRIFIÉS** — aucun ESP32-S3
  branché pendant cette vérification. La LED, le bouton et la liaison WiFi
  réelle restent à confirmer sur le boîtier.
- **Tests backend** : `tests/test_boxtelemetry.py`.
- **Génération des archives** : `python3 scripts/build_release.py` (le dossier
  `.pio/` de compilation n'entre jamais dans l'archive, vérifié par
  `tests/test_build_release.py`).
