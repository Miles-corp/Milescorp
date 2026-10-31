"""Tests du serveur local Miles Companion (`127.0.0.1:8787`).

Le serveur a deux rôles :

- servir l'application (build statique) et le cockpit du dépôt sous
  ``/cockpit/`` — une seule implémentation des vues Projet / Conversation /
  Mémoire / Outils, jamais une copie ;
- relayer les routes de l'agent vers MILES (`127.0.0.1:8080`).

Ces tests vérifient le routage, la liste blanche des fichiers servis,
l'absence de ressource distante dans la page servie, et le relais réel des
routes d'API (vérifié contre un MILES factice, sans réseau externe).
"""

from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.interface.companion import server as companion

COMPANION_DIR = Path(companion.ROOT)
COCKPIT_HTML = Path(companion.COCKPIT_DIR) / "index.html"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Ne jamais suivre une redirection : les tests la vérifient elle-même."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


class CompanionTestServer:
    """Serveur Companion sur un port libre, avec client HTTP brut."""

    def __init__(self) -> None:
        self._httpd = companion.Server(("127.0.0.1", 0), companion.Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._port

    def request(
        self,
        path: str,
        method: str = "GET",
        body: object = None,
        accept: str | None = None,
    ) -> dict[str, object]:
        """Requête sans suivi de redirection."""
        url = "http://127.0.0.1:%d%s" % (self._port, path)
        data = None
        headers = {}
        if accept:
            headers["Accept"] = accept
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=15) as resp:
                return {
                    "status": resp.status,
                    "body": resp.read().decode("utf-8", "replace"),
                    "type": resp.headers.get("Content-Type", ""),
                    "location": resp.headers.get("Location", ""),
                    "sw_allowed": resp.headers.get("Service-Worker-Allowed", ""),
                }
        except urllib.error.HTTPError as exc:
            return {
                "status": exc.code,
                "body": exc.read().decode("utf-8", "replace"),
                "type": exc.headers.get("Content-Type", ""),
                "location": exc.headers.get("Location", ""),
                "sw_allowed": exc.headers.get("Service-Worker-Allowed", ""),
            }

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def __enter__(self) -> "CompanionTestServer":
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()


class FakeMiles(BaseHTTPRequestHandler):
    """MILES factice : enregistre la dernière requête reçue."""

    received: list[dict[str, object]] = []
    server_version = "FakeMiles"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def _record(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        FakeMiles.received.append({"method": method, "path": self.path, "body": body})
        payload = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        self._record("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._record("POST")


class CompanionRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = CompanionTestServer()
        self.addCleanup(self.server.stop)

    def test_cockpit_without_slash_redirects(self) -> None:
        result = self.server.request("/cockpit")
        self.assertEqual(result["status"], 302)
        self.assertEqual(result["location"], "/cockpit/")

    def test_projet_redirects_to_the_cockpit(self) -> None:
        """L'ancienne page Projet est un doublon : elle renvoie au cockpit."""
        result = self.server.request("/projet")
        self.assertEqual(result["status"], 302)
        self.assertEqual(result["location"], "/cockpit/")
        self.assertFalse(
            (COMPANION_DIR / "projet.html").exists(),
            "projet.html ne doit pas exister : une seule implémentation",
        )

    def test_cockpit_index_is_served(self) -> None:
        result = self.server.request("/cockpit/")
        self.assertEqual(result["status"], 200)
        self.assertIn("text/html", str(result["type"]))
        self.assertIn("app.css", str(result["body"]))
        # Fichier identique a celui du depot (fin de ligne normalisee).
        self.assertEqual(
            str(result["body"]).replace("\r\n", "\n"),
            COCKPIT_HTML.read_text(encoding="utf-8").replace("\r\n", "\n"),
        )

    def test_cockpit_assets_are_served(self) -> None:
        css = self.server.request("/cockpit/app.css")
        script = self.server.request("/cockpit/app.js")
        icon = self.server.request("/cockpit/miles.svg")
        self.assertEqual(css["status"], 200)
        self.assertIn("text/css", str(css["type"]))
        self.assertEqual(script["status"], 200)
        self.assertIn("javascript", str(script["type"]))
        self.assertEqual(icon["status"], 200)
        self.assertIn("image/svg+xml", str(icon["type"]))

    def test_cockpit_whitelist_refuses_anything_else(self) -> None:
        for path in ("/cockpit/inconnu.txt", "/cockpit/%2e%2e/server.py"):
            with self.subTest(path=path):
                result = self.server.request(path)
                self.assertEqual(result["status"], 404)

    def test_application_files_are_the_only_public_ones(self) -> None:
        """Seule la coque construite est publique, jamais les sources."""
        shell = self.server.request("/")
        self.assertEqual(shell["status"], 200)
        self.assertIn('id="root"', str(shell["body"]))
        # L'ancien site Readdy n'est plus une ressource publique.
        self.assertEqual(self.server.request("/index.html")["status"], 404)
        self.assertEqual(self.server.request("/miles-bridge.js")["status"], 404)
        # Le code du serveur n'est pas une ressource publique.
        self.assertEqual(self.server.request("/server.py")["status"], 404)

    def test_spa_routes_render_the_application(self) -> None:
        for path in ("/device", "/discover", "/miles", "/routines", "/settings"):
            with self.subTest(path=path):
                result = self.server.request(path)
                self.assertEqual(result["status"], 200)
                self.assertIn("Miles Companion", str(result["body"]))

    def test_unknown_asset_is_still_a_404(self) -> None:
        self.assertEqual(self.server.request("/assets/absent.png")["status"], 404)

    def test_missions_is_a_page_for_browsers(self) -> None:
        """Le chemin /missions appartient à l'application, pas au relais MILES."""
        page = self.server.request("/missions", accept="text/html,application/xhtml+xml")
        self.assertEqual(page["status"], 200)
        self.assertIn("text/html", str(page["type"]))
        self.assertIn('id="root"', str(page["body"]))

    def test_pwa_files_are_served(self) -> None:
        """Manifeste, service worker et icônes : installation depuis le navigateur."""
        manifeste = self.server.request("/manifest.webmanifest")
        self.assertEqual(manifeste["status"], 200)
        self.assertIn("application/manifest+json", str(manifeste["type"]))
        self.assertIn("standalone", str(manifeste["body"]))

        worker = self.server.request("/sw.js")
        self.assertEqual(worker["status"], 200)
        self.assertIn("javascript", str(worker["type"]))
        self.assertEqual(worker["sw_allowed"], "/")

        icone = self.server.request("/icons/icon-192.png")
        self.assertEqual(icone["status"], 200)
        self.assertIn("image/png", str(icone["type"]))
        self.assertEqual(self.server.request("/icons/absent.png")["status"], 404)


class ServedPageTest(unittest.TestCase):
    """La page servie ne doit contenir que des ressources locales."""

    def setUp(self) -> None:
        # La page réellement servie est la coque construite, pas l'ancien
        # export Readdy conservé pour historique.
        self.html = (COMPANION_DIR / "dist" / "index.html").read_text(encoding="utf-8")

    def test_page_is_french(self) -> None:
        self.assertIn('lang="fr"', self.html)

    def test_no_remote_resource_is_referenced(self) -> None:
        for scheme in ("http://", "https://", "//cdn", "unpkg"):
            self.assertNotIn(scheme, self.html, scheme)

    def test_unused_icon_font_is_gone(self) -> None:
        """FontAwesome n'était référencé nulle part : il a été supprimé."""
        self.assertNotIn("fontawesome", self.html.lower())
        leftovers = list((COMPANION_DIR / "assets" / "fontawesome").rglob("*"))
        self.assertEqual(
            [str(p) for p in leftovers if p.is_file()],
            [],
            "aucun fichier FontAwesome ne doit rester",
        )

    def test_favicon_is_local_and_present(self) -> None:
        self.assertIn("assets/miles.svg", self.html)
        self.assertTrue((COMPANION_DIR / "assets" / "miles.svg").is_file())
        self.assertNotIn("/vite.svg", self.html)

    def test_referenced_local_files_exist(self) -> None:
        for name in ("assets/fonts.css", "assets/remixicon/remixicon.min.css"):
            with self.subTest(name=name):
                self.assertIn(name, self.html)
                self.assertTrue((COMPANION_DIR / name).is_file(), name)


class MilesRelayTest(unittest.TestCase):
    """Le relais vers MILES doit transmettre la route et le corps tels quels."""

    def setUp(self) -> None:
        FakeMiles.received = []
        self.miles = ThreadingHTTPServer(("127.0.0.1", 0), FakeMiles)
        self.miles_port = self.miles.server_address[1]
        self._thread = threading.Thread(target=self.miles.serve_forever, daemon=True)
        self._thread.start()

        def stop_miles() -> None:
            # Ordre impose : arreter la boucle AVANT de fermer le socket.
            self.miles.shutdown()
            self.miles.server_close()

        self.addCleanup(stop_miles)

        previous = os.environ.get("COMPANION_MILES_URL")
        os.environ["COMPANION_MILES_URL"] = "http://127.0.0.1:%d" % self.miles_port

        def restore() -> None:
            if previous is None:
                os.environ.pop("COMPANION_MILES_URL", None)
            else:
                os.environ["COMPANION_MILES_URL"] = previous

        self.addCleanup(restore)
        self.server = CompanionTestServer()
        self.addCleanup(self.server.stop)

    def test_api_route_is_relayed_unchanged(self) -> None:
        result = self.server.request("/api/project")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"], json.dumps({"ok": True, "path": "/api/project"}))
        self.assertEqual(FakeMiles.received[-1]["path"], "/api/project")

    def test_cockpit_api_prefix_is_relayed(self) -> None:
        self.server.request("/api/tasks")
        self.assertEqual(FakeMiles.received[-1]["path"], "/api/tasks")

    def test_post_body_is_relayed_unchanged(self) -> None:
        """L'écriture des statuts depuis le cockpit passe par ce relais."""
        payload = {"status": "DONE", "agent": "Agent A"}
        result = self.server.request(
            "/api/tasks/TASK-DEV-099/status", method="POST", body=payload
        )
        self.assertEqual(result["status"], 200)
        last = FakeMiles.received[-1]
        self.assertEqual(last["method"], "POST")
        self.assertEqual(last["path"], "/api/tasks/TASK-DEV-099/status")
        self.assertEqual(json.loads(str(last["body"])), payload)

    def test_unreachable_miles_is_reported_explicitly(self) -> None:
        os.environ["COMPANION_MILES_URL"] = "http://127.0.0.1:9"
        result = self.server.request("/api/project")
        self.assertEqual(result["status"], 502)
        self.assertIn("MILES injoignable", str(result["body"]))


class FakeBox(BaseHTTPRequestHandler):
    """Backend boitier factice : une telemetrie plausible, aucune valeur reelle."""

    server_version = "FakeBox"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        payload = json.dumps(
            {
                "source": "boxtelemetry",
                "cpu": {"charge": [0.42], "uptime_s": 120.0},
                "temperatures": [{"capteur": "hwmon0", "celsius": 42.5}],
                "ventilos": [{"capteur": "hwmon0", "tr/min": 1200}],
                "injection_esp32": {"etat": "aucun"},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class BoxRelayTest(unittest.TestCase):
    """L'ancienne route publique `/api/box` a disparu avec le pont Readdy.

    Le boîtier est désormais lu côté serveur (session exigée) et sa lecture
    réelle est couverte par ``tests/test_companion_sensors.py``.
    """

    def _point_box_at(self, port: int) -> None:
        previous = os.environ.get("COMPANION_BOX_URL")
        os.environ["COMPANION_BOX_URL"] = "http://127.0.0.1:%d" % port

        def restore() -> None:
            if previous is None:
                os.environ.pop("COMPANION_BOX_URL", None)
            else:
                os.environ["COMPANION_BOX_URL"] = previous

        self.addCleanup(restore)

    def setUp(self) -> None:
        # MILES factice : sert a prouver que /api/box ne lui est PAS relaye.
        FakeMiles.received = []
        self.miles = ThreadingHTTPServer(("127.0.0.1", 0), FakeMiles)
        self._miles_thread = threading.Thread(
            target=self.miles.serve_forever, daemon=True
        )
        self._miles_thread.start()

        def stop_miles() -> None:
            self.miles.shutdown()
            self.miles.server_close()

        self.addCleanup(stop_miles)
        previous = os.environ.get("COMPANION_MILES_URL")
        os.environ["COMPANION_MILES_URL"] = "http://127.0.0.1:%d" % (
            self.miles.server_address[1]
        )

        def restore_miles() -> None:
            if previous is None:
                os.environ.pop("COMPANION_MILES_URL", None)
            else:
                os.environ["COMPANION_MILES_URL"] = previous

        self.addCleanup(restore_miles)

        self.server = CompanionTestServer()
        self.addCleanup(self.server.stop)

    def test_ancienne_route_publique_est_fermee(self) -> None:
        """Aucune route `/api/box` non authentifiée ne subsiste."""
        self._point_box_at(9)
        result = self.server.request("/api/box")
        self.assertEqual(result["status"], 404)
        self.assertNotIn("celsius", str(result["body"]))
        self.assertNotIn("tr/min", str(result["body"]))

    def test_route_du_boitier_n_est_pas_relayee_a_miles(self) -> None:
        """`/api/box` n'existe plus, et rien de tel n'est transmis à MILES."""
        self._point_box_at(9)
        self.server.request("/api/box")
        chemins = [entree["path"] for entree in FakeMiles.received]
        self.assertNotIn("/api/box", chemins)


class LoopbackOnlyTest(unittest.TestCase):
    def test_server_refuses_non_loopback_host(self) -> None:
        self.assertEqual(companion.main(["--host", "0.0.0.0", "--port", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
