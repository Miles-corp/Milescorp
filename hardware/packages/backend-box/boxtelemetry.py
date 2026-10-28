#!/usr/bin/env python3
"""Backend box MILES — telemetry physique du boîtier (étape 1 du plan).

Contrat :
- écoute **127.0.0.1:8095** par défaut (fail-closed) ; le mode LAN exige
  une clé locale (`MILES_BOX_HOST`/`MILES_BOX_KEY`) — voir README ;
- `GET  /box/telemetry` : relevé matériel LOCAL (lecture /proc, /sys,
  uptime) ; chaque capteur absent rend "non disponible" (jamais inventé) ;
- `POST /box/ingest` : réception des relevés ESP32 (clé locale exigée) ;
- **zéro appel réseau sortant**, écriture limitée à `box_state.json` local,
  aucune clé affichée ni journalisée.

Usage : python3 boxtelemetry.py
"""

from __future__ import annotations

import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8095
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "box_state.json")
MAX_BODY = 8192


def lire_cpu() -> dict[str, Any]:
    """Charge et uptime depuis /proc (Linux) — repli honnête sinon."""
    resultat: dict[str, Any] = {"charge": None, "uptime_s": None}
    try:
        with open("/proc/loadavg", "r", encoding="ascii") as fh:
            resultat["charge"] = [float(x) for x in fh.read().split()[:3]]
    except OSError:
        pass
    try:
        with open("/proc/uptime", "r", encoding="ascii") as fh:
            resultat["uptime_s"] = round(float(fh.read().split()[0]), 1)
    except OSError:
        pass
    return resultat


def lire_hwmmon() -> dict[str, Any]:
    """Températures et ventilos via /sys/class/hwmon (lecture seule)."""
    temperatures: list[dict[str, Any]] = []
    ventilos: list[dict[str, Any]] = []
    racine = "/sys/class/hwmon"
    try:
        entrees = sorted(os.listdir(racine))
    except OSError:
        return {"temperatures": [], "ventilos": []}
    for nom in entrees:
        base = os.path.join(racine, nom)
        for champ in os.listdir(base):
            if not champ.startswith("temp") or not champ.endswith("_input"):
                continue
            try:
                with open(os.path.join(base, champ), "r", encoding="ascii") as fh:
                    brut = int(fh.read().strip())
                valeurs: dict[str, Any] = {"capteur": nom, "celsius": round(brut / 1000.0, 1)}
                nom_fichier = os.path.join(base, champ.replace("_input", "_label"))
                if os.path.isfile(nom_fichier):
                    with open(nom_fichier, "r", encoding="utf-8") as fh:
                        valeurs["libelle"] = fh.read().strip()
                temperatures.append(valeurs)
            except (OSError, ValueError):
                continue
        for champ in os.listdir(base):
            if not champ.startswith("fan") or not champ.endswith("_input"):
                continue
            try:
                with open(os.path.join(base, champ), "r", encoding="ascii") as fh:
                    ventilos.append({"capteur": nom, "tr/min": int(fh.read().strip())})
            except (OSError, ValueError):
                continue
    return {"temperatures": temperatures, "ventilos": ventilos}


def collecter() -> dict[str, Any]:
    """Relevé complet (lecture seule, aucun réseau, aucun secret)."""
    hw = lire_hwmmon()
    return {
        "source": "boxtelemetry",
        "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cpu": lire_cpu(),
        "temperatures": hw["temperatures"] or [{"etat": "non disponible"}],
        "ventilos": hw["ventilos"] or [{"etat": "non disponible"}],
        "injection_esp32": _etat_injection(),
    }


def _etat_injection() -> dict[str, Any]:
    """Dernier relevé ESP32 reçu (ou "aucun"), jamais inventé."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            etat = json.load(fh)
        age = round(time.time() - float(etat.get("recu_le", 0)), 1)
        if age > 60:
            return {"etat": "recu mais perime", "age_s": age}
        return {"etat": "recu", "age_s": age, **{
            k: v for k, v in etat.items() if k in
            ("temperature", "humidite", "bouton")}}
    except (OSError, ValueError):
        return {"etat": "aucun"}


def _verifier_cle(en_tetes: Any, body: bytes) -> bool:
    """Clé locale exigée pour POST /box/ingest (jamais journalisée).

    La comparaison est à **temps constant** (`hmac.compare_digest`) : une
    comparaison naïve laisse fuir, par le temps de réponse, la longueur du
    préfixe correct — sur un réseau local c'est lent mais mesurable.

    Les **octets** sont comparés, pas les chaînes : `compare_digest` refuse
    les `str` non ASCII. Un corps qui n'est pas un objet JSON, ou une clé qui
    n'est pas une chaîne, est refusé sans lever d'exception.
    """
    attendue = os.environ.get("MILES_BOX_KEY", "")
    if not attendue:
        return False
    try:
        charge = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(charge, dict):
        return False
    fournie = charge.get("cle")
    if not isinstance(fournie, str):
        return False
    return hmac.compare_digest(fournie.encode("utf-8"), attendue.encode("utf-8"))


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:  # aucun accès ni secret au journal
        return

    def _envoyer(self, code: int, charge: dict) -> None:
        corps = json.dumps(charge, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        # Origines locales uniquement (cockpit 8787, MILES 8080).
        origine = self.headers.get("Origin", "")
        if origine.startswith("http://127.0.0.1") or origine.startswith("http://localhost"):
            self.send_header("Access-Control-Allow-Origin", origine)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(corps)

    def do_OPTIONS(self) -> None:  # noqa: N802 — préflight CORS local
        self._envoyer(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/box/telemetry":
            self._envoyer(404, {"error": "inconnu"})
            return
        self._envoyer(200, collecter())

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?")[0] != "/box/ingest":
            self._envoyer(404, {"error": "inconnu"})
            return
        longueur = int(self.headers.get("Content-Length") or 0)
        if longueur <= 0 or longueur > MAX_BODY:
            self._envoyer(400, {"error": "corps invalide"})
            return
        corps = self.rfile.read(longueur)
        if not _verifier_cle(self.headers, corps):
            self._envoyer(401, {"error": "cle locale requise"})
            return
        try:
            charge = json.loads(corps.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._envoyer(400, {"error": "json invalide"})
            return
        # Seuls des relevés scalaires plausibles sont conservés.
        propre = {
            k: charge[k] for k in ("temperature", "humidite", "bouton")
            if k in charge and isinstance(charge[k], (int, float, bool, str))
        }
        propre["recu_le"] = time.time()
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(propre, fh)
        self._envoyer(200, {"ok": True})


def main() -> int:
    host = os.environ.get("MILES_BOX_HOST", DEFAULT_HOST)
    port = int(os.environ.get("MILES_BOX_PORT", DEFAULT_PORT))
    if host != DEFAULT_HOST and not os.environ.get("MILES_BOX_KEY"):
        # Fail-closed : aucune écoute réseau sans clé locale.
        print("REFUS : MILES_BOX_HOST hors local sans MILES_BOX_KEY configure.")
        return 1
    serveur = ThreadingHTTPServer((host, port), _Handler)
    print(f"[boxtelemetry] http://{host}:{port}/box/telemetry (lecture seule)")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt boxtelemetry.")
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
