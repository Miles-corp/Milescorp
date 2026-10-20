"""Package de tests de MILES.

Hergénéité de la suite de tests : le fichier ``.env`` local du développeur
ne doit pas influencer les résultats. ``MILES_ENV_FILE`` est donc redirigé
vers un chemin inexistant pour toute la session de test.

Un développeur qui souhaite volontairement tester avec un ``.env``
particulier peut définir ``MILES_ENV_FILE`` avant de lancer la suite : dans
ce cas, la valeur existante est conservée.
"""

import os
import tempfile

if "MILES_ENV_FILE" not in os.environ:
    os.environ["MILES_ENV_FILE"] = os.path.join(
        tempfile.gettempdir(), "miles_tests_no_such_env_file"
    )
