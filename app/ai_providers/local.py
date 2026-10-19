"""Fournisseur IA local (serveur de modèle local, ex. Ollama, llama.cpp)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.ai_providers.base import AIProvider, AIProviderError


class LocalProvider(AIProvider):
    """Fournisseur IA appelant un serveur de modèle local compatible."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: int = 60,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._name = f"local ({self._base_url})"

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        """Vérifier rapidement si le serveur local répond."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=min(self._timeout, 5)) as resp:
                return resp.status < 400
        except Exception:  # noqa: BLE001
            return False

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Envoyer les messages au serveur local et retourner la réponse."""
        # Format compatible Ollama / llama.cpp server
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
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
                        f"Erreur HTTP {resp.status} du fournisseur local: {body_text[:200]}"
                    )
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            raise AIProviderError(
                f"Erreur HTTP {exc.code} du fournisseur local: {body_text[:200]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AIProviderError(
                f"Impossible de joindre le fournisseur local ({self._base_url}): {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(
                f"Erreur inattendue avec le fournisseur local: {exc}"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                f"Réponse invalide (non-JSON) du fournisseur local: {raw[:200]}"
            ) from exc

        # Extraction du contenu (format OpenAI-like)
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIProviderError("Aucun choix retourné par le fournisseur local.")
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not content:
                raise AIProviderError("Réponse vide du fournisseur local.")
            return str(content)
        except (AttributeError, IndexError, TypeError) as exc:
            raise AIProviderError(
                f"Format de réponse inattendu du fournisseur local: {exc}"
            ) from exc
