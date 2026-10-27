"""Tests de la mémoire avancée (spéc MEMOIRE_AVANCEE, v3) — §6 de la spec.

Invariants : migration non destructive, kind 'inconnu' par défaut (jamais
d'auto-promotion en fait), détection stricte (duplique/négation exacte),
isolation des liens par propriétaire, zéro réseau dans le module.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from app.memory.persistent import PersistentMemory, PersistentMemoryError


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._dossier = tempfile.mkdtemp(prefix="miles-memoire-av-")
        self.chemin = os.path.join(self._dossier, "memory.db")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._dossier, ignore_errors=True)

    def _memoire(self) -> PersistentMemory:
        return PersistentMemory(enabled=True, db_path=self.chemin)


class TestMigrationV3(_Base):
    def test_colonne_kind_et_table_liens_creees(self) -> None:
        mem = self._memoire()
        mem.add_memory("souvenir de base")
        conn = sqlite3.connect(self.chemin)
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(memories)")}
        self.assertIn("kind", colonnes)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("memory_links", tables)
        row = conn.execute("SELECT kind FROM memories").fetchone()
        self.assertEqual(row[0], "inconnu")  # défaut honnête, rien n'est prouvé
        conn.close()
        mem.close()

    def test_base_v2_existante_migree_sans_perte(self) -> None:
        # Simule une base v2 créée avant la migration (sans kind).
        conn = sqlite3.connect(self.chemin)
        conn.execute("""CREATE TABLE schema_version (version INTEGER PRIMARY KEY)""")
        conn.execute("INSERT INTO schema_version VALUES (2)")
        conn.execute("""CREATE TABLE memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            importance INTEGER NOT NULL DEFAULT 1,
            owner_user_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO memories (content, created_at, updated_at) VALUES (?, ?, ?)",
            ("ancien souvenir", "2026-01-01", "2026-01-01"),
        )
        conn.commit()
        conn.close()
        mem = self._memoire()
        conn = sqlite3.connect(self.chemin)
        row = conn.execute("SELECT content, kind FROM memories").fetchone()
        self.assertEqual(row, ("ancien souvenir", "inconnu"))  # préservé + défaut
        conn.close()
        mem.close()


class TestKind(_Base):
    def test_kind_defaut_inconnu(self) -> None:
        mem = self._memoire()
        mem_id = mem.add_memory("simple")
        self.assertEqual(mem.list_memories()[0]["kind"], "inconnu")
        mem.close()

    def test_kind_invalide_refuse(self) -> None:
        mem = self._memoire()
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("x", kind="certifie")
        mem.close()

    def test_set_kind_fait_promotion_humaine(self) -> None:
        mem = self._memoire()
        mem_id = mem.add_memory("fait a confirmer")
        self.assertTrue(mem.set_kind(mem_id, "fait"))
        self.assertEqual(mem.list_memories()[0]["kind"], "fait")
        with self.assertRaises(PersistentMemoryError):
            mem.set_kind(mem_id, "toto")  # jamais de valeur libre
        mem.close()


class TestDetection(_Base):
    def test_contenu_identique_devient_duplique(self) -> None:
        mem = self._memoire()
        mem.add_memory("Le projet MILES tourne a Paris.")
        mem.add_memory("Le projet MILES tourne à Paris.")
        liens = mem.list_links()
        self.assertEqual(len(liens), 1)
        self.assertEqual(liens[0]["relation"], "duplique")
        self.assertEqual(liens[0]["confidence"], "signale")  # jamais confirmé auto
        mem.close()

    def test_negation_exacte_devient_contradit(self) -> None:
        mem = self._memoire()
        mem.add_memory("Le serveur est actif")
        mem.add_memory("Le serveur n'est pas actif")
        liens = mem.list_links(relation="contradit")
        self.assertEqual(len(liens), 1)
        self.assertEqual(liens[0]["confidence"], "signale")
        mem.close()

    def test_phrases_differentes_ne_creent_aucun_lien(self) -> None:
        # Règle étroite : pas de fausses contradictions.
        mem = self._memoire()
        mem.add_memory("Le serveur est actif")
        mem.add_memory("Le ciel est bleu aujourd'hui")
        self.assertEqual(mem.list_links(), [])
        mem.close()

    def test_confirmation_humaine(self) -> None:
        mem = self._memoire()
        mem.add_memory("Le serveur est actif")
        mem.add_memory("Le serveur n'est pas actif")
        lien = mem.list_links()[0]
        self.assertTrue(mem.confirm_link(lien["id"]))
        self.assertEqual(mem.list_links()[0]["confidence"], "confirme")
        mem.close()


class TestIsolationLiens(_Base):
    def test_aucun_lien_entre_souvenirs_de_deux_utilisateurs(self) -> None:
        mem = self._memoire()
        mem.add_memory("Le projet MILES tourne a Paris.", owner_user_id="alice")
        mem.add_memory("Le projet MILES tourne a Paris.", owner_user_id="bob")
        # Isolation : alice ne voit pas bob → AUCUN lien n'est même CRÉÉ.
        self.assertEqual(mem.list_links(owner_user_id="alice"), [])
        self.assertEqual(mem.list_links(owner_user_id="bob"), [])
        self.assertEqual(len(mem.list_links()), 0)
        mem.close()

    def test_lien_avec_souvenir_partage_visible(self) -> None:
        mem = self._memoire()
        mem.add_memory("Note commune.", owner_user_id="")   # partagé
        mem.add_memory("Note commune.", owner_user_id="alice")
        liens = mem.list_links(owner_user_id="alice")
        self.assertEqual(len(liens), 1)
        # bob ne voit pas le lien de alice (même si un extrémité est partagée)
        self.assertEqual(mem.list_links(owner_user_id="bob"), [])
        mem.close()

    def test_confirm_refuse_pour_non_proprietaire(self) -> None:
        mem = self._memoire()
        mem.add_memory("Le serveur est actif", owner_user_id="alice")
        mem.add_memory("Le serveur n'est pas actif", owner_user_id="alice")
        lien = mem.list_links(owner_user_id="alice")[0]
        self.assertFalse(mem.confirm_link(lien["id"], owner_user_id="bob"))
        self.assertTrue(mem.confirm_link(lien["id"], owner_user_id="alice"))
        mem.close()

    def test_set_kind_refuse_pour_non_proprietaire(self) -> None:
        mem = self._memoire()
        mem_id = mem.add_memory("note interne d alice", owner_user_id="alice")
        self.assertFalse(mem.set_kind(mem_id, "fait", owner_user_id="bob"))
        self.assertEqual(mem.list_memories(owner_user_id="alice")[0]["kind"], "inconnu")
        mem.close()


class TestResume(_Base):
    def test_ordre_et_marques(self) -> None:
        mem = self._memoire()
        mem.add_memory("inconnu d abord")
        fid = mem.add_memory("fait important", kind="fait")
        hy = mem.add_memory("hypothese here", kind="hypothese")
        resume = PersistentMemory.resume_memoire(mem.list_memories())
        self.assertLess(resume.index("[fait]"), resume.index("[hypothèse]"))
        self.assertLess(resume.index("[hypothèse]"), resume.index("inconnu d abord"))
        mem.close()

    def test_troncature(self) -> None:
        mem = self._memoire()
        for i in range(20):
            mem.add_memory(f"souvenir numero {i} " + "x" * 50)
        resume = PersistentMemory.resume_memoire(mem.list_memories(), max_car=120)
        self.assertLessEqual(len(resume), 120)
        mem.close()


class TestGardefous(_Base):
    def test_aucun_reseau_dans_le_module(self) -> None:
        import app.memory.persistent as mod
        with open(mod.__file__, encoding="utf-8") as fh:
            source = fh.read()
        for interdit in ("import socket", "import urllib", "import requests"):
            self.assertNotIn(interdit, source)


class TestCycleCLI(_Base):
    def test_hypothese_fait_contradictions_confirmer(self) -> None:
        import io
        from contextlib import redirect_stdout
        from app.config.settings import Settings
        from app.interface.cli import CLI

        mem = self._memoire()
        cli = CLI(settings=Settings(), provider=None, memory=mem)

        def run(cmd: str) -> str:
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli._handle_command(cmd)
            return buf.getvalue()

        # 1. enregistrer deux hypothèses contradictoires
        self.assertIn("Hypothèse enregistrée", run("/hypothese Le serveur est actif"))
        self.assertIn("Hypothèse enregistrée", run("/hypothese Le serveur n'est pas actif"))
        # 2. les voir signalées
        out = run("/contradictions")
        self.assertIn("contradit", out)
        self.assertIn("signale", out)
        # 3. confirmer le lien
        lien_id = int(out.split("#")[1].split()[0])
        self.assertIn("confirmé", run(f"/confirmer {lien_id}"))
        # 4. promotion en fait
        fid = mem.list_memories()[0]["id"]
        self.assertIn("marqué comme [fait]", run(f"/fait {fid}"))
        self.assertEqual(
            [m for m in mem.list_memories() if m["id"] == fid][0]["kind"], "fait")
        mem.close()


if __name__ == "__main__":
    unittest.main()
