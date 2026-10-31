"""Non-régression : le site Companion ne charge aucune ressource distante.

Le site servi est la coque construite dans ``dist/``, plus l'ancien export
Readdy (conservé hors service). Ces tests portent sur les fichiers
**réellement servis** et échouent si un hôte distant ou une mesure inventée
réapparaît dans le build.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
COMPANION = RACINE / "app" / "interface" / "companion"
DIST = COMPANION / "dist"
HTML = DIST / "index.html"
BUNDLES = sorted((DIST / "app").glob("*.js"))
CSS = sorted((DIST / "app").glob("*.css"))

#: Hôtes dont un chargement trahirait un détachement incomplet.
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


class BuildPresentTest(unittest.TestCase):
    def test_build_shell_exists(self) -> None:
        self.assertTrue(HTML.is_file(), "exécutez npm run build dans frontend/")
        self.assertTrue(BUNDLES, "aucun bundle JS dans dist/app")
        self.assertTrue(CSS, "aucune feuille CSS dans dist/app")


class TestRessourcesDistantes(unittest.TestCase):
    def test_html_sans_url_absolue(self) -> None:
        self.assertEqual(URL_ABSOLUE.findall(HTML.read_text(encoding="utf-8")), [])

    def test_css_sans_url_absolue(self) -> None:
        for feuille in CSS:
            with self.subTest(css=feuille.name):
                self.assertEqual(
                    URL_ABSOLUE.findall(feuille.read_text(encoding="utf-8")), []
                )

    def test_bundle_sans_hote_chargeable(self) -> None:
        for bundle in BUNDLES:
            contenu = bundle.read_text(encoding="utf-8", errors="replace")
            for hote in HOTES_INTERDITS:
                with self.subTest(bundle=bundle.name, hote=hote):
                    self.assertNotIn(hote, contenu)

    def test_html_reference_uniquement_le_local(self) -> None:
        contenu = HTML.read_text(encoding="utf-8")
        references = re.findall(r'(?:src|href)="([^"]+)"', contenu)
        self.assertTrue(references)
        for reference in references:
            with self.subTest(reference=reference):
                self.assertTrue(
                    reference.startswith(("/app/", "/assets/", "/icons/", "/manifest.webmanifest")),
                    "ressource non locale : %s" % reference,
                )


class TestApplicationInstallable(unittest.TestCase):
    """Manifeste et service worker : installation locale, jamais hors API."""

    def test_manifeste_valide_et_icones_presentes(self) -> None:
        manifeste = DIST / "manifest.webmanifest"
        self.assertTrue(manifeste.is_file(), "manifeste absent du build")
        data = json.loads(manifeste.read_text(encoding="utf-8"))
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")
        self.assertEqual(data["name"], "Miles Companion")
        tailles = {icone["sizes"] for icone in data["icons"]}
        self.assertIn("192x192", tailles)
        self.assertIn("512x512", tailles)
        self.assertTrue(any(icone.get("purpose") == "maskable" for icone in data["icons"]))
        for icone in data["icons"]:
            with self.subTest(icone=icone["src"]):
                chemin = DIST / icone["src"].lstrip("/")
                self.assertTrue(chemin.is_file(), "icône absente : %s" % chemin)

    def test_service_worker_ne_met_jamais_l_api_en_cache(self) -> None:
        worker = DIST / "sw.js"
        self.assertTrue(worker.is_file(), "service worker absent du build")
        source = worker.read_text(encoding="utf-8")
        self.assertIn(
            'const BYPASS = ["/api/", "/setup", "/healthz", "/cockpit/"];', source
        )
        self.assertIn("/manifest.webmanifest", source)


class TestValeursInventees(unittest.TestCase):
    def test_html_sans_mesure(self) -> None:
        self.assertEqual([m.group(0) for m in MESURE.finditer(HTML.read_text(encoding="utf-8"))], [])

    def test_html_sans_libelle_de_demonstration(self) -> None:
        contenu = HTML.read_text(encoding="utf-8")
        for interdit in ("build démo", "miles-local-7b"):
            with self.subTest(libelle=interdit):
                self.assertNotIn(interdit, contenu)

    def test_aucun_chiffre_de_capteur_dans_le_html(self) -> None:
        """Les mesures viennent de l'API, jamais d'un HTML pré-rempli."""
        contenu = HTML.read_text(encoding="utf-8")
        for invente in ("40 °C", "14 ms", "42.5", "87 %"):
            with self.subTest(valeur=invente):
                self.assertNotIn(invente, contenu)


if __name__ == "__main__":
    unittest.main()
