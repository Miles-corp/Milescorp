"""Fournisseur Anthropic (Claude) — protocole NATIF /v1/messages.

Pas de fausse compatibilité OpenAI : l'API Anthropic utilise ses propres
en-têtes (x-api-key, anthropic-version), son corps (system en top-level,
max_tokens obligatoire) et sa réponse (content[].text). Aucun SDK externe :
bibliothèque standard uniquement, comme tout le reste de MILES.

Aucune clé dans un message d'erreur ni dans un journal.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.ai_providers.base import AIProvider, AIProviderError

#: Version de l'API Anthropic exigée.
ANTHROPIC_VERSION = "2023-06-01"
#: Nombre maximal de jetons de réponse (borne conservatrice MILES).
MAX_TOKENS = 1024


class AnthropicProvider(AIProvider):
    """Fournisseur Claude via l'API Anthropic native."""

    def __init__(
        self,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-3-5-haiku-latest",
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._name = f"anthropic ({self._base_url})"

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _convertir(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Convertir le format MILES (system/user/assistant) vers Anthropic.

        Returns:
            (systeme_top_level, contents_convertis)
        """
        systeme: list[str] = []
        sorties: list[dict[str, Any]] = []
        for m in messages:
            role = str(m.get("role", "user"))
            contenu = str(m.get("content", ""))
            if role == "system":
                systeme.append(contenu)
                continue
            role_anthropic = "assistant" if role == "assistant" else "user"
            # Anthropic alterne strictement user/assistant : on fusionne
            # deux roles consecutifs identiques pour rester valide.
            if sorties and sorties[-1]["role"] == role_anthropic:
                sorties[-1]["content"] += "\n\n" + contenu
            else:
                sorties.append({"role": role_anthropic, "content": contenu})
        return ("\n\n".join(systeme) or None), sorties

    def chat(self, messages: list[dict[str, str]]) -> str:
        systeme, contents = self._convertir(messages)
        if not contents:
            raise AIProviderError("Aucun message à envoyer (conversation vide).")
        if not self._api_key:
            raise AIProviderError("Clé API Anthropic absente (configurez avec /api add anthropic).")

        corps: dict[str, Any] = {
            "model": self._model,
            "max_tokens": MAX_TOKENS,
            "messages": contents,
        }
        if systeme:
            corps["system"] = systeme

        req = urllib.request.Request(
            f"{self._base_url}/v1/messages",
            data=json.dumps(corps).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": str(self._api_key),
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                brut = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self._erreur_http(exc) from None
        except urllib.error.URLError as exc:
            raise AIProviderError(
                f"Impossible de joindre Anthropic ({self._base_url})."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Erreur inattendue avec Anthropic : {type(exc).__name__}.") from None

        try:
            data = json.loads(brut)
            blocs = data.get("content") or []
            texte = "".join(
                b.get("text", "") for b in blocs if b.get("type") == "text"
            )
        except (ValueError, AttributeError, TypeError):
            raise AIProviderError("Réponse invalide (non-JSON) d'Anthropic.") from None
        if not texte:
            raise AIProviderError("Réponse vide d'Anthropic.")
        return texte

    @staticmethod
    def _erreur_http(exc: urllib.error.HTTPError) -> AIProviderError:
        """Traduire une erreur HTTP en message PUBLIC (jamais de clé)."""
        code = exc.code
        if code in (401, 403):
            return AIProviderError("Anthropic : clé API invalide ou refusée (HTTP %d)." % code)
        if code == 404:
            return AIProviderError("Anthropic : modèle ou endpoint introuvable (HTTP 404).")
        if code == 429:
            return AIProviderError("Anthropic : limite de débit atteinte (HTTP 429), réessayez plus tard.")
        return AIProviderError(f"Anthropic : erreur HTTP {code}.")

    def is_available(self) -> bool:
        """Sonde légère : GET /v1/models (liste, sans secret dans la sortie)."""
        if not self._api_key:
            return False
        try:
            req = urllib.request.Request(
                f"{self._base_url}/v1/models",
                headers={"x-api-key": str(self._api_key),
                         "anthropic-version": ANTHROPIC_VERSION},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=min(self._timeout, 5)) as resp:
                return resp.status < 400
        except Exception:  # noqa: BLE001 — toute erreur = indisponible
            return False
