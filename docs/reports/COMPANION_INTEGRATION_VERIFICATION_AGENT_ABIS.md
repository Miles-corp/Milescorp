# Vérification de l'intégration Miles Companion — Agent A bis

- **Date** : 2026-10-28
- **Auteur** : Agent A bis (instance site web)
- **Base** : `main` @ `ec9d62c` (995 tests OK, 5 ignorés)
- **Périmètre** : `app/interface/companion/**`, `tests/test_companion_static_assets.py`
- **Push** : aucun (mandat)

## Méthode

Trois niveaux, distingués partout : **lu** (code), **exécuté** (commande + sortie
réelle), **non vérifié** (exigerait un navigateur ou un boîtier).

| Commande | Résultat réel |
|---|---|
| `tests.test_companion_server` + `test_web_device` + `test_web_project_board` | **63 tests OK** (25,5 s) |
| `tests.test_companion_static_assets` (nouveau) | **7 tests OK** |
| `python -m unittest discover -s tests -t .` | **995 OK, 5 ignorés** (mesure de session) |

## 1. Ressources distantes — DÉFAUT TROUVÉ PUIS CORRIGÉ

`index.html` ne référence que des chemins locaux (`assets/fonts.css`,
`assets/remixicon/remixicon.min.css`, `assets/index-*.js`, `assets/index-*.css`,
vidéo et poster locaux). Le filigrane Readdy est neutralisé en CSS **et** par
une seconde couche dans `miles-bridge.js` (lignes 120-136). Aucune URL absolue
dans `index.html`, `miles-bridge.js` ni les CSS (vérifié par test).

**Défaut** : le bundle servi `assets/index-DSIZJMQZ.js` initialisait
`SourceMapConsumer` avec

```
https://unpkg.com/source-map@0.7.6/lib/mappings.wasm
```

soit une **capacité d'appel réseau externe** dans un livrable censé tourner
hors ligne (`DEC-014`), atteinte sur le chemin de cartographie d'erreur.

**Correction** : l'URL est retirée du bundle (chaîne vide), le `try/catch`
existant retombant déjà sur `initialize({})`. Vérifié : `grep -c unpkg` → **0**.

Les autres hôtes du bundle (`react.dev`, `reactrouter.com`, `i18next.com`,
`github.com`, `localhost`) sont des **liens ou messages**, jamais chargés.

## 2. Valeurs inventées — DÉFAUT TROUVÉ PUIS CORRIGÉ

`index.html` est un instantané pré-rendu qui affichait, avant tout script :
`40 °C · 14 ms`, `Éveillé · 40 °C`, `miles-local-7b`, `build démo` et une barre
de démarrage figée à **57 %**.

Le pont utilisait ces chaînes comme **sentinelles** à remplacer par des mesures
réelles ou un refus explicite (`⚠ pas de capteurs`, `⚠ hors ligne`). Les
supprimer sans précaution aurait cassé le remplissage.

**Correction** : les valeurs sont devenues des marqueurs **honnêtes** —
`mesure indisponible`, `état inconnu`, `modèle inconnu` — et le pont traite ces
marqueurs exactement comme les anciens (trois branches ajoutées). Le libellé
`build démo` est retiré, la barre de démarrage part de 0 % (le pont l'anime).

**Conséquence** : sans JavaScript, la page n'affiche plus de mesure fabriquée ;
elle affiche qu'elle ne sait pas. Avec JavaScript, elle affiche la mesure réelle.

## 3. Surface HTTP — CONFORME

- Écoute par défaut `127.0.0.1` ; `server.py` **refuse** toute autre valeur
  (`Refus : Miles Companion n'ecoute que sur 127.0.0.1.`, lignes 330-333).
- Liste blanche de fichiers et routes SPA bornées ; traversée
  `/cockpit/%2e%2e/server.py` → **404** (couvert par les tests).
- Relais à cibles fixes (`MILES_DEFAULT` 8080, `BOX_DEFAULT` 8095), aucun
  paramètre utilisateur dans l'URL ; `/api/box` rend **503** sans valeur si le
  backend est muet.

## 4. Non-régression ajoutée

`tests/test_companion_static_assets.py` (7 tests) échoue si :

- une URL absolue réapparaît dans `index.html`, `miles-bridge.js` ou un CSS ;
- un hôte chargeable (`unpkg`, `cdnjs`, `jsdelivr`, Google Fonts, `readdy.ai`
  sous forme d'URL, PostHog) réapparaît dans le bundle ;
- une mesure (`\d+ °C`, `\d+ ms`) ou un libellé de démonstration revient dans
  le HTML servi ;
- le pont cesse de traiter les trois marqueurs.

## 5. Ce que je ne prétends pas

- **Aucun test dans un navigateur** : je n'ai pas vérifié le rendu, ni que le
  pont remplace effectivement les marqueurs à l'exécution.
- **Aucun test sur un boîtier réel** (capteurs, ESP32-S3, firmware).
- **Aucune validation Debian 13** : elle se fera en VM, côté utilisateur.
- Aucun test de charge ni de comportement en cas d'échec du chargement du pont.

## 6. Verdict

L'intégration est **fonctionnelle et saine côté serveur**. Les deux écarts
constatés le 2026-10-28 — appel `unpkg.com` dans le bundle, valeurs de
démonstration dans le HTML — sont **corrigés et couverts par des tests de
non-régression**. `TASK-DEV-044` peut être considérée comme traitée sur le
volet « détachement / valeurs inventées » ; le volet navigateur et boîtier réel
reste à faire, et je ne le présente pas comme acquis.
