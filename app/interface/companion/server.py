"""Serveur local du site Miles Companion.

Le site est servi par la box, sur `127.0.0.1` par défaut. Il assure :

- la coque React (`dist/`) et les ressources locales (`assets/`) ;
- les comptes, rôles, sessions et le CSRF du site ;
- les mesures réelles (`/api/companion/sensors`) ;
- un relais **borné** vers MILES, avec une session ouverte côté serveur ;
- la page locale `/setup` (boucle locale uniquement) pour la clé d'un
  fournisseur.

Ce qui a changé par rapport au pont Readdy :

- plus de relais générique `/api/*` ni de `/api/box` public ;
- plus de jeton MILES demandé dans le navigateur ;
- plus de page pré-rendue : la coque est notre code.

Usage :
    python -m app.interface.companion.server
    python app/interface/companion/server.py --port 8787

Variables :
    COMPANION_HOST / COMPANION_PORT  écoute (défaut 127.0.0.1:8787)
    COMPANION_MILES_URL              MILES (défaut http://127.0.0.1:8080)
    COMPANION_BOX_URL                backend boîtier (défaut http://127.0.0.1:8095)
    COMPANION_MILES_TOKEN            jeton MILES (sinon MILES_WEB_AUTH_TOKEN)
    COMPANION_DB                     base SQLite (défaut data/companion.db)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import ipaddress
import json
import os
import re
import secrets
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

# Exécution directe (`python app/interface/companion/server.py`) : la racine
# du dépôt doit être importable pour `app.*`.
if __package__ in (None, ""):  # pragma: no cover - dépend du mode d'appel
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.interface.companion import (
    applets,
    audit,
    auth,
    pairing,
    providers,
    sensors,
    store as store_module,
)
from app.interface.companion.miles_client import MilesClient, MilesError, get_client, reset_client

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
DIST_DIR = ROOT / "dist"
ASSETS_DIR = ROOT / "assets"
COCKPIT_DIR = REPO_ROOT / "assets" / "web"
COCKPIT_PREFIX = "/cockpit/"
COCKPIT_FILES = frozenset({"index.html", "app.css", "app.js", "miles.svg"})
SETUP_TEMPLATE = ROOT / "setup.html"
SETUP_CSS = ROOT / "setup.css"

MILES_DEFAULT = "http://127.0.0.1:8080"
BOX_DEFAULT = "http://127.0.0.1:8095"
PORT_DEFAULT = 8787
COOKIE_NAME = "miles_companion_session"
COOKIE_DEVICE = "miles_companion_device"
DEVICE_TTL_S = 15_552_000  # 180 jours
PAIR_WINDOW_S = 300.0
PAIR_MAX_ATTEMPTS = 10
_PAIR_ATTEMPTS: dict[str, list[float]] = {}
_PAIR_LOCK = threading.Lock()
MAX_BODY = 1_048_576
# Un corps refusé pour taille reste dans la socket : on le vide jusqu'à cette
# limite pour garder la connexion keep-alive correctement tramée. Au-delà, on
# ferme la connexion et on l'annonce, plutôt que de lire sans borne.
MAX_DRAIN_BODY = 8 * MAX_BODY
SETUP_TOKEN_TTL_S = 600.0
CONFIRM_TTL_S = 60.0

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
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
}

#: Anciennes routes du cockpit `assets/web` (DEC-015). Elles gardent leur
#: propre session MILES ; elles ne sont accessibles qu'en boucle locale dans
#: cette phase et disparaîtront derrière l'authentification du site avant
#: toute ouverture LAN.
LEGACY_GET = re.compile(
    r"^/(session|status|provider|memory|tools|log|missions|mission/[A-Za-z0-9_-]{1,80}"
    r"|api/project|api/tasks)$"
)
LEGACY_POST = re.compile(
    r"^/(session|logout|message|remember|forget|tool|mission"
    r"|mission/[A-Za-z0-9_-]{1,80}/(answer|authorize|cancel)"
    r"|api/tasks/[A-Za-z0-9_-]{1,80}/status)$"
)

_SETUP_LOCK = threading.Lock()
_SETUP_TOKENS: dict[str, float] = {}


def _now() -> float:
    return time.time()


def _json_dumps(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def miles_url() -> str:
    return _env("COMPANION_MILES_URL", MILES_DEFAULT).rstrip("/")


def box_url() -> str:
    return _env("COMPANION_BOX_URL", BOX_DEFAULT).rstrip("/")


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host in ("localhost", "")


def _is_private_host(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return addr.is_private and not addr.is_loopback


def _safe_join(base: Path, relative: str) -> Optional[Path]:
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def _hash_payload(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _pair_attempt(ip: str) -> bool:
    """Limiter les essais d'appairage : dix par fenêtre de cinq minutes."""
    now = time.time()
    with _PAIR_LOCK:
        recent = [item for item in _PAIR_ATTEMPTS.get(ip, []) if now - item < PAIR_WINDOW_S]
        if len(recent) >= PAIR_MAX_ATTEMPTS:
            _PAIR_ATTEMPTS[ip] = recent
            return False
        recent.append(now)
        _PAIR_ATTEMPTS[ip] = recent
        return True


def _device_label(user_agent: str) -> str:
    """Nom par défaut d'un appareil, déduit de son agent utilisateur."""
    ua = (user_agent or "").lower()
    if "android" in ua:
        return "Téléphone Android"
    if "iphone" in ua:
        return "iPhone"
    if "ipad" in ua:
        return "iPad"
    return "Navigateur"


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "MilesCompanion/2"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- cycle
    def do_GET(self) -> None:  # noqa: N802
        self._started = time.monotonic()
        self._status_sent = 0
        self._session_cache: Optional[dict[str, Any]] = None
        self._session_loaded = False
        self._device_cache: Optional[dict[str, Any]] = None
        self._device_loaded = False
        try:
            self._route_get(self.path.split("?", 1)[0])
        except Exception as exc:  # noqa: BLE001 - jamais de trace au client
            self._send_json(500, {"error": "Erreur interne (%s)." % type(exc).__name__})
        finally:
            self._finish_access("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        self._started = time.monotonic()
        self._status_sent = 0
        self._session_cache = None
        self._session_loaded = False
        self._body_read = False
        try:
            self._route_post(self.path.split("?", 1)[0])
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": "Erreur interne (%s)." % type(exc).__name__})
        finally:
            self._drain_unread_body()
            self._finish_access("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._started = time.monotonic()
        self._status_sent = 0
        self._session_cache = None
        self._session_loaded = False
        self._body_read = False
        try:
            self._route_patch(self.path.split("?", 1)[0])
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": "Erreur interne (%s)." % type(exc).__name__})
        finally:
            self._drain_unread_body()
            self._finish_access("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._started = time.monotonic()
        self._status_sent = 0
        self._session_cache = None
        self._session_loaded = False
        self._body_read = False
        try:
            self._route_delete(self.path.split("?", 1)[0])
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": "Erreur interne (%s)." % type(exc).__name__})
        finally:
            self._drain_unread_body()
            self._finish_access("DELETE")

    def log_message(self, fmt: str, *args: Any) -> None:
        # Pas de journal verbeux sur stderr : le journal d'accès est en mémoire
        # (mode développeur) et ne contient ni cookie ni corps de requête.
        return

    def _finish_access(self, method: str) -> None:
        try:
            account = ""
            if self._session_loaded and self._session_cache:
                account = str(self._session_cache.get("username") or "")
            audit.record_access(
                method=method,
                path=self.path,
                status=self._status_sent or 0,
                account=account,
                duration_ms=(time.monotonic() - getattr(self, "_started", time.monotonic())) * 1000,
                client=self.client_address[0] if self.client_address else "",
            )
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------- réponses
    def _wants_html(self) -> bool:
        """Le client est-il un navigateur qui attend une page ?"""
        accept = (self.headers.get("Accept") or "").lower()
        return "text/html" in accept or "application/xhtml+xml" in accept

    def _security_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "style-src 'self'; script-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    def _send_json(self, status: int, payload: Any) -> None:
        body = _json_dumps(payload)
        self._status_sent = int(status)
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.close_connection:
            self.send_header("Connection", "close")
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_body(
        self,
        body: bytes,
        status: int = 200,
        ctype: str = "text/plain; charset=utf-8",
        cache: str = "no-store",
        extra: Optional[dict[str, str]] = None,
    ) -> None:
        self._status_sent = int(status)
        self.send_response(int(status))
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        if self.close_connection:
            self.send_header("Connection", "close")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_file(self, path: Path, *, cache: str = "no-store") -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json(404, {"error": "Fichier introuvable."})
            return
        ctype = MIME.get(path.suffix.lower(), "application/octet-stream")
        self._send_body(body, 200, ctype, cache)

    def _redirect(self, location: str) -> None:
        self._status_sent = 302
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()

    def _error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    # ------------------------------------------------------------ session
    def _cookie(self, name: str) -> str:
        header = self.headers.get("Cookie") or ""
        for part in header.split(";"):
            if "=" not in part:
                continue
            key, value = part.strip().split("=", 1)
            if key == name:
                return value
        return ""

    def _cookie_token(self) -> str:
        return self._cookie(COOKIE_NAME)

    def _device(self) -> Optional[dict[str, Any]]:
        """Appareil appairé par QR code, s'il est encore autorisé."""
        if self._device_loaded:
            return self._device_cache
        self._device_loaded = True
        token = self._cookie(COOKIE_DEVICE)
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = store_module.get_store().query_one(
            "SELECT * FROM paired_devices WHERE token_hash = ?", (token_hash,)
        )
        if row is None:
            return None
        self._device_cache = {
            "id": row["id"],
            "label": row["label"],
            "paired_at": row["created_at"],
            "last_seen_at": row["last_seen_at"],
        }
        if _now() - float(row["last_seen_at"]) > 60:
            store_module.get_store().execute(
                "UPDATE paired_devices SET last_seen_at = ? WHERE id = ?",
                (_now(), row["id"]),
            )
        return self._device_cache

    def _session(self) -> Optional[dict[str, Any]]:
        if self._session_loaded:
            return self._session_cache
        self._session_loaded = True
        self._session_cache = auth.resolve_session(self._cookie_token())
        return self._session_cache

    def _require_session(self) -> Optional[dict[str, Any]]:
        session = self._session()
        if session is None:
            self._error(401, "Session requise.")
            return None
        return session

    def _require_admin(self) -> Optional[dict[str, Any]]:
        session = self._require_session()
        if session is None:
            return None
        if session.get("role") != "admin":
            self._error(403, "Action réservée aux administrateurs.")
            return None
        return session

    def _origin_ok(self) -> bool:
        """Origine autorisée : boucle locale, origine configurée, ou même hôte.

        La comparaison avec l'en-tête `Host` est ce qui permet au site d'être
        utilisé depuis un téléphone sur le réseau local (`http://192.168.x:8787`)
        sans accepter une origine étrangère : un site attaquant présente une
        origine différente de l'hôte visé.
        """
        origin = (self.headers.get("Origin") or "").strip()
        if not origin:
            return True
        allowed = {
            "http://127.0.0.1:%d" % self.server.server_address[1],
            "http://localhost:%d" % self.server.server_address[1],
        }
        configured = _env("COMPANION_ORIGIN")
        if configured:
            allowed.add(configured.rstrip("/"))
        normalized = origin.rstrip("/")
        if normalized in {item.rstrip("/") for item in allowed}:
            return True
        parsed = urllib.parse.urlsplit(normalized)
        host_header = (self.headers.get("Host") or "").strip().lower()
        return bool(host_header) and parsed.scheme in ("http", "https") and parsed.netloc.lower() == host_header

    def _csrf_ok(self, session: dict[str, Any]) -> bool:
        token = self.headers.get("X-CSRF-Token") or ""
        return bool(token) and hmac.compare_digest(token, str(session.get("csrf_token") or ""))

    def _drain_unread_body(self) -> None:
        """Consommer un corps que la route n'a pas lu.

        En HTTP/1.1 keep-alive, un corps laissé dans la socket devient le
        début de la requête suivante : la méthode lue serait « {}GET » et le
        serveur répondrait 501 après une déconnexion suivie d'un
        rechargement. On vide donc ce qui reste, ou on ferme la connexion.
        """
        if getattr(self, "_body_read", True):
            return
        self._body_read = True
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            return
        if length <= 0:
            return
        if length > MAX_DRAIN_BODY:
            self.close_connection = True
            return
        try:
            self.rfile.read(length)
        except OSError:
            self.close_connection = True

    def _read_json(self) -> Optional[dict[str, Any]]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._error(400, "Corps JSON manquant.")
            return None
        if length > MAX_BODY:
            # Le corps n'a pas été lu : `_drain_unread_body` s'en charge en fin
            # de requête. Une taille au-delà de la limite de drainage ferme la
            # connexion, et la réponse doit le dire.
            if length > MAX_DRAIN_BODY:
                self.close_connection = True
            self._error(413, "Corps de requête trop volumineux.")
            return None
        self._body_read = True
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._error(400, "JSON invalide.")
            return None
        if not isinstance(payload, dict):
            self._error(400, "Objet JSON attendu.")
            return None
        return payload

    def _read_form(self) -> Optional[dict[str, str]]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 64_000:
            if length > MAX_DRAIN_BODY:
                self.close_connection = True
            return None
        self._body_read = True
        raw = self.rfile.read(length).decode("utf-8", "replace")
        parsed = urllib.parse.parse_qs(raw, keep_blank_values=True)
        return {key: values[0] for key, values in parsed.items()}

    def _proxy_legacy(self, method: str) -> None:
        """Relais du cockpit historique (boucle locale uniquement)."""
        if not _is_loopback(self.client_address[0]):
            self._error(404, "Route inconnue.")
            return
        length = int(self.headers.get("Content-Length") or 0)
        self._body_read = True
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() in ("content-type", "cookie", "x-miles-session", "x-miles-csrf")
        }
        req = urllib.request.Request(
            miles_url() + self.path, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload, status = resp.read(), resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
                cookies = resp.headers.get_all("Set-Cookie") or []
        except urllib.error.HTTPError as exc:
            payload, status = exc.read(), exc.code
            ctype = exc.headers.get("Content-Type", "application/json")
            cookies = exc.headers.get_all("Set-Cookie") or []
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                502,
                {"error": "MILES injoignable", "detail": type(exc).__name__},
            )
            return
        self._status_sent = int(status)
        self.send_response(int(status))
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    # ------------------------------------------------------------ routage
    def _route_get(self, path: str) -> None:
        if path == "/healthz":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/setup":
            self._serve_setup()
            return
        if path == "/setup.css":
            self._send_file(SETUP_CSS, cache="no-store")
            return
        if path == "/manifest.webmanifest":
            self._serve_dist_file("manifest.webmanifest")
            return
        if path == "/sw.js":
            self._serve_dist_file("sw.js", extra={"Service-Worker-Allowed": "/"})
            return
        if path.startswith("/icons/"):
            self._serve_icon(path)
            return
        if path.startswith("/api/companion/"):
            self._api_get(path)
            return
        if path.startswith("/assets/"):
            self._serve_shared_asset(path)
            return
        if path.startswith("/app/"):
            self._serve_dist_asset(path)
            return
        if path in ("/cockpit", "/projet", "/projet/"):
            self._redirect(COCKPIT_PREFIX)
            return
        if path.startswith(COCKPIT_PREFIX):
            self._serve_cockpit(path)
            return
        # `/missions` existe aussi comme page de l'application : un navigateur
        # qui demande du HTML reçoit la coque, un client d'API garde le relais.
        if (
            LEGACY_GET.match(path)
            and _is_loopback(self.client_address[0])
            and not self._wants_html()
        ):
            self._proxy_legacy("GET")
            return
        if path.startswith("/api/"):
            self._error(404, "Route API inconnue.")
            return
        if path == "/" or not Path(path).suffix:
            self._serve_app_shell()
            return
        self._error(404, "Ressource introuvable.")

    def _route_post(self, path: str) -> None:
        if path == "/setup":
            self._post_setup()
            return
        if path.startswith("/api/companion/"):
            self._api_post(path)
            return
        if LEGACY_POST.match(path) and _is_loopback(self.client_address[0]):
            self._proxy_legacy("POST")
            return
        self._error(404, "Route inconnue.")

    def _route_patch(self, path: str) -> None:
        if path.startswith("/api/companion/"):
            if not self._origin_ok():
                self._error(403, "Origine refusée.")
                return
            session = self._require_admin()
            if session is None:
                return
            if not self._csrf_ok(session):
                self._error(403, "Jeton CSRF absent ou invalide.")
                return
            self._api_patch(path, session)
            return
        self._error(404, "Route inconnue.")

    def _route_delete(self, path: str) -> None:
        if path.startswith("/api/companion/"):
            if not self._origin_ok():
                self._error(403, "Origine refusée.")
                return
            session = self._require_admin()
            if session is None:
                return
            if not self._csrf_ok(session):
                self._error(403, "Jeton CSRF absent ou invalide.")
                return
            self._api_delete(path, session)
            return
        self._error(404, "Route inconnue.")

    # ------------------------------------------------------------ statique
    def _serve_shared_asset(self, path: str) -> None:
        relative = path[len("/assets/"):]
        target = _safe_join(ASSETS_DIR, relative)
        if target is None or not target.is_file() or target.suffix.lower() not in MIME:
            self._error(404, "Ressource introuvable.")
            return
        cache = "public, max-age=86400" if target.suffix.lower() in (".woff2", ".woff", ".ttf", ".mp4", ".jpg", ".png", ".webp") else "no-store"
        self._send_file(target, cache=cache)

    def _serve_dist_asset(self, path: str) -> None:
        relative = path[len("/app/"):]
        target = _safe_join(DIST_DIR / "app", relative)
        if target is None or not target.is_file() or target.suffix.lower() not in MIME:
            self._error(404, "Ressource introuvable.")
            return
        self._send_file(target, cache="public, max-age=31536000, immutable")

    def _serve_dist_file(
        self, name: str, *, cache: str = "no-store", extra: Optional[dict[str, str]] = None
    ) -> None:
        target = DIST_DIR / name
        if not target.is_file():
            self._error(404, "Ressource introuvable.")
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._error(404, "Ressource introuvable.")
            return
        ctype = MIME.get(target.suffix.lower(), "application/octet-stream")
        self._send_body(body, 200, ctype, cache, extra=extra)

    def _serve_icon(self, path: str) -> None:
        relative = path[len("/icons/"):]
        target = _safe_join(DIST_DIR / "icons", relative)
        if target is None or not target.is_file() or target.suffix.lower() != ".png":
            self._error(404, "Ressource introuvable.")
            return
        self._send_file(target, cache="public, max-age=604800")

    def _serve_app_shell(self) -> None:
        index = DIST_DIR / "index.html"
        if not index.is_file():
            self._send_body(
                (
                    "<!DOCTYPE html><html lang='fr'><meta charset='utf-8'>"
                    "<title>Miles Companion — build absent</title>"
                    "<body style='font:16px system-ui;padding:40px;background:#0a0d12;color:#e6e8ee'>"
                    "<h1>Build absent</h1><p>Exécutez <code>npm ci &amp;&amp; npm run build</code> "
                    "dans <code>app/interface/companion/frontend</code>.</p></body></html>"
                ).encode("utf-8"),
                503,
                "text/html; charset=utf-8",
            )
            return
        self._send_file(index, cache="no-store")

    def _serve_cockpit(self, path: str) -> None:
        name = path[len(COCKPIT_PREFIX):] or "index.html"
        if name not in COCKPIT_FILES:
            self._error(404, "Ressource introuvable.")
            return
        target = COCKPIT_DIR / name
        if not target.is_file():
            self._error(404, "Cockpit absent du dépôt.")
            return
        self._send_file(target, cache="no-store")

    # -------------------------------------------------------------- setup
    def _serve_setup(self) -> None:
        if not _is_loopback(self.client_address[0]):
            self._error(403, "La connexion d'un fournisseur se fait sur la box (127.0.0.1).")
            return
        self._send_body(
            self._render_setup(self._new_setup_token(), "").encode("utf-8"),
            200,
            "text/html; charset=utf-8",
        )

    def _new_setup_token(self) -> str:
        token = secrets.token_urlsafe(32)
        with _SETUP_LOCK:
            for key, expires in list(_SETUP_TOKENS.items()):
                if expires <= _now():
                    _SETUP_TOKENS.pop(key, None)
            _SETUP_TOKENS[token] = _now() + SETUP_TOKEN_TTL_S
        return token

    def _render_setup(self, token: str, message: str) -> str:
        template = SETUP_TEMPLATE.read_text(encoding="utf-8")
        options = "".join(
            '<option value="%s">%s</option>' % (item["id"], item["label"])
            for item in providers.catalog()
            if item["requires_key"]
        )
        return (
            template.replace("{{CSRF}}", token)
            .replace("{{PROVIDERS}}", options)
            .replace("{{MODEL}}", "")
            .replace("{{MESSAGE}}", message)
        )

    def _post_setup(self) -> None:
        if not _is_loopback(self.client_address[0]):
            self._error(403, "La connexion d'un fournisseur se fait sur la box (127.0.0.1).")
            return
        if not self._origin_ok():
            self._error(403, "Origine refusée.")
            return
        form = self._read_form()
        if form is None:
            self._error(400, "Formulaire invalide.")
            return
        token = form.get("csrf", "")
        with _SETUP_LOCK:
            expires = _SETUP_TOKENS.pop(token, None)
        if expires is None or expires <= _now():
            self._send_body(
                self._render_setup(
                    self._new_setup_token(),
                    "Jeton de formulaire expiré : recommencez.",
                ).encode(),
                400,
                "text/html; charset=utf-8",
            )
            return
        provider = form.get("provider", "")
        api_key = form.get("api_key", "")
        model = form.get("model", "")
        try:
            result = providers.save_key(provider, api_key, model)
        except (ValueError, OSError) as exc:
            audit.log_event(
                "provider.key",
                target=provider,
                outcome="refus",
                detail={"raison": str(exc)},
            )
            self._send_body(
                self._render_setup(self._new_setup_token(), "Refus : %s" % exc).encode(),
                400,
                "text/html; charset=utf-8",
            )
            return
        audit.log_event(
            "provider.key",
            target=provider,
            outcome="ok",
            detail={"action": result.get("action")},
        )
        self._send_body(
            self._render_setup(
                self._new_setup_token(),
                "Clé enregistrée pour %s. Redémarrez miles.py pour l'activer."
                % providers.LABELS.get(provider, provider),
            ).encode(),
            200,
            "text/html; charset=utf-8",
        )

    # ---------------------------------------------------------------- API
    def _api_get(self, path: str) -> None:
        suffix = path[len("/api/companion/"):]

        if suffix in ("auth/me", "me"):
            session = self._require_session()
            if session is None:
                return
            account = auth.get_account(session["account_id"]) or {}
            prefs = auth.get_preferences(session["account_id"])
            self._send_json(
                200,
                {
                    "account": account,
                    "preferences": prefs,
                    "csrf_token": session["csrf_token"],
                    "miles_configured": get_client().available,
                    "device": self._device(),
                    "box_name": pairing.get_identity()["name"],
                },
            )
            return

        if suffix == "health":
            session = self._require_session()
            if session is None:
                return
            client = get_client()
            result: dict[str, Any] = {
                "site": "ok",
                "miles_configured": client.available,
                "miles": None,
            }
            if client.available:
                try:
                    result["miles"] = client.status()
                except MilesError as exc:
                    result["miles"] = {"error": exc.message}
            self._send_json(200, result)
            return

        session = self._require_session()
        if session is None:
            return

        if suffix == "sensors":
            prefs = auth.get_preferences(session["account_id"])
            self._send_json(
                200,
                sensors.build_snapshot(dev_mode=bool(prefs["dev_mode"]), box_url=box_url()),
            )
            return

        if suffix == "applets":
            prefs = auth.get_preferences(session["account_id"])
            self._send_json(
                200,
                {"applets": applets.visible(session["role"], bool(prefs["dev_mode"]))},
            )
            return

        if suffix == "providers":
            self._send_json(
                200,
                {"providers": providers.catalog(), "status": providers.status()},
            )
            return

        if suffix == "status":
            client = get_client()
            payload: dict[str, Any] = {
                "provider": providers.status(),
                "miles": None,
                "box": sensors.fetch_box(box_url()),
            }
            if client.available:
                try:
                    payload["miles"] = client.status()
                except MilesError as exc:
                    payload["miles"] = {"error": exc.message}
            self._send_json(200, payload)
            return

        if suffix == "missions":
            client = get_client()
            if not client.available:
                self._send_json(503, {"available": False, "error": "MILES non configuré sur la box."})
                return
            try:
                payload = client.missions()
            except MilesError as exc:
                self._send_json(exc.status, {"available": False, "error": exc.message})
                return
            self._send_json(200, {"available": True, **payload})
            return

        if suffix.startswith("missions/"):
            mission_id = suffix[len("missions/"):].strip("/")
            if not re.match(r"^[A-Za-z0-9_-]{1,80}$", mission_id):
                self._error(404, "Mission inconnue.")
                return
            client = get_client()
            if not client.available:
                self._send_json(503, {"available": False, "error": "MILES non configuré sur la box."})
                return
            try:
                payload = client.mission(mission_id)
            except MilesError as exc:
                self._send_json(exc.status, {"available": False, "error": exc.message})
                return
            self._send_json(200, {"available": True, "mission": payload})
            return

        if suffix == "memory":
            client = get_client()
            if not client.available:
                self._send_json(503, {"available": False, "error": "MILES non configuré sur la box."})
                return
            try:
                payload = client.request("GET", "/memory")[1]
            except MilesError as exc:
                self._send_json(exc.status, {"available": False, "error": exc.message})
                return
            memories = payload.get("memories") if isinstance(payload, dict) else None
            if memories is None and isinstance(payload, dict):
                memories = payload.get("value")
            self._send_json(200, {"available": True, "memories": memories or []})
            return

        if suffix == "routines":
            rows = store_module.get_store().query(
                "SELECT * FROM routines ORDER BY created_at DESC"
            )
            self._send_json(200, {"routines": [dict(row) for row in rows]})
            return

        if suffix == "devices":
            if session["role"] != "admin":
                self._error(403, "Action réservée aux administrateurs.")
                return
            rows = store_module.get_store().query(
                "SELECT * FROM paired_devices ORDER BY created_at DESC"
            )
            self._send_json(
                200,
                {
                    "devices": [
                        {
                            "id": row["id"],
                            "label": row["label"],
                            "paired_at": row["created_at"],
                            "last_seen_at": row["last_seen_at"],
                        }
                        for row in rows
                    ]
                },
            )
            return

        if suffix == "journal":
            prefs = auth.get_preferences(session["account_id"])
            if not prefs["dev_mode"]:
                self._send_json(403, {"error": "Le journal est accessible en mode développeur."})
                return
            limit = 100
            events = audit.list_events(
                limit=limit,
                account_id=None if session["role"] == "admin" else session["account_id"],
            )
            self._send_json(200, {"events": events, "limit": limit})
            return

        if suffix == "access-log":
            prefs = auth.get_preferences(session["account_id"])
            if not prefs["dev_mode"]:
                self._send_json(403, {"error": "Le journal est accessible en mode développeur."})
                return
            self._send_json(200, {"entries": audit.list_access(200)})
            return

        if suffix == "accounts":
            if session["role"] != "admin":
                self._error(403, "Action réservée aux administrateurs.")
                return
            self._send_json(200, {"accounts": auth.list_accounts()})
            return

        self._error(404, "Route inconnue.")

    def _api_post(self, path: str) -> None:
        suffix = path[len("/api/companion/"):]
        if not self._origin_ok():
            self._error(403, "Origine refusée.")
            return

        if suffix == "auth/login":
            self._post_login()
            return

        if suffix == "pair":
            self._post_pair()
            return

        session = self._require_session()
        if session is None:
            return
        if not self._csrf_ok(session):
            self._error(403, "Jeton CSRF absent ou invalide.")
            return

        if suffix == "auth/logout":
            auth.revoke_session(self._cookie_token())
            audit.log_event("auth.logout", account=session, outcome="ok")
            self._send_body(
                _json_dumps({"ok": True}),
                200,
                "application/json; charset=utf-8",
                extra={
                    "Set-Cookie": "%s=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
                    % COOKIE_NAME
                },
            )
            return

        if suffix == "password":
            data = self._read_json()
            if data is None:
                return
            self._post_password(session, data)
            return

        if suffix == "dev-mode":
            data = self._read_json()
            if data is None:
                return
            enabled = bool(data.get("enabled"))
            prefs = auth.set_dev_mode(session["account_id"], enabled)
            audit.log_event(
                "dev_mode",
                account=session,
                target="actif" if enabled else "inactif",
                outcome="ok",
            )
            self._send_json(200, {"ok": True, "preferences": prefs})
            return

        if suffix == "message":
            data = self._read_json()
            if data is None:
                return
            message = str(data.get("message") or "").strip()
            if not message:
                self._error(400, "Message vide.")
                return
            client = get_client()
            if not client.available:
                self._send_json(503, {"error": "MILES non configuré sur la box."})
                return
            try:
                status, payload = client.request("POST", "/message", {"message": message[:4000]})
            except MilesError as exc:
                self._send_json(exc.status, {"error": exc.message})
                return
            audit.log_event("chat.message", account=session, outcome="ok")
            self._send_json(status, payload)
            return

        if suffix == "routines":
            data = self._read_json()
            if data is None:
                return
            name = str(data.get("name") or "").strip()[:80]
            objective = str(data.get("objective") or "").strip()[:2000]
            if not name or not objective:
                self._error(400, "Nom et objectif requis.")
                return
            routine_id = secrets.token_hex(8)
            store_module.get_store().execute(
                "INSERT INTO routines (id, name, objective, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (routine_id, name, objective, session["account_id"], _now()),
            )
            audit.log_event("routine.create", account=session, target=routine_id, outcome="ok")
            self._send_json(201, {"id": routine_id})
            return

        if suffix == "actions/prepare":
            data = self._read_json()
            if data is None:
                return
            self._action_prepare(session, data)
            return

        if suffix == "actions/execute":
            data = self._read_json()
            if data is None:
                return
            self._action_execute(session, data)
            return

        if suffix == "accounts":
            if session["role"] != "admin":
                self._error(403, "Action réservée aux administrateurs.")
                return
            data = self._read_json()
            if data is None:
                return
            self._post_account(data, session)
            return

        self._error(404, "Route inconnue.")

    def _api_patch(self, path: str, session: dict[str, Any]) -> None:
        suffix = path[len("/api/companion/"):]
        match = re.match(r"^accounts/([a-f0-9]{8,40})$", suffix)
        if not match:
            self._error(404, "Route inconnue.")
            return
        data = self._read_json()
        if data is None:
            return
        account_id = match.group(1)
        try:
            account = auth.update_account(
                account_id,
                role=data.get("role"),
                disabled=data.get("disabled"),
                display_name=data.get("display_name"),
            )
        except auth.AuthError as exc:
            self._error(400, str(exc))
            return
        audit.log_event(
            "account.update",
            account=session,
            target=account["username"],
            outcome="ok",
            detail={"role": account["role"], "disabled": account["disabled"]},
        )
        self._send_json(200, {"account": account})

    def _api_delete(self, path: str, session: dict[str, Any]) -> None:
        suffix = path[len("/api/companion/"):]
        match = re.match(r"^accounts/([a-f0-9]{8,40})$", suffix)
        if match:
            account_id = match.group(1)
            if account_id == session["account_id"]:
                self._error(400, "Impossible de supprimer son propre compte.")
                return
            target = auth.get_account(account_id)
            try:
                auth.delete_account(account_id)
            except auth.AuthError as exc:
                self._error(400, str(exc))
                return
            audit.log_event(
                "account.delete",
                account=session,
                target=(target or {}).get("username", account_id),
                outcome="ok",
            )
            self._send_json(200, {"ok": True})
            return
        match = re.match(r"^routines/([a-f0-9]{8,40})$", suffix)
        if match:
            routine_id = match.group(1)
            store_module.get_store().execute("DELETE FROM routines WHERE id = ?", (routine_id,))
            audit.log_event("routine.delete", account=session, target=routine_id, outcome="ok")
            self._send_json(200, {"ok": True})
            return
        match = re.match(r"^devices/([a-f0-9]{8,40})$", suffix)
        if match:
            device_id = match.group(1)
            row = store_module.get_store().query_one(
                "SELECT * FROM paired_devices WHERE id = ?", (device_id,)
            )
            if row is None:
                self._error(404, "Appareil inconnu.")
                return
            store_module.get_store().execute(
                "DELETE FROM paired_devices WHERE id = ?", (device_id,)
            )
            audit.log_event(
                "device.revoke", account=session, target=row["label"], outcome="ok"
            )
            self._send_json(200, {"ok": True})
            return
        self._error(404, "Route inconnue.")

    # ------------------------------------------------------------- comptes
    def _post_login(self) -> None:
        data = self._read_json()
        if data is None:
            return
        username = str(data.get("username") or "").strip().lower()
        password = str(data.get("password") or "")
        ip = self.client_address[0] if self.client_address else ""
        if auth.login_locked(username, ip):
            audit.log_event("auth.login", target=username, outcome="verrouillé")
            self._send_json(429, {"error": "Trop de tentatives : réessayez dans 15 minutes."})
            return
        account = auth.authenticate(username, password)
        if account is None:
            auth.record_login_failure(username, ip)
            audit.log_event("auth.login", target=username, outcome="refus")
            self._send_json(401, {"error": "Identifiant ou mot de passe incorrect."})
            return
        auth.clear_login_failures(username, ip)
        token, csrf, expires = auth.create_session(
            account["id"],
            ip=ip,
            user_agent=self.headers.get("User-Agent") or "",
        )
        secure = _env("COMPANION_SECURE_COOKIES") == "1"
        cookie = "%s=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d%s" % (
            COOKIE_NAME,
            token,
            int(expires - _now()),
            "; Secure" if secure else "",
        )
        audit.log_event("auth.login", account=account, outcome="ok")
        self._send_body(
            _json_dumps(
                {
                    "ok": True,
                    "account": account,
                    "csrf_token": csrf,
                    "expires_at": expires,
                }
            ),
            200,
            "application/json; charset=utf-8",
            extra={"Set-Cookie": cookie},
        )

    def _post_password(self, session: dict[str, Any], data: dict[str, Any]) -> None:
        current = str(data.get("current_password") or "")
        new = str(data.get("new_password") or "")
        row = store_module.get_store().query_one(
            "SELECT password_hash FROM accounts WHERE id = ?",
            (session["account_id"],),
        )
        if row is None or not auth.verify_password(current, row["password_hash"]):
            audit.log_event("account.password", account=session, outcome="refus")
            self._error(400, "Mot de passe actuel incorrect.")
            return
        try:
            auth.set_password(session["account_id"], new)
        except auth.AuthError as exc:
            self._error(400, str(exc))
            return
        audit.log_event("account.password", account=session, outcome="ok")
        self._send_json(200, {"ok": True, "reauth": True})

    def _post_account(self, data: dict[str, Any], session: dict[str, Any]) -> None:
        try:
            account = auth.create_account(
                str(data.get("username") or ""),
                str(data.get("password") or ""),
                role=str(data.get("role") or "user"),
                display_name=str(data.get("display_name") or ""),
            )
        except auth.AuthError as exc:
            self._error(400, str(exc))
            return
        audit.log_event(
            "account.create",
            account=session,
            target=account["username"],
            outcome="ok",
            detail={"role": account["role"]},
        )
        self._send_json(201, {"account": account})

    # ----------------------------------------------------------- appairage
    def _post_pair(self) -> None:
        """Associer cet appareil à la box avec le jeton du QR code.

        Aucun compte n'est requis : le jeton ne prouve que la possession du
        boîtier physique. La session reste obligatoire pour toute action.
        """
        if not self._origin_ok():
            self._error(403, "Origine refusée.")
            return
        data = self._read_json()
        if data is None:
            return
        token = str(data.get("token") or "").strip()
        if not token or len(token) > 200:
            self._error(400, "Jeton d'appairage manquant.")
            return
        ip = self.client_address[0] if self.client_address else ""
        if not _pair_attempt(ip):
            audit.log_event("device.pair", target=ip, outcome="limite")
            self._send_json(429, {"error": "Trop de tentatives : réessayez dans 5 minutes."})
            return
        identity = pairing.get_identity()
        if not pairing.token_matches(token, identity):
            audit.log_event("device.pair", target=ip, outcome="refus")
            self._send_json(401, {"error": "QR code inconnu ou révoqué."})
            return
        user_agent = self.headers.get("User-Agent") or ""
        label = str(data.get("label") or "").strip()[:40] or _device_label(user_agent)
        device_id = secrets.token_hex(8)
        device_token = secrets.token_urlsafe(32)
        now = _now()
        store_module.get_store().execute(
            "INSERT INTO paired_devices "
            "(id, label, token_hash, created_at, last_seen_at, ip_hash, ua_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                device_id,
                label,
                hashlib.sha256(device_token.encode("utf-8")).hexdigest(),
                now,
                now,
                hashlib.sha256(ip.encode("utf-8")).hexdigest() if ip else "",
                hashlib.sha256(user_agent.encode("utf-8")).hexdigest(),
            ),
        )
        audit.log_event(
            "device.pair",
            target=label,
            outcome="ok",
            detail={"box": identity["box_id"]},
        )
        secure = _env("COMPANION_SECURE_COOKIES") == "1"
        cookie = "%s=%s; HttpOnly; SameSite=Lax; Path=/; Max-Age=%d%s" % (
            COOKIE_DEVICE,
            device_token,
            DEVICE_TTL_S,
            "; Secure" if secure else "",
        )
        self._send_body(
            _json_dumps(
                {
                    "ok": True,
                    "box": {"id": identity["box_id"], "name": identity["name"]},
                    "device": {"id": device_id, "label": label, "paired_at": now},
                }
            ),
            200,
            "application/json; charset=utf-8",
            extra={"Set-Cookie": cookie},
        )

    # ------------------------------------------------------------ actions
    def _action_prepare(self, session: dict[str, Any], data: dict[str, Any]) -> None:
        action_id = str(data.get("action") or "").strip()
        payload = data.get("payload")
        if not isinstance(payload, dict):
            self._error(400, "Charge utile invalide.")
            return
        item = applets.get(action_id)
        if item is None:
            self._error(404, "Action inconnue.")
            return
        if item["role"] == "admin" and session["role"] != "admin":
            self._error(403, "Action réservée aux administrateurs.")
            return
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = _now()
        db = store_module.get_store()
        db.execute("DELETE FROM confirmation_tokens WHERE expires_at <= ?", (now,))
        db.execute(
            "INSERT INTO confirmation_tokens "
            "(token_hash, account_id, action_id, payload_hash, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                token_hash,
                session["account_id"],
                action_id,
                _hash_payload(payload),
                now,
                now + CONFIRM_TTL_S,
            ),
        )
        audit.log_event(
            "action.prepare",
            account=session,
            target=action_id,
            outcome="ok",
        )
        self._send_json(
            200,
            {
                "token": token,
                "expires_at": now + CONFIRM_TTL_S,
                "confirmation": item.get("confirmation") or "Confirmer cette action ?",
            },
        )

    def _action_execute(self, session: dict[str, Any], data: dict[str, Any]) -> None:
        token = str(data.get("token") or "")
        payload = data.get("payload")
        if not token or not isinstance(payload, dict):
            self._error(400, "Jeton ou charge utile manquant.")
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db = store_module.get_store()
        row = db.query_one(
            "SELECT * FROM confirmation_tokens WHERE token_hash = ?", (token_hash,)
        )
        if row is None:
            self._error(403, "Jeton de confirmation inconnu.")
            return
        if row["used_at"] is not None:
            self._error(403, "Jeton déjà utilisé.")
            return
        if row["account_id"] != session["account_id"]:
            self._error(403, "Jeton lié à un autre compte.")
            return
        if float(row["expires_at"]) <= _now():
            self._error(403, "Jeton expiré : recommencez.")
            return
        if row["payload_hash"] != _hash_payload(payload):
            self._error(403, "Charge utile différente de celle confirmée.")
            return
        db.execute(
            "UPDATE confirmation_tokens SET used_at = ? WHERE token_hash = ?",
            (_now(), token_hash),
        )
        action_id = row["action_id"]
        try:
            result = self._execute_action(action_id, payload, session)
        except (MilesError, ValueError, auth.AuthError) as exc:
            message = getattr(exc, "message", str(exc))
            audit.log_event("action.execute", account=session, target=action_id, outcome="refus", detail={"raison": message})
            status = getattr(exc, "status", 400)
            self._send_json(status, {"error": message})
            return
        audit.log_event("action.execute", account=session, target=action_id, outcome="ok")
        self._send_json(200, {"ok": True, "result": result})

    def _execute_action(
        self, action_id: str, payload: dict[str, Any], session: dict[str, Any]
    ) -> Any:
        client = get_client()
        if action_id == "mission.create":
            self._require_miles(client)
            objective = str(payload.get("objective") or "").strip()
            if not objective:
                raise ValueError("Objectif manquant.")
            return client.request("POST", "/mission", {"objective": objective[:2000]})[1]
        if action_id == "routine.run":
            routine_id = str(payload.get("routine_id") or "")
            row = store_module.get_store().query_one(
                "SELECT * FROM routines WHERE id = ? AND enabled = 1", (routine_id,)
            )
            if row is None:
                raise ValueError("Routine inconnue ou désactivée.")
            self._require_miles(client)
            result = client.request("POST", "/mission", {"objective": row["objective"]})[1]
            store_module.get_store().execute(
                "UPDATE routines SET last_run_at = ? WHERE id = ?", (_now(), routine_id)
            )
            return result
        if action_id == "mission.answer":
            self._require_miles(client)
            mission_id = self._valid_mission_id(payload)
            answer = str(payload.get("answer") or "").strip()
            if not answer:
                raise ValueError("Réponse vide.")
            return client.request(
                "POST", "/mission/%s/answer" % mission_id, {"answer": answer[:4000]}
            )[1]
        if action_id == "mission.authorize":
            self._require_miles(client)
            mission_id = self._valid_mission_id(payload)
            approval = str(payload.get("approval_token") or "")
            if not approval:
                raise ValueError("Jeton d'approbation manquant (rechargez la mission).")
            return client.request(
                "POST",
                "/mission/%s/authorize" % mission_id,
                {"approval_token": approval, "approved": bool(payload.get("approved"))},
            )[1]
        if action_id == "mission.cancel":
            self._require_miles(client)
            mission_id = self._valid_mission_id(payload)
            return client.request("POST", "/mission/%s/cancel" % mission_id, {})[1]
        if action_id == "provider.activate":
            return providers.activate(str(payload.get("provider") or ""))
        if action_id == "provider.test":
            return providers.test(str(payload.get("provider") or ""))
        raise ValueError("Action non implémentée.")

    @staticmethod
    def _valid_mission_id(payload: dict[str, Any]) -> str:
        mission_id = str(payload.get("mission_id") or "")
        if not re.match(r"^[A-Za-z0-9_-]{1,80}$", mission_id):
            raise ValueError("Identifiant de mission invalide.")
        return mission_id

    @staticmethod
    def _require_miles(client: MilesClient) -> None:
        if not client.available:
            raise MilesError("MILES non configuré sur la box.", 503)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _lan_allowed() -> bool:
    """Ouverture LAN : triple condition explicite, jamais par accident.

    L'audit indépendant n'a pas encore eu lieu (DEC-019) : le mode LAN reste
    donc refusé même si les deux variables sont présentes, sauf preuve
    explicite `COMPANION_LAN_AUDITED=1`.
    """
    if _env("COMPANION_ALLOW_LAN") != "1":
        return False
    if _env("COMPANION_LAN_AUDITED") != "1":
        return False
    return _is_private_host(_env("COMPANION_LAN_HOST"))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Site local Miles Companion")
    parser.add_argument("--host", default=os.environ.get("COMPANION_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("COMPANION_PORT", PORT_DEFAULT)))
    parser.add_argument("--lan", action="store_true", help="écoute LAN (audit B exigé)")
    args = parser.parse_args(argv)

    host = args.host
    if args.lan:
        if not _lan_allowed():
            print(
                "Refus : l'écoute LAN exige COMPANION_ALLOW_LAN=1, "
                "COMPANION_LAN_HOST=<adresse privée> et COMPANION_LAN_AUDITED=1 "
                "(audit indépendant). Le défaut reste 127.0.0.1.",
                file=sys.stderr,
            )
            return 2
        host = _env("COMPANION_LAN_HOST")
    elif not _is_loopback(host):
        print("Refus : Miles Companion n'ecoute que sur 127.0.0.1 (ou --lan audite).", file=sys.stderr)
        return 2

    with Server((host, args.port), Handler) as httpd:
        client = get_client()
        print(
            "[companion] http://%s:%d · MILES %s · jeton MILES %s"
            % (host, args.port, miles_url(), "configuré" if client.available else "absent"),
            flush=True,
        )
        qr_host = pairing.detect_lan_host() if _is_loopback(host) else host
        for line in pairing.startup_lines(qr_host, args.port):
            print(line, flush=True)
        if not store_module.get_store().query_one("SELECT 1 FROM accounts LIMIT 1"):
            print(
                "[companion] aucun compte : créez le premier administrateur avec\n"
                "  python -m app.interface.companion.auth add <identifiant> --role admin",
                flush=True,
            )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[companion] arret demande", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
