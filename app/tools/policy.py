"""Politique de sécurité des outils MILES.

Règles immuables appliquées avant toute exécution d'outil. Cette classe ne
décide pas ce qui est autorisé : elle vérifie que la demande respecte la
politique définie par l'application.
"""

from __future__ import annotations

from typing import Any, Set


class ToolPolicy:
    """Politique de sécurité pour les outils MILES.

    Règles :
    - Aucun shell arbitraire.
    - Aucun exec()/eval() de code généré.
    - Aucune lecture de fichier hors chemins autorisés.
    - Aucune action réseau, dépense, suppression ou commande sensible sans
      permission explicite.
    - Aucune extension automatique des permissions par le modèle.
    """

    _SHELL_KEYS = {"shell", "command", "cmd", "exec", "eval", "run", "system"}
    _CODE_KEYS = {"code", "script", "python", "javascript", "shell_code", "source"}
    _SECRET_KEYS = {
        "password", "secret", "api_key", "token", "private_key", "credential",
        "apikey", "access_key", "secret_key",
    }

    def __init__(self, granted_permissions: Set[str]) -> None:
        self._granted_permissions: Set[str] = set(granted_permissions)

    def has_permission(self, permission: str) -> bool:
        """Vérifier qu'une permission est accordée par l'application."""
        return permission in self._granted_permissions

    def has_all_permissions(self, permissions: tuple[str, ...]) -> bool:
        """Vérifier que toutes les permissions requises sont accordées."""
        return all(permission in self._granted_permissions for permission in permissions)

    def is_risk_level_valid(self, risk_level: str) -> bool:
        """Vérifier qu'un niveau de risque est reconnu."""
        return risk_level in ("LOW", "MEDIUM", "HIGH")

    def requires_human_confirmation(self, risk_level: str) -> bool:
        """Déterminer si une confirmation humaine explicite est requise."""
        return risk_level in ("MEDIUM", "HIGH")

    @staticmethod
    def _iter_values(obj: Any):
        """Parcourir récursivement toutes les valeurs d'une structure imbriquée."""
        if isinstance(obj, dict):
            for value in obj.values():
                yield from ToolPolicy._iter_values(value)
        elif isinstance(obj, (list, tuple, set)):
            for value in obj:
                yield from ToolPolicy._iter_values(value)
        else:
            yield obj

    @staticmethod
    def _iter_keys(obj: Any):
        """Parcourir récursivement toutes les clés d'une structure imbriquée."""
        if isinstance(obj, dict):
            for key in obj.keys():
                yield key
                yield from ToolPolicy._iter_keys(key)
        elif isinstance(obj, (list, tuple, set)):
            for value in obj:
                yield from ToolPolicy._iter_keys(value)

    def validate_no_shell_access(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'accès shell arbitraire."""
        forbidden_keys = {"shell", "command", "cmd", "exec", "eval", "run", "system"}
        for key in self._iter_keys(parameters):
            if isinstance(key, str) and key.lower() in forbidden_keys:
                raise PermissionError(
                    f"Paramètre interdit (accès shell) : {key}"
                )
        for value in self._iter_values(parameters):
            if isinstance(value, str):
                lowered = value.lower()
                if any(k in lowered for k in forbidden_keys):
                    raise PermissionError(
                        f"Valeur interdite (accès shell) : {value}"
                    )

    def validate_no_code_execution(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'exécution de code généré par le modèle."""
        code_keys = {"code", "script", "python", "javascript", "shell_code", "source"}
        for key in self._iter_keys(parameters):
            if isinstance(key, str) and key.lower() in code_keys:
                raise PermissionError(
                    f"Paramètre interdit (exécution de code) : {key}"
                )
        for value in self._iter_values(parameters):
            if isinstance(value, str):
                lowered = value.lower()
                if any(k in lowered for k in code_keys):
                    raise PermissionError(
                        f"Valeur interdite (exécution de code) : {value}"
                    )

    def validate_no_secret_access(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'accès à des secrets ou mots de passe."""
        secret_keys = {"password", "secret", "api_key", "token", "private_key", "credential", "apikey", "access_key", "secret_key"}
        for key in self._iter_keys(parameters):
            if isinstance(key, str) and key.lower() in secret_keys:
                raise PermissionError(
                    f"Paramètre interdit (accès aux secrets) : {key}"
                )
        for value in self._iter_values(parameters):
            if isinstance(value, str):
                lowered = value.lower()
                if any(k in lowered for k in secret_keys):
                    raise PermissionError(
                        f"Valeur interdite (accès aux secrets) : {value}"
                    )
