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

    def validate_no_shell_access(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'accès shell arbitraire."""
        forbidden_keys = {"shell", "command", "cmd", "exec", "eval", "run", "system"}
        for key in parameters:
            if key.lower() in forbidden_keys:
                raise PermissionError(
                    f"Paramètre interdit (accès shell) : {key}"
                )

    def validate_no_code_execution(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'exécution de code généré par le modèle."""
        code_keys = {"code", "script", "python", "javascript", "shell_code", "source"}
        for key in parameters:
            if key.lower() in code_keys:
                raise PermissionError(
                    f"Paramètre interdit (exécution de code) : {key}"
                )

    def validate_no_secret_access(self, parameters: dict[str, Any]) -> None:
        """Rejeter toute tentative d'accès à des secrets ou mots de passe."""
        secret_keys = {"password", "secret", "api_key", "token", "private_key", "credential"}
        for key in parameters:
            if key.lower() in secret_keys:
                raise PermissionError(
                    f"Paramètre interdit (accès aux secrets) : {key}"
                )
