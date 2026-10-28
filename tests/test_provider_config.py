"""Tests du gestionnaire de configuration multi-fournisseurs (mission L1).

Section « Configuration » de la spec : lecture, ajout, remplacement,
suppression, preservation, protection des secrets, priorite environnement,
configuration invalide, conservation sur echec. ZONE RESEAU INTERDITE.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import provider_config as pc


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="miles-cfg-")
        self.env = os.path.join(self._dossier, ".env")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._dossier, ignore_errors=True)

    def _lire(self) -> str:
        with open(self.env, encoding="utf-8") as fh:
            return fh.read()


class TestLectureEtEtat(_Base):
    def test_statut_sans_secret(self) -> None:
        pc.set_key("groq", "gsk-super-cle-123456", self.env)
        lignes = pc.statut(self.env)
        self.assertEqual(len(lignes), 4)
        self.assertIn("configuree (n=", lignes[0]["cle"])
        brut = repr(lignes)
        self.assertNotIn("gsk-super-cle", brut)
        self.assertNotIn("gsk-super-cle", self._lire().split("MILES_API_KEY_GROQ=", 1)[0])  # journal jamais

    def test_statut_configuration_initiale(self) -> None:
        lignes = pc.statut(self.env)
        for entree in lignes:
            self.assertIsNone(entree["cle"])
        # actif par defaut : groq (retrocompat historique)
        self.assertTrue([e for e in lignes if e["provider"] == "groq"][0]["actif"])


class TestCles(_Base):
    def test_ajout_puis_remplacement(self) -> None:
        self.assertEqual(pc.set_key("openai", "sk-aaaa1111", self.env), "nouvelle")
        self.assertEqual(pc.set_key("openai", "sk-bbbb2222", self.env), "remplacee")
        self.assertIn("MILES_API_KEY_OPENAI=sk-bbbb2222", self._lire())
        self.assertNotIn("sk-aaaa1111", self._lire())

    def test_preservation_des_parametres(self) -> None:
        with open(self.env, "w", encoding="utf-8") as fh:
            fh.write("# mon commentaire\nMILES_MISSION_MAX_STEPS=7\nHISTORIQUE=x\n")
        pc.set_key("gemini", "AIza-fake-cle-999", self.env)
        contenu = self._lire()
        self.assertIn("# mon commentaire", contenu)
        self.assertIn("MILES_MISSION_MAX_STEPS=7", contenu)
        self.assertIn("HISTORIQUE=x", contenu)
        self.assertIn("MILES_API_KEY_GEMINI=AIza-fake-cle-999", contenu)

    def test_cle_invalide(self) -> None:
        for mauvaise in ("", 'avec"guillemet', "avec\nsaut", "x" * 600):
            with self.subTest(cle=repr(mauvaise)[:20]):
                with self.assertRaises(ValueError):
                    pc.set_key("anthropic", mauvaise, self.env)

    def test_fournisseur_inconnu(self) -> None:
        with self.assertRaises(ValueError):
            pc.set_key("mistral-inconnu-ici", "cle", self.env)

    def test_suppression_clé(self) -> None:
        pc.set_key("groq", "gsk-abcdef", self.env)
        self.assertTrue(pc.remove_key("groq", self.env))
        self.assertNotIn("MILES_API_KEY_GROQ", self._lire())
        self.assertFalse(pc.remove_key("groq", self.env))  # deja absente

    def test_suppression_fournisseur_actif_retire_aussi_remote(self) -> None:
        pc.set_key("groq", "gsk-abcdef", self.env)
        pc.activate("groq", self.env)
        self.assertIn("MILES_REMOTE_API_KEY=gsk-abcdef", self._lire())
        pc.remove_key("groq", self.env)
        contenu = self._lire()
        self.assertNotIn("MILES_API_KEY_GROQ", contenu)
        self.assertNotIn("MILES_REMOTE_API_KEY", contenu)
        # les autres parametres restent
        self.assertIn("MILES_REMOTE_PROVIDER=groq", contenu)


class TestActivation(_Base):
    def test_activation_recopie_vers_remote(self) -> None:
        pc.set_key("anthropic", "sk-ant-fake-000", self.env)
        pc.set_model("anthropic", "claude-3-5-haiku", self.env)
        info = pc.activate("anthropic", self.env)
        self.assertEqual(info["provider"], "anthropic")
        self.assertNotIn("sk-ant", repr(info))  # jamais de secret dans le retour
        contenu = self._lire()
        self.assertIn("MILES_REMOTE_PROVIDER=anthropic", contenu)
        self.assertIn("MILES_REMOTE_API_KEY=sk-ant-fake-000", contenu)
        self.assertIn("MILES_REMOTE_MODEL=claude-3-5-haiku", contenu)

    def test_activation_sans_cle_echoue_et_preserve(self) -> None:
        pc.set_key("groq", "gsk-avant", self.env)
        pc.activate("groq", self.env)
        avant = self._lire()
        # Environnement neutralise pour ce test (aucune cle artificielle).
        with patch.dict(os.environ, {"MILES_API_KEY_OPENAI": ""}):
            with self.assertRaises(ValueError):
                pc.activate("openai", self.env)  # aucune cle openai
        self.assertEqual(self._lire(), avant)  # configuration precedente intacte


class TestPrioriteEnvironnement(_Base):
    def test_variables_environnement_signalees(self) -> None:
        with patch.dict(os.environ, {"MILES_API_KEY_GEMINI": "AIza-env"}):
            self.assertIn("MILES_API_KEY_GEMINI", pc.environnement_prioritaire("gemini"))
        self.assertEqual(pc.environnement_prioritaire("anthropic"), [])

    def test_env_masque_le_fichier(self) -> None:
        # Une cle en environnement prime sur .env : le statut doit la voir.
        with patch.dict(os.environ, {"MILES_API_KEY_OPENAI": "sk-env-123456"}):
            statut = pc.statut(self.env)
            openai = [e for e in statut if e["provider"] == "openai"][0]
            self.assertIsNotNone(openai["cle"])
        statut_sans = pc.statut(self.env)
        openai_sans = [e for e in statut_sans if e["provider"] == "openai"][0]
        self.assertIsNone(openai_sans["cle"])


if __name__ == "__main__":
    unittest.main()
