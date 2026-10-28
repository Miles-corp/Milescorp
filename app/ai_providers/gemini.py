"""Fournisseur Google Gemini — protocole NATIF generateContent.

Pas de fausse compatibilité OpenAI : l'API Gemini utilise ses propres
chemins (``/v1beta/models/{model}:generateContent``), son authentification
(clé en paramètre ``key=``) et ses corps/réponses (contents/parts).

Sécurité : la clé passe en query ; **aucune URL avec clé n'est jamais
affichée, journalisée ou propagée** dans les messages d'erreur.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.ai_providers.base import AIProvider, AIProviderError

#: Base publique de l'API Gemini.
GEMINI_BASE = "https://generativelanguage.googleapis.com"


class GeminiProvider(AIProvider):
    """Fournisseur Google Gemini via l'API native generateContent."""

    def __init__(
        self,
        base_url: str = GEMINI_BASE,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._name = f"gemini ({self._base_url})"

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _convertir(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
        """Convertir le format MILES vers Gemini (contents + systemInstruction)."""
        systeme: list[str] = []
        contents: list[dict[str, Any]] = []
        for m in messages:
            role = str(m.get("role", "user"))
            contenu = str(m.get("content", ""))
            if role == "system":
                systeme.append(contenu)
                continue
            role_gemini = "model" if role == "assistant" else "user"
            if contents and contents[-1]["role"] == role_gemini:
                contents[-1]["parts"].append({"text": contenu})
            else:
                contents.append({"role": role_gemini, "parts": [{"text": contenu}]})
        return ("\n\n".join(systeme) or None), contents

    def chat(self, messages: list[dict[str, str]]) -> str:
        systeme, contents = self._convertir(messages)
        if not contents:
            raise AIProviderError("Aucun message à envoyer (conversation vide).")
        if not self._api_key:
            raise AIProviderError("Clé API Gemini absente (configurez avec /api add gemini).")

        corps: dict[str, Any] = {"contents": contents}
        if systeme:
            corps["systemInstruction"] = {"parts": [{"text": systeme}]}

        url = (f"{self._base_url}/v1beta/models/{self._model}:generateContent"
               f"?key={self._api_key}")
        req = urllib.request.Request(
            url,
            data=json.dumps(corps).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                brut = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise self._erreur_http(exc) from None
        except urllib.error.URLError:
            raise AIProviderError(
                f"Impossible de joindre Gemini ({self._base_url})."
            ) from None
        except Exception as exc:  # noqa: BLE001
            raise AIProviderError(f"Erreur inattendue avec Gemini : {type(exc).__name__}.") from None

        try:
            data = json.loads(brut)
            candidats = data.get("candidates") or []
            texte = "".join(
                "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", []))
                for c in candidats
            )
        except (ValueError, AttributeError, TypeError):
            raise AIProviderError("Réponse invalide (non-JSON) de Gemini.") from None
        if not texte:
            raise AIProviderError("Réponse vide de Gemini.")
        return texte

    @staticmethod
    def _erreur_http(exc: urllib.error.HTTPError) -> AIProviderError:
        """Traduire une erreur HTTP en message PUBLIC (la clé n'apparaît JAMAIS)."""
        code = exc.code
        if code in (400, 401, 403):
            return AIProviderError(
                "Gemini : clé API invalide ou requête refusée (HTTP %d)." % code
            )
        if code == 404:
            return AIProviderError("Gemini : modèle introuvable (HTTP 404).")
        if code == 429:
            return AIProviderError("Gemini : limite de débit atteinte (HTTP 429), réessayez plus tard.")
        return AIProviderError(f"Gemini : erreur HTTP {code}.")

    def is_available(self) -> bool:
        """Sonde légère : GET /v1beta/models (avec la clé, sortie sans secret)."""
        if not self._api_key:
            return False
        try:
            req = urllib.request.Request(
                f"{self._base_url}/v1beta/models?key={self._api_key}",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=min(self._timeout, 5)) as resp:
                return resp.status < 400
        except Exception:  # noqa: BLE001
            return False
