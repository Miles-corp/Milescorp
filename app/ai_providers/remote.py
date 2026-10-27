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
        health_path: str | None = None,
    ) -> None:
        brut = base_url.rstrip("/")
        # Contrat OpenAI-compatible (Groq, OpenAI...) : l'endpoint de santé
        # standard est GET <base>/models ; /health y est généralement absent
        # (diagnostic 2026-10-26 : is_available() -> False alors que le chat
        # fonctionne). La détection est faite AVANT normalisation "/v1".
        self._openai_compat = brut.endswith("/v1") or "/openai" in brut
        # Éviter le doublon "/v1/" si l'URL de base se termine déjà par "/v1"
        # (cas fréquent avec Groq : https://api.groq.com/openai/v1).
        self._base_url = brut[:-3] if brut.endswith("/v1") else brut
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._health_path = health_path
        self._name = f"remote ({self._base_url})"

    @property
    def name(self) -> str:
        return self._name

    def _health_candidates(self) -> list[str]:
        """Chemins de sonde ordonnés (jamais de secret dans ces URL)."""
        if self._health_path:
            return ["/" + str(self._health_path).lstrip("/")]
        principal = "/models" if self._openai_compat else "/health"
        secondaire = "/health" if principal == "/models" else "/models"
        return [principal, secondaire]

    def availability_probe(self) -> dict[str, Any]:
        """Sonde de disponibilité détaillée, SANS aucun secret dans la sortie.

        Distingue les causes : ``configure_absente``, ``ok``,
        ``auth_invalide`` (401/403), ``endpoint_absent`` (404 sur tous les
        candidats), ``delai_passe``, ``reseau_injoignable``, ``http_<code>``.
        Zéro appel réseau si la configuration est vide.
        """
        if not self._base_url or not self._model:
            return {"disponible": False, "cause": "configure_absente", "endpoint": None}
        causes: list[str] = []
        for chemin in self._health_candidates():
            url = f"{self._base_url}{chemin}"
            try:
                req = urllib.request.Request(
                    url, method="GET", headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=min(self._timeout, 5)) as resp:
                    if resp.status < 400:
                        return {"disponible": True, "cause": "ok", "endpoint": chemin}
                    if resp.status in (401, 403):
                        return {"disponible": False, "cause": "auth_invalide", "endpoint": chemin}
                    causes.append(f"http_{resp.status}")
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    return {"disponible": False, "cause": "auth_invalide", "endpoint": chemin}
                causes.append(f"http_{exc.code}")
            except TimeoutError:
                causes.append("delai_passe")
            except urllib.error.URLError as exc:
                raison = getattr(exc, "reason", None)
                causes.append("delai_passe" if isinstance(raison, TimeoutError) else "reseau_injoignable")
            except Exception:  # noqa: BLE001 — toute sonde inattendue = indisponible
                causes.append("sonde_inconnue")
        if not causes:
            return {"disponible": False, "cause": "endpoint_absent", "endpoint": None}
        derniere = causes[-1]
        cause = "endpoint_absent" if derniere == "http_404" else derniere
        return {"disponible": False, "cause": cause, "endpoint": None}

    def is_available(self) -> bool:
        """Vérifier la disponibilité (voir availability_probe pour la cause)."""
        return bool(self.availability_probe()["disponible"])

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
                f"Impossible de joindre le fournisseur distant ({self._base_url}): {exc}"
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
