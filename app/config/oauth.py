"""Assistant de liaison de comptes OAuth (S6.3, MI-008 phase 3).

Principe (décisions validées du 2026-10-24) :
- les jetons OAuth sont stockés uniquement dans le fichier `.env` local,
  ignoré par Git ; jamais affichés, journalisés ni transmis ;
- le flux OAuth est un flux « authorization code » avec serveur de
  rappel local (127.0.0.1) ; aucune dépendance externe ;
- un compte lié (ex. Google) raccourcit la configuration des services
  du même groupe d'identité (ex. Gemini) ;
- aucun appel réseau n'est fait sans autorisation explicite de l'utilisateur.

Conformité charte IA : niveau 4 (secrets) — tout audit indépendant
recommandé avant production ; aucune déclaration d'audit ici.
"""

from __future__ import annotations

import http.server
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from typing import Callable, Optional

# Fournisseurs OAuth connus : nom → (URL d'autorisation, URL de token,
# scopes, clé d'environnement du jeton).
OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": "openid email profile",
        "token_key": "MILES_OAUTH_GOOGLE_TOKEN",
        "client_id_key": "MILES_OAUTH_GOOGLE_CLIENT_ID",
        "client_secret_key": "MILES_OAUTH_GOOGLE_CLIENT_SECRET",
    },
}

#: Port local pour le serveur de rappel OAuth.
CALLBACK_PORT = 8765

#: Durée maximale d'attente du rappel (secondes).
CALLBACK_TIMEOUT = 120.0


class OAuthError(Exception):
    """Erreur lors du flux OAuth."""


def _build_auth_url(provider: str, client_id: str, state: str) -> str:
    """Construire l'URL d'autorisation OAuth."""
    spec = OAUTH_PROVIDERS[provider]
    params = {
        "client_id": client_id,
        "redirect_uri": f"http://127.0.0.1:{CALLBACK_PORT}/callback",
        "response_type": "code",
        "scope": spec["scopes"],
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return spec["auth_url"] + "?" + urllib.parse.urlencode(params)


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Gestionnaire HTTP minimal pour le rappel OAuth."""

    auth_code: Optional[str] = None
    state_received: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        if "error" in params:
            _CallbackHandler.error = params["error"][0]
        else:
            _CallbackHandler.auth_code = params.get("code", [None])[0]
            _CallbackHandler.state_received = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>MILES</h1>"
            b"<p>Autorisation re\u00e7ue. Vous pouvez fermer cet onglet.</p>"
            b"</body></html>"
        )

    def log_message(self, format: str, *args: object) -> None:
        return  # Pas de log HTTP (pas de secret exposé)


def _receive_callback(timeout: float = CALLBACK_TIMEOUT) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Démarrer le serveur de rappel et attendre le code d'autorisation.

    Retourne (code, state, erreur). Lance OAuthError en cas de timeout.
    """
    _CallbackHandler.auth_code = None
    _CallbackHandler.state_received = None
    _CallbackHandler.error = None

    server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    server.timeout = timeout

    def _serve() -> None:
        server.handle_request()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    thread.join(timeout=timeout + 1)

    if _CallbackHandler.error:
        raise OAuthError(f"Refus de l'utilisateur : {_CallbackHandler.error}")
    if _CallbackHandler.auth_code is None:
        raise OAuthError("Aucun code reçu (timeout ou abandon).")
    return (
        _CallbackHandler.auth_code,
        _CallbackHandler.state_received,
        _CallbackHandler.error,
    )


def _exchange_code(
    provider: str, code: str, client_id: str, client_secret: str
) -> str:
    """Échanger le code d'autorisation contre un jeton d'accès."""
    spec = OAUTH_PROVIDERS[provider]
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": f"http://127.0.0.1:{CALLBACK_PORT}/callback",
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        spec["token_url"],
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise OAuthError(f"Échange de code échoué : {type(exc).__name__}") from exc
    token = payload.get("access_token")
    if not token:
        raise OAuthError("Pas de jeton d'accès dans la réponse.")
    return str(token)


def link_account(
    provider: str,
    env_path: str = ".env",
    show: Callable[[str], None] = print,
    open_browser: Callable[[str], bool] = webbrowser.open,
) -> int:
    """Lier un compte OAuth (ex. Google) pour réduire les étapes de setup.

    Le flux :
    1. Lire le client_id / client_secret depuis l'environnement ou `.env`.
    2. Ouvrir le navigateur vers la page d'autorisation du fournisseur.
    3. Attendre le rappel local (127.0.0.1) avec le code d'autorisation.
    4. Échanger le code contre un jeton d'accès.
    5. Stocker le jeton dans `.env` (clé `MILES_OAUTH_<PROVIDER>_TOKEN`).

    Aucun jeton n'est affiché. Aucun appel réseau sans autorisation explicite
    de l'utilisateur (le navigateur s'ouvre seulement après confirmation).
    """
    if provider not in OAUTH_PROVIDERS:
        show(f"Fournisseur OAuth inconnu : {provider}.")
        show("Fournisseurs disponibles : " + ", ".join(OAUTH_PROVIDERS))
        return 1

    spec = OAUTH_PROVIDERS[provider]
    client_id = os.environ.get(spec["client_id_key"], "").strip()
    client_secret = os.environ.get(spec["client_secret_key"], "").strip()

    # Lire depuis .env si absent de l'environnement.
    if (not client_id or not client_secret) and os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if "=" not in line or line.startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key == spec["client_id_key"]:
                        client_id = client_id or value
                    elif key == spec["client_secret_key"]:
                        client_secret = client_secret or value
        except OSError:
            pass

    if not client_id or not client_secret:
        show(
            f"Client ID/secret OAuth manquants pour {provider}. "
            f"Définissez {spec['client_id_key']} et "
            f"{spec['client_secret_key']} dans .env (ou l'environnement)."
        )
        show(
            "Ces valeurs proviennent de la console développeur du fournisseur "
            "(ex. Google Cloud Console)."
        )
        return 1

    state = secrets.token_urlsafe(32)
    url = _build_auth_url(provider, client_id, state)
    show(f"Liaison du compte {provider}…")
    show("Un navigateur va s'ouvrir pour l'autorisation.")
    show(f"Si rien ne s'ouvre, copiez cette URL : {url}")
    try:
        open_browser(url)
    except Exception:  # noqa: BLE001
        show("Impossible d'ouvrir le navigateur automatiquement.")

    show("En attente du rappel local (120 s max)…")
    try:
        code, received_state, error = _receive_callback()
    except OAuthError as exc:
        show(f"Liaison annulée : {exc}")
        return 1
    if error:
        show(f"Refus de l'utilisateur : {error}")
        return 1
    if received_state != state:
        show("Échec de vérification (state mismatch) : liaison annulée.")
        return 1

    show("Code reçu, échange en cours…")
    try:
        token = _exchange_code(provider, code, client_id, client_secret)
    except OAuthError as exc:
        show(f"Échec de l'échange : {exc}")
        return 1

    # Stocker le jeton dans .env (jamais affiché).
    from app.config.setup import write_env

    existing = ""
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        except OSError:
            pass
    write_env(env_path, {spec["token_key"]: token}, existing)
    show(f"Compte {provider} lié avec succès. Jeton stocké dans {env_path}.")
    show(
        "Les services du même groupe d'identité pourront être configurés "
        "avec le minimum d'étapes (voir `--setup`)."
    )
    return 0


def linked_providers(env_path: str = ".env") -> list[str]:
    """Lister les fournisseurs OAuth déjà liés (jeton présent dans .env)."""
    result: list[str] = []
    values: dict[str, str] = {}
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if "=" not in line or line.startswith("#"):
                        continue
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
        except OSError:
            pass
    for name, spec in OAUTH_PROVIDERS.items():
        if values.get(spec["token_key"]):
            result.append(name)
    # Aussi depuis l'environnement.
    for name, spec in OAUTH_PROVIDERS.items():
        if os.environ.get(spec["token_key"]) and name not in result:
            result.append(name)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lier un compte OAuth à MILES")
    parser.add_argument("provider", choices=list(OAUTH_PROVIDERS), help="Fournisseur OAuth")
    parser.add_argument("--env", default=".env", help="Chemin du fichier .env")
    args = parser.parse_args()
    raise SystemExit(link_account(args.provider, env_path=args.env))
