"""Package de tests de MILES.

Hétérogénéité de la suite de tests : le fichier ``.env`` local du développeur
ne doit pas influencer les résultats. ``MILES_ENV_FILE`` est donc redirigé
vers un chemin inexistant pour toute la session de test.

Le chemin d'isolation est créé dans un répertoire temporaire **unique par
session** (``tempfile.mkdtemp``) : un nom fixe et prévisible serait un piège,
car une exécution qui écrit dans ce chemin (une autre branche, un test
d'intégration, un script) le rendrait existant pour toutes les sessions
suivantes. C'est exactement ainsi que deux tests ont échoué : un fichier
``.env`` laissé dans ``%TEMP%`` par une exécution antérieure fournissait un
``MILES_REMOTE_MODEL=`` vide à toute la suite.

Un développeur qui souhaite volontairement tester avec un ``.env``
particulier peut définir ``MILES_ENV_FILE`` avant de lancer la suite : dans
ce cas, la valeur existante est conservée et aucune redirection n'a lieu.
"""

import atexit
import os
import shutil
import tempfile

#: Nom (obsolète) du chemin fixe utilisé avant l'isolation par session.
LEGACY_ISOLATION_PATH = os.path.join(
    tempfile.gettempdir(), "miles_tests_no_such_env_file"
)

_isolation_directory: str | None = None


def _install_env_isolation() -> None:
    """Rediriger ``MILES_ENV_FILE`` vers un chemin unique et inexistant."""
    global _isolation_directory
    if "MILES_ENV_FILE" in os.environ:
        # Un chemin imposé par l'utilisateur est conservé tel quel.
        return
    directory = tempfile.mkdtemp(prefix="miles-tests-env-")
    os.environ["MILES_ENV_FILE"] = os.path.join(directory, "absent.env")
    _isolation_directory = directory
    atexit.register(shutil.rmtree, directory, True)


def isolation_directory() -> str | None:
    """Répertoire d'isolation de la session, ou ``None`` si l'utilisateur impose le sien."""
    return _isolation_directory


def isolation_env_path() -> str | None:
    """Chemin ``.env`` isolé de la session, ou ``None`` si l'utilisateur impose le sien."""
    if _isolation_directory is None:
        return None
    return os.environ.get("MILES_ENV_FILE")


_install_env_isolation()
