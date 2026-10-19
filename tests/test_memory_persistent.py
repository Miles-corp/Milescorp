"""Tests de la mémoire persistante locale (SQLite).

Ces tests utilisent des fichiers temporaires isolés. Aucun fichier de
mémoire réel de l'utilisateur n'est lu, modifié ou effacé.
Aucun fournisseur IA réel ni clé API n'est utilisé.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from app.memory.persistent import PersistentMemory, PersistentMemoryError


class TestPersistentMemory(unittest.TestCase):
    """Tests de la classe PersistentMemory."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="miles_test_memory_")
        self.db_path = os.path.join(self.tmpdir, "memory.db")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_memory(self, **kwargs: Any) -> PersistentMemory:
        return PersistentMemory(
            enabled=True,
            db_path=self.db_path,
            **kwargs,
        )

    # --- Initialisation ---

    def test_initialization_creates_database(self) -> None:
        mem = self._make_memory()
        self.assertTrue(mem.is_available)
        self.assertTrue(os.path.isfile(self.db_path))
        mem.close()

    def test_initialization_creates_tables(self) -> None:
        mem = self._make_memory()
        self.assertTrue(mem.is_available)
        mem.close()

        # Réouvrir et vérifier que les tables existent
        mem2 = PersistentMemory(enabled=True, db_path=self.db_path)
        self.assertTrue(mem2.is_available)
        mem2.close()

    def test_disabled_memory_not_available(self) -> None:
        mem = PersistentMemory(enabled=False, db_path=self.db_path)
        self.assertFalse(mem.is_available)

    # --- Ajout et lecture de souvenirs ---

    def test_add_and_list_memory(self) -> None:
        mem = self._make_memory()
        mem_id = mem.add_memory("Je préfère le thé au café.", category="gout")
        self.assertIsInstance(mem_id, int)
        self.assertGreater(mem_id, 0)

        memories = mem.list_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["id"], mem_id)
        self.assertEqual(memories[0]["content"], "Je préfère le thé au café.")
        self.assertEqual(memories[0]["category"], "gout")
        mem.close()

    def test_add_empty_content_raises(self) -> None:
        mem = self._make_memory()
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("")
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("   ")
        mem.close()

    def test_add_secret_refused(self) -> None:
        mem = self._make_memory()
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("Ma clé API est sk-1234567890abcdef")
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("Mon mot de passe est supersecret")
        mem.close()

    def test_get_memory(self) -> None:
        mem = self._make_memory()
        mem_id = mem.add_memory("Souvenir test", category="test")
        rec = mem.get_memory(mem_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["content"], "Souvenir test")
        self.assertIsNone(mem.get_memory(99999))
        mem.close()

    def test_delete_memory(self) -> None:
        mem = self._make_memory()
        mem_id = mem.add_memory("À supprimer", category="tmp")
        self.assertTrue(mem.delete_memory(mem_id))
        self.assertFalse(mem.delete_memory(mem_id))  # déjà supprimé
        self.assertEqual(len(mem.list_memories()), 0)
        mem.close()

    def test_clear_all_memories(self) -> None:
        mem = self._make_memory()
        mem.add_memory("A", category="a")
        mem.add_memory("B", category="b")
        count = mem.clear_all_memories()
        self.assertEqual(count, 2)
        self.assertEqual(len(mem.list_memories()), 0)
        mem.close()

    def test_list_memories_by_category(self) -> None:
        mem = self._make_memory()
        mem.add_memory("Travail 1", category="travail")
        mem.add_memory("Travail 2", category="travail")
        mem.add_memory("Perso", category="perso")

        trav = mem.list_memories(category="travail")
        self.assertEqual(len(trav), 2)
        perso = mem.list_memories(category="perso")
        self.assertEqual(len(perso), 1)
        mem.close()

    def test_max_content_length(self) -> None:
        mem = self._make_memory(max_content_length=10)
        long_text = "x" * 50
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory(long_text)
        mem.close()

    # --- Préférences ---

    def test_set_and_get_preference(self) -> None:
        mem = self._make_memory()
        mem.set_preference("langue", "français")
        self.assertEqual(mem.get_preference("langue"), "français")
        self.assertIsNone(mem.get_preference("inexistante"))
        mem.close()

    def test_set_preference_secret_refused(self) -> None:
        mem = self._make_memory()
        with self.assertRaises(PersistentMemoryError):
            mem.set_preference("cle", "sk-abc123")
        mem.close()

    def test_delete_preference(self) -> None:
        mem = self._make_memory()
        mem.set_preference("theme", "sombre")
        self.assertTrue(mem.delete_preference("theme"))
        self.assertFalse(mem.delete_preference("theme"))
        mem.close()

    # --- Contexte IA ---

    def test_get_context_memories_respects_limit(self) -> None:
        mem = self._make_memory(max_memories_in_context=2)
        mem.add_memory("Souvenir 1", importance=1)
        mem.add_memory("Souvenir 2", importance=2)
        mem.add_memory("Souvenir 3", importance=3)
        ctx = mem.get_context_memories()
        self.assertEqual(len(ctx), 2)
        # Le plus important d'abord
        self.assertEqual(ctx[0]["content"], "Souvenir 3")
        mem.close()

    def test_context_memories_empty_when_disabled(self) -> None:
        mem = PersistentMemory(enabled=False, db_path=self.db_path)
        self.assertEqual(mem.get_context_memories(), [])
        mem.close()

    # --- Base absente / corrompue ---

    def test_corrupt_database_raises(self) -> None:
        # Créer un fichier non-SQLite à l'emplacement
        with open(self.db_path, "w") as f:
            f.write("ceci n'est pas une base sqlite")
        mem = PersistentMemory(enabled=True, db_path=self.db_path)
        self.assertFalse(mem.is_available)
        # Ne doit pas lever d'exception à l'initialisation (dégradation gracieuse)
        mem.close()

    def test_add_memory_when_unavailable_raises(self) -> None:
        mem = PersistentMemory(enabled=False, db_path=self.db_path)
        with self.assertRaises(PersistentMemoryError):
            mem.add_memory("test")
        mem.close()


if __name__ == "__main__":
    unittest.main()
