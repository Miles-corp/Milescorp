"""État et connexion rapide des fournisseurs IA, côté site.

Trois règles :

1. **Aucune clé ne sort de la box.** Ce module ne renvoie qu'un booléen
   « configuré », le modèle et le fournisseur actif. La longueur de la clé
   (`provider_config.statut()` la renvoyait) n'est jamais exposée.
2. **Une seule liste de fournisseurs** : celle que MILES sait réellement
   construire (`app.ai_providers.registry.fournisseurs_soutenus`) plus le
   moteur local Ollama. Mistral et « claude » du vieux catalogue `--setup`
   ne sont pas proposés tant qu'ils ne sont pas soutenus par la fabrique.
3. **Le test est explicite** : il n'est lancé que sur action de
   l'utilisateur, avec un délai court, et ne renvoie qu'un booléen et une
   raison courte — jamais de clé, jamais d'URL contenant la clé.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from app.config import provider_config
from app.ai_providers.registry import build_provider, fournisseurs_soutenus

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]

#: Libellés affichés. Une seule source pour l'interface et le serveur.
LABELS: dict[str, str] = {
    "groq": "Groq",
    "openai": "OpenAI",
    "anthropic": "Claude (Anthropic)",
    "gemini": "Gemini",
    "local": "Ollama (local)",
}

#: Fournisseurs qui exigent une clé. `local` n'en exige pas.
KEYLESS = {"local"}


def _env_file() -> str:
    return os.environ.get("MILES_ENV_FILE", str(REPO_ROOT / ".env"))


def _env_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    path = Path(_env_file())
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            if key.strip() == name:
                return raw.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def mode_actif() -> str:
    return (_env_value("MILES_PROVIDER") or "remote").lower()


def fournisseur_actif() -> Optional[str]:
    if mode_actif() == "local":
        return "local"
    return (_env_value("MILES_REMOTE_PROVIDER") or "").lower() or None


def _model_for(provider: str) -> str:
    if provider == "local":
        return _env_value("MILES_LOCAL_MODEL") or ""
    return _env_value("MILES_MODEL_%s" % provider.upper())


def _configured(provider: str) -> bool:
    if provider in KEYLESS:
        return True
    return bool(_env_value("MILES_API_KEY_%s" % provider.upper()) or (
        os.environ.get("MILES_API_KEY_%s" % provider.upper()) or ""
    ).strip())


def catalog() -> list[dict[str, Any]]:
    """Liste des fournisseurs réellement proposables, sans aucun secret."""
    active = fournisseur_actif()
    mode = mode_actif()
    items = []
    for provider in fournisseurs_soutenus() + ["local"]:
        configured = _configured(provider)
        items.append(
            {
                "id": provider,
                "label": LABELS.get(provider, provider.title()),
                "requires_key": provider not in KEYLESS,
                "configured": configured,
                "active": (provider == active) if provider != "local" else (mode == "local"),
                "model": _model_for(provider),
                "key_state": (
                    "non requise"
                    if provider in KEYLESS
                    else ("configurée" if configured else "absente")
                ),
                "mode": "local" if provider in KEYLESS else "distant",
            }
        )
    return items


def status() -> dict[str, Any]:
    """État compact du fournisseur actif (aucune clé, aucune longueur)."""
    mode = mode_actif()
    active = fournisseur_actif()
    model = _model_for(active) if active else ""
    return {
        "mode": mode,
        "provider": active,
        "provider_label": LABELS.get(active or "", active or "non configuré"),
        "model": model or "inconnu",
        "configured": bool(active and _configured(active)),
        "keyless": active in KEYLESS if active else False,
        "restart_required": False,
    }


def activate(provider: str) -> dict[str, Any]:
    """Activer un fournisseur déjà configuré ; aucun redémarrage implicite."""
    provider = (provider or "").strip().lower()
    if provider not in LABELS or provider not in (fournisseurs_soutenus() + ["local"]):
        raise ValueError("Fournisseur non soutenu.")
    if provider == "local":
        from app.config.setup import write_env

        env_path = _env_file()
        existing = ""
        try:
            existing = Path(env_path).read_text(encoding="utf-8")
        except OSError:
            pass
        write_env(env_path, {"MILES_PROVIDER": "local"}, existing)
        return {
            "provider": provider,
            "restart_required": True,
            "message": "Fournisseur local activé dans .env ; redémarrez miles.py.",
        }
    if not _configured(provider):
        raise ValueError(
            "Clé absente pour %s : connectez-la d'abord sur la page locale."
            % LABELS.get(provider, provider)
        )
    result = provider_config.activate(provider, env_path=_env_file())
    return {
        "provider": provider,
        "model": result.get("modele"),
        "restart_required": True,
        "message": "Fournisseur activé dans .env ; redémarrez miles.py.",
    }


def test(provider: str) -> dict[str, Any]:
    """Sonde explicite de disponibilité, sans exposer la clé."""
    provider = (provider or "").strip().lower()
    if provider not in LABELS or provider not in (fournisseurs_soutenus() + ["local"]):
        raise ValueError("Fournisseur non soutenu.")
    if provider != "local" and not _configured(provider):
        return {
            "provider": provider,
            "available": False,
            "reason": "aucune clé configurée",
        }
    model = _model_for(provider)
    if not model:
        return {
            "provider": provider,
            "available": False,
            "reason": "aucun modèle configuré",
        }
    try:
        if provider == "local":
            from app.ai_providers.local import LocalProvider

            adapter = LocalProvider(
                base_url=_env_value("MILES_LOCAL_BASE_URL") or "http://localhost:11434",
                model=model,
                timeout=5,
            )
        else:
            adapter = build_provider(
                provider,
                model=model,
                api_key=provider_config.cle_pour(provider, env_path=_env_file()),
                base_url=_env_value("MILES_REMOTE_BASE_URL") or None,
                timeout=5,
            )
        available = bool(adapter.is_available())
    except Exception as exc:  # noqa: BLE001 - le message ne contient pas la clé
        return {
            "provider": provider,
            "available": False,
            "reason": "échec de la sonde (%s)" % type(exc).__name__,
        }
    return {
        "provider": provider,
        "available": available,
        "reason": "joignable" if available else "injoignable ou refusé",
    }


def key_for(provider: str) -> Optional[str]:
    """Réservé au serveur : jamais renvoyé par une route ni journalisé."""
    provider = (provider or "").strip().lower()
    if provider == "local" or provider not in fournisseurs_soutenus():
        return None
    return provider_config.cle_pour(provider, env_path=_env_file())


def save_key(provider: str, api_key: str, model: str = "") -> dict[str, Any]:
    """Écrire une clé sur la box, de façon atomique, sans la renvoyer.

    Appelé uniquement par la page locale ``/setup`` (boucle locale), jamais
    par une route JSON de l'interface distante.
    """
    provider = (provider or "").strip().lower()
    if provider not in fournisseurs_soutenus():
        raise ValueError("Fournisseur non soutenu.")
    action = provider_config.set_key(provider, api_key, env_path=_env_file())
    if model:
        provider_config.set_model(provider, model, env_path=_env_file())
    return {
        "provider": provider,
        "action": action,
        "model": model or provider_config.modele_fournisseur(provider, env_path=_env_file()) or "",
        "restart_required": True,
    }
