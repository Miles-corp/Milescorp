"""Anti-dérive des `.env.example` (DEC-016 du lot paquets téléchargeables).

La racine `.env.example` est la source de vérité. Le paquet pc-miles en
dérive ; ce test échoue dès qu'une variable de la racine manque dans le
paquet — c'est exactement la « dérive silencieuse » qu'interdit DEC-016.
"""

from __future__ import annotations

import pathlib
import re
import unittest

RACINE = pathlib.Path(".env.example")
PAQUET = pathlib.Path("hardware/packages/pc-miles/.env.example")

_CLE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _cles(chemin: pathlib.Path) -> set[str]:
    """Clés MILES_* effectivement définies (lignes actives, pas commentées)."""
    trouvees: set[str] = set()
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if ligne.lstrip().startswith("#"):
            continue
        m = _CLE.match(ligne)
        if m and m.group(1).startswith("MILES_"):
            trouvees.add(m.group(1))
    return trouvees


class TestEnvExampleAligne(unittest.TestCase):
    def test_fichiers_presents(self) -> None:
        self.assertTrue(RACINE.is_file(), ".env.example racine absent")
        self.assertTrue(PAQUET.is_file(), ".env.example du paquet pc-miles absent")

    def test_paquet_contient_toutes_les_variables_racine(self) -> None:
        """Toute variable active de la racine existe aussi dans le paquet."""
        racine = _cles(RACINE)
        paquet = _cles(PAQUET)
        self.assertTrue(racine, "aucune variable MILES_* lue dans la racine")
        manquantes = racine - paquet
        self.assertEqual(
            manquantes,
            set(),
            "Variables de la racine absentes du paquet pc-miles "
            "(dérive interdite par DEC-016) : %s" % sorted(manquantes),
        )

    def test_le_paquet_peut_etendre_la_racine(self) -> None:
        """Les variables propres au boîtier sont autorisées en plus."""
        paquet = _cles(PAQUET) - _cles(RACINE)
        inattendues = paquet - {"MILES_BOX_KEY"}
        self.assertEqual(
            inattendues,
            set(),
            "Variables inattendues dans le paquet (à justifier) : "
            "%s" % sorted(inattendues),
        )

    def test_aucune_cle_api_en_clair(self) -> None:
        """Aucune valeur réelle de clé dans les deux fichiers."""
        for chemin in (RACINE, PAQUET):
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                if ligne.lstrip().startswith("#"):
                    continue
                m = _CLE.match(ligne)
                if not m or not m.group(1).endswith("API_KEY"):
                    continue
                valeur = ligne.split("=", 1)[1].strip()
                self.assertFalse(
                    valeur,
                    f"{chemin} : {m.group(1)} porte une valeur — "
                    "les clés API se saisissent via --setup, jamais en clair.",
                )


if __name__ == "__main__":
    unittest.main()
