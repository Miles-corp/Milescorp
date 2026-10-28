"""Non-régression : le site Companion ne charge aucune ressource distante.

Défauts trouvés le 2026-10-28 (`TASK-DEV-060`, corrigés en `TASK-DEV-061`) :

1. le bundle Readdy initialisait `SourceMapConsumer` sur
   ``https://unpkg.com/source-map@.../mappings.wasm`` — capacité d'appel
   externe dans un livrable censé fonctionner hors ligne (`DEC-014`) ;
2. `index.html` affichait des mesures inventées (`40 °C`, `14 ms`) et le
   libellé « build démo » avant que le pont ne les remplace.

Ces tests portent sur les fichiers **servis**, pas sur le serveur : ils
échouent si une valeur de démonstration ou un hôte distant réapparaît.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
COMPANION = RACINE / "app" / "interface" / "companion"
HTML = COMPANION / "index.html"
PONT = COMPANION / "miles-bridge.js"
ASSETS = COMPANION / "assets"
BUNDLE = ASSETS / "index-DSIZJMQZ.js"
CSS = sorted(ASSETS.glob("*.css")) + sorted((ASSETS / "remixicon").glob("*.css"))

#: Hôtes dont un chargement trahirait un détachement incomplet.
#: Forme URL (`//hote`) et non simple mot : le bundle cite `readdy.ai` dans
#: un filtre de liens et un logo neutralisé, sans jamais le charger.
HOTES_INTERDITS = (
    "//unpkg.com",
    "//cdnjs.cloudflare.com",
    "//cdn.jsdelivr.net",
    "//jsdelivr.net",
    "//fonts.googleapis.com",
    "//fonts.gstatic.com",
    "//static.readdy.ai",
    "//readdy.ai",
    "//app.posthog.com",
    "//us.i.posthog.com",
)

URL_ABSOLUE = re.compile(r"https?://")
MESURE = re.compile(r"\d{1,3}\s*°C|\b\d+\s*ms\b")

#: Marqueurs neutres que `miles-bridge.js` sait remplacer par une mesure réelle.
MARQUEURS = ("mesure indisponible", "état inconnu", "modèle inconnu")


class TestRessourcesDistantes(unittest.TestCase):
    def test_html_sans_url_absolue(self) -> None:
        self.assertEqual(URL_ABSOLUE.findall(HTML.read_text(encoding="utf-8")), [])

    def test_pont_sans_url_absolue(self) -> None:
        self.assertEqual(URL_ABSOLUE.findall(PONT.read_text(encoding="utf-8")), [])

    def test_css_sans_url_absolue(self) -> None:
        for feuille in CSS:
            with self.subTest(css=feuille.name):
                self.assertEqual(
                    URL_ABSOLUE.findall(feuille.read_text(encoding="utf-8")), []
                )

    def test_bundle_sans_hote_chargeable(self) -> None:
        contenu = BUNDLE.read_text(encoding="utf-8", errors="replace")
        for hote in HOTES_INTERDITS:
            with self.subTest(hote=hote):
                self.assertNotIn(hote, contenu)


class TestValeursInventees(unittest.TestCase):
    def test_html_sans_mesure(self) -> None:
        """Aucun chiffre de température ou de latence dans le HTML servi."""
        contenu = HTML.read_text(encoding="utf-8")
        self.assertEqual([m.group(0) for m in MESURE.finditer(contenu)], [])

    def test_html_sans_libelle_de_demonstration(self) -> None:
        contenu = HTML.read_text(encoding="utf-8")
        for interdit in ("build démo", "miles-local-7b"):
            with self.subTest(libelle=interdit):
                self.assertNotIn(interdit, contenu)

    def test_pont_remplace_les_marqueurs(self) -> None:
        """Les marqueurs neutres doivent rester traités : sinon la page reste vide."""
        pont = PONT.read_text(encoding="utf-8")
        for marqueur in MARQUEURS:
            with self.subTest(marqueur=marqueur):
                self.assertIn(marqueur, pont)


if __name__ == "__main__":
    unittest.main()
