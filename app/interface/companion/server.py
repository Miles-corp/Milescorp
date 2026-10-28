"""Serveur local de Miles Companion (127.0.0.1 uniquement).

Sert l'application (build statique) et proxifie les routes de l'agent vers le
serveur MILES. Aucune ressource distante n'est chargee : polices, icones,
images et video sont servies depuis ce dossier.

Usage :
    python -m app.interface.companion.server
    python app/interface/companion/server.py --port 8787

Variables d'environnement :
    COMPANION_MILES_URL   URL du serveur MILES (defaut http://127.0.0.1:8080)
    COMPANION_PORT        port d'ecoute (defaut 8787)
    COMPANION_HOST        interface d'ecoute (defaut 127.0.0.1)
"""

from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
MILES_DEFAULT = "http://127.0.0.1:8080"
PORT_DEFAULT = 8787

# Backend boitier (telemetrie materielle). Cible figee : le cockpit ne peut
# pas faire pointer ce relai ailleurs, et aucun chemin n'est repris de la
# requete cliente (pas de relai arbitraire).
BOX_DEFAULT = "http://127.0.0.1:8095"
BOX_PATH = "/box/telemetry"
BOX_TIMEOUT_S = 2.0

# Racine du depot : trois niveaux au-dessus de app/interface/companion.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ROOT)))

# Cockpit projet du depot (`assets/web`) : c'est l'implementation unique des
# vues Projet / Conversation / Memoire / Outils. Elle est servie ici sous
# ``/cockpit/`` pour qu'une seule source de verite existe, au lieu de deux
# pages qui derivent l'une de l'autre. Liste blanche : aucun nom de fichier
# venu de la requete n'atteint le disque (meme discipline que ``web.py``).
COCKPIT_DIR = os.path.join(REPO_ROOT, "assets", "web")
COCKPIT_PREFIX = "/cockpit/"
COCKPIT_FILES = frozenset({"index.html", "app.css", "app.js", "miles.svg"})

# Fichiers publics de l'application : seuls ceux-la sont servis depuis le
# dossier du serveur. Sans cette liste, tout fichier du dossier (le code du
# serveur lui-meme) serait telechargeable ; ce n'est pas un secret, mais ce
# n'est pas non plus une ressource publique.
PUBLIC_FILES = frozenset({"index.html", "miles-bridge.js"})
PUBLIC_PREFIXES = ("assets/",)

# En-tetes retires avant de relayer vers MILES : ils decrivent la connexion
# cliente et non la requete elle-meme.
STRIP = {
    "host",
    "origin",
    "referer",
    "content-length",
    "connection",
    "accept-encoding",
    "transfer-encoding",
}

# Routes de l'agent, relayees telles quelles.
API_PREFIXES = ("/api/",)

# Routes SPA : tout chemin sans extension rend l'application.
SPA_ROUTES = {"", "device", "discover", "miles", "routines", "settings"}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".mp4": "video/mp4",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".map": "application/json; charset=utf-8",
}


def miles_url() -> str:
    return os.environ.get("COMPANION_MILES_URL", MILES_DEFAULT).rstrip("/")


def box_url() -> str:
    """URL du backend boitier (locale par defaut)."""
    return os.environ.get("COMPANION_BOX_URL", BOX_DEFAULT).rstrip("/")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "MilesCompanion"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- journal
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[companion] %s\n" % (fmt % args))

    # ----------------------------------------------------------- utilitaires
    def _resolve(self, relative: str) -> str | None:
        """Resout un chemin sous ROOT ; refuse toute sortie du dossier."""
        candidate = os.path.normpath(os.path.join(ROOT, relative))
        if candidate == ROOT or candidate.startswith(ROOT + os.sep):
            return candidate
        return None

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _serve_cockpit(self, path: str) -> None:
        """Servir le cockpit du depot sous ``/cockpit/`` (liste blanche)."""
        name = path[len(COCKPIT_PREFIX):] or "index.html"
        if name not in COCKPIT_FILES:
            return self._send_bytes(b"Not found", 404, "text/plain; charset=utf-8")
        full = os.path.join(COCKPIT_DIR, name)
        if not os.path.isfile(full):
            return self._send_bytes(
                b"Cockpit absent du depot", 404, "text/plain; charset=utf-8"
            )
        self._send_file(full)

    def _send_bytes(self, payload: bytes, status: int, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_file(self, full_path: str) -> None:
        ext = os.path.splitext(full_path)[1].lower()
        try:
            with open(full_path, "rb") as fh:
                payload = fh.read()
        except OSError:
            self._send_bytes(b"Fichier illisible", 500, "text/plain; charset=utf-8")
            return
        ctype = MIME.get(ext, "application/octet-stream")
        if ext == ".mp4":
            self._send_video(full_path, ctype)
            return
        self._send_bytes(payload, 200, ctype)

    def _send_video(self, full_path: str, ctype: str) -> None:
        """Gere les requetes Range : indispensable pour la lecture video."""
        size = os.path.getsize(full_path)
        range_header = self.headers.get("Range", "")
        start, end = 0, size - 1
        status = 200
        if range_header.startswith("bytes="):
            spec = range_header[len("bytes="):].split(",")[0].strip()
            first, _, last = spec.partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:
                    start = max(0, size - int(last))
            except ValueError:
                start, end = 0, size - 1
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(full_path, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # -------------------------------------------------------------- routage
    def _proxied(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in STRIP}
        target = miles_url() + self.path
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload, status = resp.read(), resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
                cookies = resp.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as exc:
            payload, status = exc.read(), exc.code
            ctype = exc.headers.get("Content-Type", "application/json")
            cookies = exc.headers.get_all("Set-Cookie") or []
        except Exception as exc:  # noqa: BLE001 - signale l'echec sans le masquer
            payload = (
                '{"error": "MILES injoignable", "detail": "%s"}' % type(exc).__name__
            ).encode()
            status, ctype, cookies = 502, "application/json", []
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _serve_box(self) -> None:
        """Relayer la telemetrie du boitier, ou dire qu'elle est indisponible.

        Le cockpit interroge cette route en meme origine : aucune requete
        inter-origine, et le navigateur n'apprend pas l'existence du port
        8095. Si le backend ne repond pas, on renvoie 503 **sans valeur** :
        le cockpit affichera « aucune valeur affichee » au lieu d'un chiffre
        fabrique (DEC-014, DEC-016 §4).
        """
        try:
            with urllib.request.urlopen(
                box_url() + BOX_PATH, timeout=BOX_TIMEOUT_S
            ) as resp:
                payload = resp.read()
                status = resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
        except Exception as exc:  # noqa: BLE001 - l'echec est le resultat attendu
            payload = (
                '{"etat": "indisponible", "detail": "%s"}' % type(exc).__name__
            ).encode()
            status, ctype = 503, "application/json; charset=utf-8"
        self._send_bytes(payload, status, ctype)

    def _serve_route(self, path: str) -> None:
        # Boitier : relai local dedie, avant le relai generique vers MILES.
        if path == "/api/box":
            return self._serve_box()

        # Les routes de l'agent vont vers MILES.
        if path.startswith(API_PREFIXES) or path in {
            "/session",
            "/status",
            "/provider",
            "/configure",
            "/message",
            "/memory",
            "/remember",
            "/forget",
            "/log",
            "/tools",
            "/tool",
            "/missions",
            "/logout",
        } or path.startswith("/mission/"):
            return self._proxied(self.command)

        # Cockpit projet : servi depuis le depot, jamais recopie.
        if path in ("/cockpit", "/projet", "/projet/"):
            # Redirection : les references relatives du cockpit (app.css,
            # app.js) n'ont de sens que sous la barre oblique finale.
            return self._redirect(COCKPIT_PREFIX)
        if path.startswith(COCKPIT_PREFIX):
            return self._serve_cockpit(path)

        relative = path.lstrip("/")
        if relative and (
            relative in PUBLIC_FILES or relative.startswith(PUBLIC_PREFIXES)
        ):
            full = self._resolve(relative)
            if full and os.path.isfile(full):
                return self._send_file(full)

        # Route SPA (sans extension) : rend l'application.
        if not os.path.splitext(relative)[1]:
            index = self._resolve("index.html")
            if index and os.path.isfile(index):
                return self._send_file(index)

        self._send_bytes(b"Not found", 404, "text/plain; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        self._serve_route(path)

    do_HEAD = do_GET  # noqa: N815

    def do_POST(self) -> None:  # noqa: N802
        self._proxied("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._proxied("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxied("DELETE")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serveur local Miles Companion")
    parser.add_argument("--port", type=int, default=int(os.environ.get("COMPANION_PORT", PORT_DEFAULT)))
    parser.add_argument("--host", default=os.environ.get("COMPANION_HOST", "127.0.0.1"))
    args = parser.parse_args(argv)
    if args.host not in ("127.0.0.1", "localhost"):
        print("Refus : Miles Companion n'ecoute que sur 127.0.0.1.", file=sys.stderr)
        return 2
    with Server((args.host, args.port), Handler) as httpd:
        print(
            "[companion] http://%s:%d -> MILES %s" % (args.host, args.port, miles_url()),
            flush=True,
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[companion] arret demande", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
