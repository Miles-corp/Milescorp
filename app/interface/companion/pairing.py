"""Identité de la box et appairage d'un appareil par QR code.

Le QR est imprimé au dos du boîtier. Il contient une URL d'appairage :

    http://<box>:8787/appairer#t=<jeton>

Le jeton est placé dans le **fragment** (`#…`) : il n'est donc jamais envoyé
au serveur dans l'URL, jamais écrit dans le journal d'accès et jamais transmis
par l'en-tête `Referer`. Il est comparé à temps constant par le serveur.

Appairer un appareil ne donne **aucun accès au compte** : le serveur délivre
seulement un cookie d'appareil (révocable depuis la box), et la connexion à
l'interface reste protégée par le nom d'utilisateur et le mot de passe.

L'identité (dont le jeton) vit dans `data/box_identity.json`, ignoré par Git
et lisible par le seul compte qui fait tourner la box. La CLI permet de
regénérer le QR ou de révoquer l'ancien jeton :

    python -m app.interface.companion.pairing show
    python -m app.interface.companion.pairing qr --out data/box-001-qr.png
    python -m app.interface.companion.pairing rotate
"""

from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_IDENTITY = ROOT.parents[2] / "data" / "box_identity.json"
PAIR_PATH = "/appairer"
DEFAULT_PORT = 8787
DEFAULT_NAME = "Miles Box"
TOKEN_BYTES = 32
BOX_ID_BYTES = 6

_IDENTITY: Optional[dict[str, Any]] = None
_IDENTITY_LOCK = threading.RLock()


def identity_path() -> Path:
    override = os.environ.get("COMPANION_IDENTITY", "").strip()
    return Path(override) if override else DEFAULT_IDENTITY


def _new_identity(name: str) -> dict[str, Any]:
    return {
        "box_id": secrets.token_hex(BOX_ID_BYTES),
        "name": (name or DEFAULT_NAME).strip()[:60] or DEFAULT_NAME,
        "token": secrets.token_urlsafe(TOKEN_BYTES),
        "created_at": time.time(),
    }


def _write(identity: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:  # Windows : le mode POSIX n'existe pas
        pass
    temporary.replace(path)


def load_identity() -> Optional[dict[str, Any]]:
    path = identity_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if not payload.get("token") or not payload.get("box_id"):
        return None
    payload.setdefault("name", DEFAULT_NAME)
    return payload


def get_identity() -> dict[str, Any]:
    """Identité partagée ; créée au premier démarrage de la box."""
    global _IDENTITY
    with _IDENTITY_LOCK:
        if _IDENTITY is not None:
            return _IDENTITY
        existing = load_identity()
        if existing is None:
            existing = _new_identity(os.environ.get("COMPANION_BOX_NAME", DEFAULT_NAME))
            _write(existing, identity_path())
            existing["_created"] = True
        _IDENTITY = existing
        return _IDENTITY


def reset_identity() -> None:
    """Oublier l'identité en mémoire (tests, changement de chemin)."""
    global _IDENTITY
    with _IDENTITY_LOCK:
        _IDENTITY = None


def rotate() -> dict[str, Any]:
    """Révoquer l'ancien jeton d'appairage et en émettre un neuf."""
    global _IDENTITY
    with _IDENTITY_LOCK:
        identity = dict(get_identity())
        identity.pop("_created", None)
        identity["token"] = secrets.token_urlsafe(TOKEN_BYTES)
        identity["rotated_at"] = time.time()
        _write(identity, identity_path())
        _IDENTITY = identity
        return identity


def token_matches(candidate: str, identity: dict[str, Any]) -> bool:
    expected = str(identity.get("token") or "")
    if not candidate or not expected:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def pairing_url(
    identity: dict[str, Any],
    host: str,
    port: int = DEFAULT_PORT,
    scheme: str = "http",
) -> str:
    return "%s://%s:%d%s#t=%s" % (scheme, host, port, PAIR_PATH, identity["token"])


def detect_lan_host() -> str:
    """Adresse privée de la box, sans émettre de paquet."""
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if parsed.is_private and not parsed.is_loopback and not parsed.is_link_local:
                return address
    except OSError:
        pass
    return "127.0.0.1"


def write_qr(payload: str, out: Path) -> Path:
    """Écrire le QR en PNG ou SVG (bibliothèque `qrcode` déjà installée)."""
    import qrcode

    out.parent.mkdir(parents=True, exist_ok=True)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    if out.suffix.lower() == ".svg":
        from qrcode.image.svg import SvgPathImage

        image = qr.make_image(image_factory=SvgPathImage)
    else:
        image = qr.make_image(fill_color="black", back_color="white")
    image.save(str(out))
    return out


def startup_lines(host: str, port: int, scheme: str = "http") -> list[str]:
    """Lignes affichées au démarrage : le jeton n'apparaît qu'à la création."""
    identity = get_identity()
    lines = ["[appairage] box %s — %s" % (identity["box_id"], identity["name"])]
    if identity.get("_created"):
        lines.append("[appairage] QR : %s" % pairing_url(identity, host, port, scheme))
        lines.append("[appairage] à imprimer et coller au dos du boîtier.")
        identity.pop("_created", None)
    else:
        lines.append(
            "[appairage] QR à régénérer : python -m app.interface.companion.pairing qr "
            "--out data/box-qr.png --host %s --port %d" % (host, port)
        )
    return lines


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Identité et QR d'appairage de la box.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="afficher l'identité et l'URL d'appairage")

    qr_parser = sub.add_parser("qr", help="écrire le QR (PNG ou SVG)")
    qr_parser.add_argument("--out", required=True, help="fichier de sortie (.png ou .svg)")
    qr_parser.add_argument("--host", default="", help="adresse vue par le téléphone")
    qr_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    qr_parser.add_argument("--scheme", default="http", choices=("http", "https"))

    sub.add_parser("rotate", help="révoquer l'ancien jeton d'appairage")

    args = parser.parse_args(argv)
    identity = get_identity()

    if args.command == "show":
        print("box     : %s — %s" % (identity["box_id"], identity["name"]))
        print("jeton   : %s… (masqué)" % identity["token"][:6])
        print("URL     : %s" % pairing_url(identity, detect_lan_host(), DEFAULT_PORT))
        return 0

    if args.command == "rotate":
        identity = rotate()
        print("Nouveau jeton émis ; l'ancien QR ne fonctionne plus.")
        print("URL     : %s" % pairing_url(identity, detect_lan_host(), DEFAULT_PORT))
        return 0

    host = args.host.strip() or detect_lan_host()
    payload = pairing_url(identity, host, args.port, args.scheme)
    out = Path(args.out)
    try:
        write_qr(payload, out)
    except Exception as exc:  # noqa: BLE001 - message clair pour la CLI
        print("Échec de génération du QR : %s" % exc, file=sys.stderr)
        return 1
    print("QR écrit : %s" % out)
    print("URL     : %s" % payload)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
