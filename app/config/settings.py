"""Configuration de MILES.

Charge les paramètres depuis :
1. un fichier JSON optionnel (chemin transmis ou config/config.json),
2. les variables d'environnement,
3. des valeurs par défaut sûres.

Aucune clé API n'est codée en dur. Les secrets proviennent des variables
d'environnement ou d'un fichier .env ignoré par Git.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SettingsError(Exception):
    """Erreur de configuration."""


class Settings:
    """Paramètres de configuration de MILES."""

    DEFAULTS: dict[str, Any] = {
        "provider": "remote",
        "remote_base_url": "http://localhost:8000",
        "remote_model": "miles-default",
        "remote_timeout": 30,
        "local_base_url": "http://localhost:11434",
        "local_model": "miles-local",
        "local_timeout": 60,
        "history_limit": 10,
        "voice_enabled": False,
        "allowed_actions": ["datetime", "workdir", "list_files"],
    }

    def __init__(self, config_path: str | None = None) -> None:
        self._values: dict[str, Any] = dict(self.DEFAULTS)

        # 1. Fichier JSON optionnel
        resolved_config = config_path or os.environ.get(
            "MILES_CONFIG", "config/config.json"
        )
        config_file = Path(resolved_config)
        if config_file.is_file():
            try:
                with config_file.open("r", encoding="utf-8") as fh:
                    file_values = json.load(fh)
                if not isinstance(file_values, dict):
                    raise SettingsError(
                        f"Le fichier de configuration {config_file} doit contenir un objet JSON."
                    )
                self._values.update(file_values)
            except json.JSONDecodeError as exc:
                raise SettingsError(
                    f"Fichier de configuration invalide {config_file}: {exc}"
                ) from exc
            except OSError as exc:
                raise SettingsError(
                    f"Impossible de lire {config_file}: {exc}"
                ) from exc

        # 2. Variables d'environnement (prioritaires sur le fichier)
        env_mapping = {
            "MILES_PROVIDER": "provider",
            "MILES_REMOTE_BASE_URL": "remote_base_url",
            "MILES_REMOTE_MODEL": "remote_model",
            "MILES_REMOTE_TIMEOUT": "remote_timeout",
            "MILES_LOCAL_BASE_URL": "local_base_url",
            "MILES_LOCAL_MODEL": "local_model",
            "MILES_LOCAL_TIMEOUT": "local_timeout",
            "MILES_HISTORY_LIMIT": "history_limit",
            "MILES_VOICE_ENABLED": "voice_enabled",
            # Secrets : jamais codés en dur, lus uniquement depuis l'environnement
            "MILES_REMOTE_API_KEY": "remote_api_key",
            "MILES_LOCAL_API_KEY": "local_api_key",
        }
        for env_name, key in env_mapping.items():
            value = os.environ.get(env_name)
            if value is not None:
                # Conversion de type pour les champs numériques
                if key in ("remote_timeout", "local_timeout", "history_limit"):
                    try:
                        value = int(value)
                    except ValueError as exc:
                        raise SettingsError(
                            f"La variable {env_name} doit être un entier, valeur reçue: {value!r}"
                        ) from exc
                elif key == "voice_enabled":
                    value = value.lower() in ("1", "true", "yes", "on")
                self._values[key] = value

        # Validation
        self._validate()

    def _validate(self) -> None:
        provider = self._values.get("provider")
        if provider not in ("remote", "local"):
            raise SettingsError(
                f"Fournisseur inconnu : {provider!r}. Valeurs attendues: 'remote' ou 'local'."
            )

        history_limit = self._values.get("history_limit")
        if not isinstance(history_limit, int) or history_limit < 1:
            raise SettingsError(
                f"history_limit doit être un entier positif, valeur reçue: {history_limit!r}"
            )

    @property
    def provider(self) -> str:
        return str(self._values["provider"])

    @provider.setter
    def provider(self, value: str) -> None:
        if value not in ("remote", "local"):
            raise SettingsError(f"Fournisseur inconnu : {value!r}")
        self._values["provider"] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __contains__(self, key: str) -> bool:
        return key in self._values

    def as_dict(self) -> dict[str, Any]:
        """Retourne une copie des valeurs (les clés API sont incluses, ne pas journaliser)."""
        return dict(self._values)
