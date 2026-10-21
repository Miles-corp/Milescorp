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


# Valeurs acceptées pour un paramètre booléen, en variable d'environnement
# ou dans le fichier de configuration JSON (insensible à la casse).
_TRUE_VALUES = ("1", "true", "yes", "on")
_FALSE_VALUES = ("0", "false", "no", "off")


def _coerce_bool(value: Any, source: str) -> bool:
    """Convertir une valeur de configuration en booléen.

    Un booléen est renvoyé tel quel. Une chaîne est comparée à une liste
    blanche de valeurs admises. Toute autre valeur lève une SettingsError
    explicite : utiliser bool() serait trompeur, car bool("false") vaut True
    et activerait silencieusement une fonctionnalité censée être désactivée.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    raise SettingsError(
        f"{source} doit être un booléen (true/false), valeur reçue : {value!r}"
    )


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
        "memory_enabled": False,
        "memory_db_path": "data/memory.db",
        "memory_max_memories_in_context": 5,
        "memory_max_content_length": 1000,
        # Persistance de l'historique de conversation (V1)
        "conversation_persist": True,
        "conversation_db_path": "data/conversations.db",
        # Orchestrateur de missions (Phase 6)
        "mission_enabled": True,
        "mission_persist": True,
        "mission_db_path": "data/missions.db",
        "mission_max_steps": 12,
        "mission_max_attempts": 2,
        "mission_max_duration_seconds": 120,
        "mission_max_tool_calls": 24,
        "mission_max_interactions": 5,
        # Interface web : authentification et contrôle d'origine (Phase 6.1)
        "web_auth_token": "",
        "web_users_file": "",
        "web_allowed_origins": "",
    }

    def __init__(self, config_path: str | None = None) -> None:
        self._values: dict[str, Any] = dict(self.DEFAULTS)

        # 1. Fichier .env (stdlib, pas de dépendance externe).
        # Les variables déjà présentes dans l'environnement du processus
        # sont prioritaires. Le fichier .env est lu dans un dictionnaire
        # local : l'environnement du processus n'est PAS modifié (aucun
        # effet de bord global, suite de tests hermétique).
        dotenv_values = self._load_env_file()

        # 2. Fichier JSON optionnel
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
            # Mémoire persistante locale
            "MILES_MEMORY_ENABLED": "memory_enabled",
            "MILES_MEMORY_DB_PATH": "memory_db_path",
            "MILES_MEMORY_MAX_MEMORIES_IN_CONTEXT": "memory_max_memories_in_context",
            "MILES_MEMORY_MAX_CONTENT_LENGTH": "memory_max_content_length",
            # Persistance de l'historique de conversation (V1)
            "MILES_CONVERSATION_PERSIST": "conversation_persist",
            "MILES_CONVERSATION_DB_PATH": "conversation_db_path",
            # Orchestrateur de missions (Phase 6)
            "MILES_MISSION_ENABLED": "mission_enabled",
            "MILES_MISSION_PERSIST": "mission_persist",
            "MILES_MISSION_DB_PATH": "mission_db_path",
            "MILES_MISSION_MAX_STEPS": "mission_max_steps",
            "MILES_MISSION_MAX_ATTEMPTS": "mission_max_attempts",
            "MILES_MISSION_MAX_DURATION_SECONDS": "mission_max_duration_seconds",
            "MILES_MISSION_MAX_TOOL_CALLS": "mission_max_tool_calls",
            "MILES_MISSION_MAX_INTERACTIONS": "mission_max_interactions",
            # Interface web : authentification et contrôle d'origine (Phase 6.1)
            "MILES_WEB_AUTH_TOKEN": "web_auth_token",
            "MILES_WEB_USERS_FILE": "web_users_file",
            "MILES_WEB_ALLOWED_ORIGINS": "web_allowed_origins",
            # Secrets : jamais codés en dur, lus uniquement depuis l'environnement
            "MILES_REMOTE_API_KEY": "remote_api_key",
            "MILES_LOCAL_API_KEY": "local_api_key",
        }
        # 3. Variables d'environnement : le processus d'abord, puis le
        # fichier .env (jamais l'inverse).
        for env_name, key in env_mapping.items():
            value = os.environ.get(env_name)
            if value is None:
                value = dotenv_values.get(env_name)
            if value is not None:
                # Conversion de type pour les champs numériques
                if key in (
                    "remote_timeout",
                    "local_timeout",
                    "history_limit",
                    "memory_max_memories_in_context",
                    "memory_max_content_length",
                    "mission_max_steps",
                    "mission_max_attempts",
                    "mission_max_duration_seconds",
                    "mission_max_tool_calls",
                    "mission_max_interactions",
                ):
                    try:
                        value = int(value)
                    except ValueError as exc:
                        raise SettingsError(
                            f"La variable {env_name} doit être un entier, valeur reçue: {value!r}"
                        ) from exc
                elif key == "voice_enabled":
                    value = value.lower() in ("1", "true", "yes", "on")
                elif key == "memory_enabled":
                    # Conversion explicite : "false" ne doit pas être
                    # interprété comme vrai par bool().
                    value = _coerce_bool(value, env_name)
                elif key == "conversation_persist":
                    value = _coerce_bool(value, env_name)
                elif key in ("mission_enabled", "mission_persist"):
                    value = _coerce_bool(value, env_name)
                self._values[key] = value

        # Validation
        self._validate()

    def _load_env_file(self) -> dict[str, str]:
        """Lire les variables d'un fichier .env s'il existe.

        Utilise uniquement la bibliothèque standard Python (aucun
        python-dotenv). Les variables déjà présentes dans l'environnement
        du processus sont prioritaires : elles sont ignorées ici.
        Un fichier .env absent n'empêche pas le démarrage.

        Le fichier est lu dans un dictionnaire local : l'environnement du
        processus n'est pas modifié, ce qui évite tout effet de bord
        global (notamment entre deux instances de Settings).
        """
        values: dict[str, str] = {}
        env_path = Path(os.environ.get("MILES_ENV_FILE", ".env"))
        if not env_path.is_file():
            return values
        try:
            with env_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Retirer les guillemets environnants s'ils existent.
                    if (
                        len(value) >= 2
                        and value[0] == value[-1]
                        and value[0] in ('"', "'")
                    ):
                        value = value[1:-1]
                    # Ne pas écraser une variable déjà définie dans le
                    # environnement du processus.
                    if key not in os.environ:
                        values[key] = value
        except OSError:
            # Fichier .env illisible : on ignore, le démarrage continue.
            return values
        return values

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

        max_memories = self._values.get("memory_max_memories_in_context")
        if not isinstance(max_memories, int) or max_memories < 0:
            raise SettingsError(
                f"memory_max_memories_in_context doit être un entier positif, valeur reçue: {max_memories!r}"
            )

        max_content = self._values.get("memory_max_content_length")
        if not isinstance(max_content, int) or max_content < 1:
            raise SettingsError(
                f"memory_max_content_length doit être un entier positif, valeur reçue: {max_content!r}"
            )

        # Normalisation du paramètre booléen mémoire : la valeur peut venir
        # du fichier de configuration JSON sous forme de chaîne ("true" /
        # "false"). Sans cette normalisation, bool("false") vaudrait True et
        # activerait la mémoire persistante malgré une désactivation
        # explicite. Une valeur invalide provoque une erreur explicite.
        if "memory_enabled" in self._values:
            self._values["memory_enabled"] = _coerce_bool(
                self._values["memory_enabled"], "memory_enabled"
            )

        # Même normalisation pour la persistance de la conversation : une
        # chaîne "false" ne doit pas activer silencieusement l'enregistrement
        # de l'historique sur disque.
        if "conversation_persist" in self._values:
            self._values["conversation_persist"] = _coerce_bool(
                self._values["conversation_persist"], "conversation_persist"
            )

        # Même normalisation pour l'orchestrateur de missions.
        for key in ("mission_enabled", "mission_persist"):
            if key in self._values:
                self._values[key] = _coerce_bool(self._values[key], key)

        # Bornes de l'orchestrateur : des valeurs aberrantes doivent être
        # refusées, pas corrigées silencieusement.
        for key, minimum in (
            ("mission_max_steps", 1),
            ("mission_max_attempts", 1),
            ("mission_max_duration_seconds", 1),
            ("mission_max_tool_calls", 1),
            ("mission_max_interactions", 1),
        ):
            value = self._values.get(key)
            if not isinstance(value, int) or value < minimum:
                raise SettingsError(
                    f"{key} doit être un entier >= {minimum}, valeur reçue : {value!r}"
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

    @property
    def memory_enabled(self) -> bool:
        """Indiquer si la mémoire persistante locale est activée.

        La valeur est normalisée en booléen lors de la validation de la
        configuration : la chaîne "false" ne doit jamais être interprétée
        comme vraie.
        """
        return bool(self._values.get("memory_enabled", False))

    @property
    def memory_db_path(self) -> str:
        return str(self._values.get("memory_db_path", "data/memory.db"))

    @property
    def memory_max_memories_in_context(self) -> int:
        return int(self._values.get("memory_max_memories_in_context", 5))

    @property
    def memory_max_content_length(self) -> int:
        return int(self._values.get("memory_max_content_length", 1000))

    @property
    def conversation_persist(self) -> bool:
        """Indiquer si l'historique de conversation doit être persisté.

        La valeur est normalisée en booléen lors de la validation de la
        configuration : la chaîne "false" ne doit jamais être interprétée
        comme vraie.
        """
        return bool(self._values.get("conversation_persist", True))

    @property
    def conversation_db_path(self) -> str:
        return str(self._values.get("conversation_db_path", "data/conversations.db"))

    @property
    def mission_enabled(self) -> bool:
        """Indiquer si l'orchestrateur de missions est activé."""
        return bool(self._values.get("mission_enabled", True))

    @property
    def mission_persist(self) -> bool:
        """Indiquer si les missions doivent être persistées."""
        return bool(self._values.get("mission_persist", True))

    @property
    def mission_db_path(self) -> str:
        return str(self._values.get("mission_db_path", "data/missions.db"))

    @property
    def mission_max_steps(self) -> int:
        return int(self._values.get("mission_max_steps", 12))

    @property
    def mission_max_attempts(self) -> int:
        return int(self._values.get("mission_max_attempts", 2))

    @property
    def mission_max_duration_seconds(self) -> int:
        return int(self._values.get("mission_max_duration_seconds", 120))

    @property
    def mission_max_tool_calls(self) -> int:
        """Plafond global d'appels d'outils par mission."""
        return int(self._values.get("mission_max_tool_calls", 24))

    @property
    def mission_max_interactions(self) -> int:
        """Plafond global d'échanges avec l'utilisateur par mission."""
        return int(self._values.get("mission_max_interactions", 5))
