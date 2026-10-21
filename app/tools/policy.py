"""Politique de sécurité des outils MILES.

Règles immuables appliquées avant toute exécution d'outil. Cette classe ne
décide pas ce qui est autorisé : elle vérifie que la demande respecte la
politique définie par l'application.

Distingue deux natures de valeurs :

- les **valeurs libres** (texte fourni par le modèle) : le contrôle est une
  correspondance **par sous-chaîne** sur les mots interdits ;
- les **valeurs de chemin** (paramètres déclarés comme tels dans le schéma
  de l'outil) : le contrôle est **structurel** (caractères de contrôle et
  métacaractères de commande). Un répertoire dont le nom contient « source »,
  « code » ou « script » est ainsi accepté par la politique, ce qui ne
  constitue aucun accès : le confinement des chemins
  (`app.security.paths`) reste la seule autorité sur les fichiers
  réellement accessibles.
"""

from __future__ import annotations

from typing import Any, Iterable, Set


#: Caractères de contrôle : jamais valides dans un chemin de fichier.
#: L'octet nul est le vecteur classique de troncature, le saut de ligne un
#: vecteur d'injection de journal.
PATH_CONTROL_CHARS = ("\x00", "\n", "\r")

#: Métacaractères de commande : invalides dans un chemin Windows et
#: porteurs d'injection de commande.
#:
#: « & » et « $ » en sont **exclus** : ils apparaissent dans des
#: répertoires légitimes (« Rock & Roll », « $Recycle.Bin »,
#: « $Windows.~BT ») et MILES n'a aucun interpréteur de commandes — c'est
#: le confinement des chemins qui décide de l'accès. Les exclure ne retire
#: donc aucune protection existante.
PATH_COMMAND_CHARS = (";", "|", "`", "<", ">")


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
    def _iter_values(obj: Any, in_path: bool = False):
        """Parcourir récursivement toutes les valeurs d'une structure imbriquée.

        Chaque valeur est accompagnée d'un indicateur ``in_path`` : True
        seulement pour la valeur **directe** d'un paramètre de type chemin.
        Les valeurs imbriquées ne sont jamais exemptées du contrôle par
        sous-chaîne : un paramètre de type chemin est toujours une chaîne,
        toute autre structure est une erreur de type, refusée plus loin.
        """
        if isinstance(obj, dict):
            for value in obj.values():
                yield from ToolPolicy._iter_values(value, False)
        elif isinstance(obj, (list, tuple, set)):
            for value in obj:
                yield from ToolPolicy._iter_values(value, False)
        else:
            yield obj, in_path

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

    @staticmethod
    def _validate_path_value(value: str) -> None:
        """Valider structurellement une valeur de chemin.

        Un chemin ne peut pas contenir de caractère de contrôle (octet nul,
        saut de ligne) ni de métacaractère de commande : ces caractères
        sont invalides dans un chemin Windows et porteurs d'injection.
        """
        for char in value:
            if char in PATH_CONTROL_CHARS or char in PATH_COMMAND_CHARS:
                raise PermissionError(
                    f"Valeur interdite (chemin non conforme) : {value}"
                )

    def _reject_sensitive_keys(
        self, parameters: dict[str, Any], forbidden_keys: Set[str], label: str
    ) -> None:
        """Refuser un paramètre dont la CLÉ est interdite (correspondance exacte)."""
        for key in self._iter_keys(parameters):
            if isinstance(key, str) and key.lower() in forbidden_keys:
                raise PermissionError(
                    f"Paramètre interdit ({label}) : {key}"
                )

    def _reject_sensitive_values(
        self,
        parameters: dict[str, Any],
        forbidden_keys: Set[str],
        path_parameters: Iterable[str],
        label: str,
    ) -> None:
        """Refuser une valeur interdite.

        Les valeurs de chemin (paramètres déclarés comme tels) sont validées
        **structurellement** ; les autres valeurs sont contrôlées par
        sous-chaîne, comme avant.
        """
        exempts = set(path_parameters or ())
        for key, value in parameters.items():
            # Seule une valeur **directe** d'un paramètre de type chemin
            # benefits de l'exemption : une structure imbriquée sous un tel
            # paramètre n'est pas un chemin (erreur de type, refusée plus
            # loin) et reste soumise au contrôle par sous-chaîne.
            is_path = key in exempts and isinstance(value, str)
            for item, path_value in self._iter_values(value, is_path):
                if path_value:
                    self._validate_path_value(item)
                    continue
                if isinstance(item, str):
                    lowered = item.lower()
                    if any(k in lowered for k in forbidden_keys):
                        raise PermissionError(
                            f"Valeur interdite ({label}) : {item}"
                        )

    def validate_no_shell_access(
        self,
        parameters: dict[str, Any],
        path_parameters: Iterable[str] = (),
    ) -> None:
        """Rejeter toute tentative d'accès shell arbitraire.

        Args:
            parameters : paramètres demandés par le modèle.
            path_parameters : noms des paramètres déclarés comme chemins ;
                leurs valeurs sont validées structurellement au lieu du
                contrôle par sous-chaîne.
        """
        forbidden_keys = {"shell", "command", "cmd", "exec", "eval", "run", "system"}
        self._reject_sensitive_keys(parameters, forbidden_keys, "accès shell")
        self._reject_sensitive_values(
            parameters, forbidden_keys, path_parameters, "accès shell"
        )

    def validate_no_code_execution(
        self,
        parameters: dict[str, Any],
        path_parameters: Iterable[str] = (),
    ) -> None:
        """Rejeter toute tentative d'exécution de code généré par le modèle.

        Args:
            parameters : paramètres demandés par le modèle.
            path_parameters : noms des paramètres déclarés comme chemins ;
                leurs valeurs sont validées structurellement au lieu du
                contrôle par sous-chaîne.
        """
        code_keys = {"code", "script", "python", "javascript", "shell_code", "source"}
        self._reject_sensitive_keys(parameters, code_keys, "exécution de code")
        self._reject_sensitive_values(
            parameters, code_keys, path_parameters, "exécution de code"
        )

    def validate_no_secret_access(
        self,
        parameters: dict[str, Any],
        path_parameters: Iterable[str] = (),
    ) -> None:
        """Rejeter toute tentative d'accès à des secrets ou mots de passe.

        Args:
            parameters : paramètres demandés par le modèle.
            path_parameters : noms des paramètres déclarés comme chemins ;
                leurs valeurs sont validées structurellement au lieu du
                contrôle par sous-chaîne.
        """
        secret_keys = {"password", "secret", "api_key", "token", "private_key", "credential", "apikey", "access_key", "secret_key"}
        self._reject_sensitive_keys(parameters, secret_keys, "accès aux secrets")
        self._reject_sensitive_values(
            parameters, secret_keys, path_parameters, "accès aux secrets"
        )
