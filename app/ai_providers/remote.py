"""Fournisseur IA distant via API HTTP."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.ai_providers.base import AIProvider, AIProviderError


class RemoteProvider(AIProvider):
    """Fournisseur IA appelant un service distant compatible (OpenAI-like ou autre)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # Éviter le doublon "/v1/" si l'URL de base se termine déjà par "/v1"
        # (cas fréquent avec Groq : https://api.groq.com/openai/v1).
        if self._base_url.endswith("/v1"):
            self._base_url = self._base_url[:-3]
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._name = f"remote ({self._base_url})"

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        """Vérifier rapidement si l'endpoint répond (HEAD/GET léger)."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/health",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=min(self._timeout, 5)) as resp:
                return resp.status < 400
        except Exception:  # noqa: BLE001 — toute erreur d'indisponibilité
            return False

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Envoyer les messages au fournisseur distant et retourner la réponse."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if resp.status >= 400:
                    body_text = resp.read().decode("utf-8", errors="replace")
                    raise AIProviderError(
                        f"Erreur HTTP {resp.status} du fournisseur distant: {body_text[:200]}"
                    )
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise AIProviderError(
                f"Erreur HTTP {exc.code} du fournisseur distant: {body_text[:200]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AIProviderError(
                f"Impossible de joindre le fournisseur distant ({self._base_url}): {exc}. "
                f"Verifiez MILES_REMOTE_BASE_URL ou utilisez MILES_PROVIDER=local avec un serveur Ollama."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(
                f"Erreur inattendue avec le fournisseur distant: {exc}"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                f"Réponse invalide (non-JSON) du fournisseur distant: {raw[:200]}"
            ) from exc

        # Extraction robuste du contenu de réponse (format OpenAI-like)
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIProviderError("Aucun choix retourné par le fournisseur distant.")
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not content:
                raise AIProviderError("Réponse vide du fournisseur distant.")
            return str(content)
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIProviderError(
                f"Format de réponse inattendu du fournisseur distant: {exc}"
            ) from exc
