"""Tests de non-régression S-006 : fermeture des files multiprocessing.

Les files de résultat et d'erreur doivent être fermées après chaque
exécution d'outil, y compris sur les chemins d'erreur et de dépassement de
délai. Aucun processus enfant orphelin ne doit subsister.

Le test de fuite de descripteurs s'appuie sur ``/proc/self/fd`` : il est
ignoré sous Windows, où ce pseudo-système de fichiers n'existe pas. Il
s'exécute sous Debian 13.
"""

from __future__ import annotations

import multiprocessing
import os
import time
import unittest
from multiprocessing.queues import Queue as QueueClass
from unittest import mock

from app.tools.audit import AuditLogger
from app.tools.engine import ToolEngine
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolDefinition, ToolRegistry


def _fast_handler() -> str:
    return "ok"


def _failing_handler() -> str:
    raise RuntimeError("echec simule")


def _slow_handler() -> str:
    time.sleep(30)
    return "trop lent"


def _open_fd_count() -> int:
    """Nombre de descripteurs de fichiers ouverts (Linux uniquement)."""
    return len(os.listdir("/proc/self/fd"))


def _engine_with(tool: ToolDefinition) -> ToolEngine:
    registry = ToolRegistry()
    registry.register(tool)
    return ToolEngine(
        registry=registry,
        policy=ToolPolicy(granted_permissions=set()),
        audit=AuditLogger(),
    )


class _QueueTracker:
    """Enregistre les files créées et leur fermeture."""

    def __init__(self) -> None:
        self.created: list[object] = []
        self.closed: list[object] = []
        self._real_factory = multiprocessing.Queue
        self._real_close = QueueClass.close

    def _factory(self, *args: object, **kwargs: object):
        queue = self._real_factory(*args, **kwargs)
        self.created.append(queue)
        return queue

    def __enter__(self) -> "_QueueTracker":
        tracker = self
        real_close = self._real_close

        # Fonction simple (non méthode liée) : elle est affecté à la
        # classe, elle reçoit donc l'instance de file comme argument.
        def tracking_close(queue_obj: object) -> None:
            tracker.closed.append(queue_obj)
            real_close(queue_obj)  # type: ignore[arg-type]

        self._patcher_factory = mock.patch(
            "app.tools.engine.multiprocessing.Queue", self._factory
        )
        self._patcher_close = mock.patch.object(
            QueueClass, "close", tracking_close
        )
        self._patcher_factory.start()
        self._patcher_close.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._patcher_factory.stop()
        self._patcher_close.stop()


class TestQueuesClosed(unittest.TestCase):
    """Les deux files sont fermées après chaque exécution."""

    def test_files_fermees_apres_succes(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="rapide",
                description="Rapide",
                handler=_fast_handler,
                timeout_seconds=10,
            )
        )
        with _QueueTracker() as tracker:
            result = engine.request_tool("rapide", {})

        self.assertTrue(result.success)
        self.assertEqual(len(tracker.created), 2)
        self.assertEqual(len(tracker.closed), 2)
        for queue in tracker.created:
            self.assertIn(queue, tracker.closed)

    def test_files_fermees_apres_exception(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="en_erreur",
                description="Erreur",
                handler=_failing_handler,
                timeout_seconds=10,
            )
        )
        with _QueueTracker() as tracker:
            result = engine.request_tool("en_erreur", {})

        self.assertFalse(result.success)
        self.assertEqual(len(tracker.created), 2)
        self.assertEqual(len(tracker.closed), 2)

    def test_files_fermees_apres_timeout(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="lente",
                description="Lente",
                handler=_slow_handler,
                timeout_seconds=1,
            )
        )
        with _QueueTracker() as tracker:
            result = engine.request_tool("lente", {})

        self.assertFalse(result.success)
        self.assertEqual(len(tracker.created), 2)
        self.assertEqual(len(tracker.closed), 2)

    def test_appels_repetes_ferment_toutes_les_files(self) -> None:
        """Chaque appel crée et ferme ses deux files."""
        engine = _engine_with(
            ToolDefinition(
                tool_id="rapide",
                description="Rapide",
                handler=_fast_handler,
                timeout_seconds=10,
            )
        )
        with _QueueTracker() as tracker:
            for _ in range(3):
                self.assertTrue(engine.request_tool("rapide", {}).success)

        self.assertEqual(len(tracker.created), 6)
        self.assertEqual(len(tracker.closed), 6)
        self.assertEqual(len(set(map(id, tracker.created))), 6)


class TestNoOrphanProcess(unittest.TestCase):
    """Aucun processus enfant ne doit subsister après l'exécution."""

    def test_aucun_enfant_apres_appel_reussi(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="rapide",
                description="Rapide",
                handler=_fast_handler,
                timeout_seconds=10,
            )
        )
        engine.request_tool("rapide", {})
        self.assertEqual(multiprocessing.active_children(), [])

    def test_aucun_enfant_apres_timeout(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="lente",
                description="Lente",
                handler=_slow_handler,
                timeout_seconds=1,
            )
        )
        result = engine.request_tool("lente", {})
        self.assertFalse(result.success)
        self.assertEqual(multiprocessing.active_children(), [])

    def test_moteur_utilisable_apres_un_timeout(self) -> None:
        """L-007 préservé : après un timeout, le moteur reste opérationnel."""
        engine = _engine_with(
            ToolDefinition(
                tool_id="lente",
                description="Lente",
                handler=_slow_handler,
                timeout_seconds=1,
            )
        )
        self.assertFalse(engine.request_tool("lente", {}).success)

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                tool_id="rapide",
                description="Rapide",
                handler=_fast_handler,
                timeout_seconds=10,
            )
        )
        engine2 = ToolEngine(
            registry=registry,
            policy=ToolPolicy(granted_permissions=set()),
            audit=AuditLogger(),
        )
        self.assertTrue(engine2.request_tool("rapide", {}).success)


class TestNoFileDescriptorLeak(unittest.TestCase):
    """Le nombre de descripteurs ouverts ne doit pas croître (Linux)."""

    def setUp(self) -> None:
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest(
                "Comptage de descripteurs indisponible sous Windows "
                "(/proc/self/fd absent). Test exécuté sous Debian 13."
            )

    def test_pas_de_fuite_de_descripteurs(self) -> None:
        engine = _engine_with(
            ToolDefinition(
                tool_id="rapide",
                description="Rapide",
                handler=_fast_handler,
                timeout_seconds=10,
            )
        )
        # Une exécution de référence pour amortir les allocations internes.
        engine.request_tool("rapide", {})
        before = _open_fd_count()
        for _ in range(5):
            self.assertTrue(engine.request_tool("rapide", {}).success)
        after = _open_fd_count()
        self.assertLessEqual(
            after,
            before,
            f"Fuite de descripteurs : {before} -> {after}",
        )


if __name__ == "__main__":
    unittest.main()
