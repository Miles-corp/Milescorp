"""Tests de la mémoire persistante de MILES.

Ces tests couvrent le cycle de vie complet des souvenirs :

1. enregistrer un souvenir ;
2. le retrouver (liste) ;
3. le supprimer par identifiant ;
4. les souvenirs conservés sont toujours disponibles après un **redémarrage**
   (nouvelle instance sur la même base) ;
5. un souvenir supprimé ne réapparaît pas après redémarrage ;
6. le comportement en cas de base **absente**, **vide** ou **endommagée** ;
7. l'**isolation entre utilisateurs** : les souvenirs d'un utilisateur ne
   sont ni listés ni supprimables par un autre.

Ils couvrent aussi les deux interfaces : la console (`/remember`,
`/memory`, `/forget`) et l'interface web (`POST /remember`, `GET /memory`,
`POST /forget`).

Les tests sont non destructifs : bases temporaires, répertoires
temporaires, aucun appel à un fournisseur, aucune donnée réelle lue ni
écrite.
"""

from __future__ import annotations

import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from typing import List, Optional

from app.config.settings import Settings
from app.interface.cli import CLI
from app.interface.web import WebApp
from app.interface.web_auth import WebAuthenticator, WebCredentialStore
from app.memory.persistent import PersistentMemory, PersistentMemoryError
from app.tools.service import ToolService


#: Jetons d'accès des clients de test.
JETON_ALICE = "jeton-alice-0123456789"
JETON_BOB = "jeton-bob-0123456789"

#: Les deux commandes de la console sont lues par le test.
COMMANDES = ("/remember", "/memory", "/forget")


class _BaseMemoire(unittest.TestCase):
    """Base : base temporaire, supprimée à la fin du test."""

    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="miles-memoire-")
        self.addCleanup(shutil.rmtree, self._dossier, True)
        self.db_path = os.path.join(self._dossier, "memory.db")

    def _memoire(self, **kwargs) -> PersistentMemory:
        """Ouvrir une mémoire persistante sur la base temporaire."""
        memoire = PersistentMemory(enabled=True, db_path=self.db_path, **kwargs)
        self.addCleanup(memoire.close)
        return memoire


# ---------------------------------------------------------------------------
# 1 à 3 — cycle de vie d'un souvenir
# ---------------------------------------------------------------------------

class TestCycleDeVieDesSouvenirs(_BaseMemoire):
    """Enregistrer, retrouver, supprimer."""

    def test_enregistrer_un_souvenir(self) -> None:
        """1. Un souvenir est enregistré et porte un identifiant."""
        memoire = self._memoire()
        self.assertTrue(memoire.is_available)
        identifiant = memoire.add_memory("Je préfère le thé.")
        self.assertIsInstance(identifiant, int)
        self.assertGreater(identifiant, 0)

    def test_retrouver_un_souvenir_par_la_liste(self) -> None:
        """2. Le souvenir est retrouvé dans la liste."""
        memoire = self._memoire()
        identifiant = memoire.add_memory("J'aime les Hitchhiker.")
        souvenirs = memoire.list_memories()
        self.assertEqual(len(souvenirs), 1)
        self.assertEqual(souvenirs[0]["id"], identifiant)
        self.assertEqual(souvenirs[0]["content"], "J'aime les Hitchhiker.")

    def test_supprimer_un_souvenir_par_identifiant(self) -> None:
        """3. Le souvenir est supprimé par son identifiant."""
        memoire = self._memoire()
        identifiant = memoire.add_memory("À supprimer")
        self.assertTrue(memoire.delete_memory(identifiant))
        self.assertEqual(memoire.list_memories(), [])
        # Une seconde suppression ne réussit pas.
        self.assertFalse(memoire.delete_memory(identifiant))


# ---------------------------------------------------------------------------
# 4 et 5 — persistance après redémarrage
# ---------------------------------------------------------------------------

class TestPersistanceApresRedemarrage(_BaseMemoire):
    """Les souvenirs survivent à la fermeture et au redémarrage."""

    def test_les_souvenirs_survivent_a_un_redemarrage(self) -> None:
        """4. Après redémarrage, les souvenirs conservés sont disponibles."""
        premiere = self._memoire()
        identifiant = premiere.add_memory("Conservé après redémarrage.")
        premiere.close()

        seconde = PersistentMemory(enabled=True, db_path=self.db_path)
        self.addCleanup(seconde.close)
        souvenirs = seconde.list_memories()
        self.assertEqual(len(souvenirs), 1)
        self.assertEqual(souvenirs[0]["id"], identifiant)
        self.assertEqual(souvenirs[0]["content"], "Conservé après redémarrage.")

    def test_un_souvenir_supprime_ne_reapparait_pas(self) -> None:
        """5. Un souvenir supprimé ne réapparaît pas après redémarrage."""
        premiere = self._memoire()
        a_supprimer = premiere.add_memory("À supprimer définitivement")
        premiere.add_memory("Conservé")
        self.assertTrue(premiere.delete_memory(a_supprimer))
        premiere.close()

        seconde = PersistentMemory(enabled=True, db_path=self.db_path)
        self.addCleanup(seconde.close)
        contenus = [m["content"] for m in seconde.list_memories()]
        self.assertEqual(contenus, ["Conservé"])

    def test_les_preferences_survivent_a_un_redemarrage(self) -> None:
        """4b. Les préférences survivent aussi (mémorisation de l'état)."""
        premiere = self._memoire()
        premiere.set_preference("style", "concise")
        premiere.close()

        seconde = PersistentMemory(enabled=True, db_path=self.db_path)
        self.addCleanup(seconde.close)
        self.assertEqual(seconde.get_preference("style"), "concise")


# ---------------------------------------------------------------------------
# 6 — base absente, vide ou endommagée
# ---------------------------------------------------------------------------

class TestBaseDeDonneesDegradee(_BaseMemoire):
    """Le comportement en cas de base absente, vide ou endommagée."""

    def test_base_absente_elle_est_creee(self) -> None:
        """6a. Une base absente est créée."""
        self.assertFalse(os.path.exists(self.db_path))
        memoire = self._memoire()
        self.assertTrue(memoire.is_available)
        self.assertTrue(os.path.exists(self.db_path))
        memoire.add_memory("Premier souvenir")
        self.assertEqual(len(memoire.list_memories()), 1)

    def test_base_vide_elle_est_initialisee(self) -> None:
        """6b. Une base vide (fichier de zéro octet) est initialisée."""
        with open(self.db_path, "wb"):
            pass
        memoire = self._memoire()
        self.assertTrue(memoire.is_available)
        memoire.add_memory("Premier souvenir")
        self.assertEqual(len(memoire.list_memories()), 1)

    def test_base_endommagee_degradation_gracieuse(self) -> None:
        """6c. Une base endommagée : dégradation gracieuse, aucune exception."""
        with open(self.db_path, "w", encoding="utf-8") as fh:
            fh.write("ceci n'est pas une base sqlite")
        memoire = self._memoire()
        self.assertFalse(memoire.is_available)
        # Les opérations lèvent une erreur explicite, jamais une exception
        # inattendue.
        with self.assertRaises(PersistentMemoryError):
            memoire.add_memory("test")
        with self.assertRaises(PersistentMemoryError):
            memoire.list_memories()
        with self.assertRaises(PersistentMemoryError):
            memoire.delete_memory(1)
        # Le contexte IA reste vide, sans erreur.
        self.assertEqual(memoire.get_context_memories(), [])

    def test_memoire_desactivee_operations_refusees(self) -> None:
        """6d. Une mémoire désactivée refuse toute opération."""
        memoire = PersistentMemory(enabled=False, db_path=self.db_path)
        self.assertFalse(memoire.is_available)
        with self.assertRaises(PersistentMemoryError):
            memoire.add_memory("test")


# ---------------------------------------------------------------------------
# 7 — isolation entre utilisateurs
# ---------------------------------------------------------------------------

class TestIsolationEntreUtilisateurs(_BaseMemoire):
    """Les souvenirs d'un utilisateur ne sont pas accessibles à un autre."""

    def _app(self, memoire: PersistentMemory) -> WebApp:
        authentificateur = WebAuthenticator(
            WebCredentialStore({"alice": JETON_ALICE, "bob": JETON_BOB})
        )
        return WebApp(
            settings=Settings(),
            tool_service=ToolService(),
            memory=memoire,
            authenticator=authentificateur,
        )

    def test_un_utilisateur_ne_voit_pas_les_souvenirs_d_un_autre(self) -> None:
        """7a. La liste d'un utilisateur ne contient pas les souvenirs d'un
        autre."""
        memoire = self._memoire()
        app = self._app(memoire)
        session_alice = app.authenticator.login(JETON_ALICE)
        session_bob = app.authenticator.login(JETON_BOB)

        app.add_memory("note personnelle d'alice", owner_user_id="alice")
        app.add_memory("note personnelle de bob", owner_user_id="bob")

        liste_alice = app.list_memories(owner_user_id=session_alice.user_id)
        contenus_alice = [m["content"] for m in liste_alice]
        self.assertIn("note personnelle d'alice", contenus_alice)
        self.assertNotIn(
            "note personnelle de bob",
            contenus_alice,
            "un utilisateur voit les souvenirs d'un autre",
        )

        liste_bob = app.list_memories(owner_user_id=session_bob.user_id)
        contenus_bob = [m["content"] for m in liste_bob]
        self.assertIn("note personnelle de bob", contenus_bob)
        self.assertNotIn("note personnelle d'alice", contenus_bob)

    def test_un_utilisateur_ne_peut_pas_supprimer_les_souvenirs_d_un_autre(
        self,
    ) -> None:
        """7b. Un utilisateur ne peut pas supprimer les souvenirs d'un
        autre."""
        memoire = self._memoire()
        app = self._app(memoire)
        session_alice = app.authenticator.login(JETON_ALICE)
        session_bob = app.authenticator.login(JETON_BOB)

        identifiant = app.add_memory(
            "note personnelle d'alice", owner_user_id=session_alice.user_id
        )
        resultat = app.delete_memory(
            identifiant["id"], owner_user_id=session_bob.user_id
        )
        self.assertFalse(
            resultat.get("deleted"),
            "un utilisateur a supprime le souvenir d'un autre",
        )
        # Le souvenir est toujours la.
        restants = memoire.list_memories(owner_user_id="alice")
        self.assertEqual(len(restants), 1)

    def test_le_proprietaire_est_persiste(self) -> None:
        """7c. Le propriétaire du souvenir est écrit en base et relu."""
        memoire = self._memoire()
        identifiant = memoire.add_memory("mien", owner_user_id="alice")
        memoire.close()

        relue = PersistentMemory(enabled=True, db_path=self.db_path)
        self.addCleanup(relue.close)
        souvenir = relue.get_memory(identifiant)
        self.assertIsNotNone(souvenir)
        self.assertEqual(souvenir["owner_user_id"], "alice")

    def test_les_souvenirs_existants_sont_partages(self) -> None:
        """7d. Les souvenirs enregistrés avant l'isolation (propriétaire
        inconnu) restent visibles : ils ne sont attribués à personne."""
        memoire = self._memoire()
        identifiant = memoire.add_memory("ancien souvenir")
        memoire.close()

        relue = PersistentMemory(enabled=True, db_path=self.db_path)
        self.addCleanup(relue.close)
        partage = relue.list_memories(owner_user_id="alice")
        self.assertEqual(len(partage), 1)
        self.assertEqual(partage[0]["id"], identifiant)


# ---------------------------------------------------------------------------
# Les deux interfaces : console et web
# ---------------------------------------------------------------------------

class TestCommandesConsoleMemoire(_BaseMemoire):
    """Les commandes `/remember`, `/memory` et `/forget` de la console."""

    def _cli(self, memoire: PersistentMemory) -> CLI:
        return CLI(
            settings=Settings(),
            provider=None,
            conversation=None,
            validator=None,
            memory=memoire,
            tool_service=ToolService(),
            mission_runner=None,
            session_id="session-cli",
        )

    def test_les_commandes_existent(self) -> None:
        """Les trois commandes sont annoncées dans l'aide."""
        memoire = self._memoire()
        cli = self._cli(memoire)
        aide = io.StringIO()
        with redirect_stdout(aide):
            cli._handle_command("/help")
        texte = aide.getvalue()
        for commande in COMMANDES:
            self.assertIn(commande, texte)

    def test_cycle_complet_en_console(self) -> None:
        """Enregistrer, lister et supprimer depuis la console."""
        memoire = self._memoire()
        cli = self._cli(memoire)
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli._handle_command("/remember Je préfère le thé.")
        texte = sortie.getvalue()
        self.assertIn("enregistré", texte.lower())
        self.assertEqual(len(memoire.list_memories()), 1)

        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli._handle_command("/memory")
        self.assertIn("préfère", sortie.getvalue())

        identifiant = memoire.list_memories()[0]["id"]
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli._handle_command(f"/forget {identifiant}")
        self.assertIn("supprimé", sortie.getvalue().lower())
        self.assertEqual(memoire.list_memories(), [])

    def test_une_reponse_incomprenable_ne_supprime_pas(self) -> None:
        """Un identifiant invalide ne supprime rien."""
        memoire = self._memoire()
        cli = self._cli(memoire)
        memoire.add_memory("à garder")
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli._handle_command("/forget pas-un-nombre")
        self.assertIn("nombre", sortie.getvalue().lower())
        self.assertEqual(len(memoire.list_memories()), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
