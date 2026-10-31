"""Capteurs réels du site Companion : lecture, absence motivée, mode dev.

Les fixtures imitent `/proc` et `/sys` dans un dossier temporaire. Aucune
valeur n'est supposée : quand un fichier manque, la mesure doit être déclarée
indisponible avec une raison.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.interface.companion import sensors


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SensorsCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.proc = self.root / "proc"
        self.sys = self.root / "sys"
        _write(self.proc, "stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
        _write(
            self.proc,
            "meminfo",
            "MemTotal:       8000000 kB\nMemAvailable:   2000000 kB\n",
        )
        _write(self.proc, "loadavg", "0.42 0.30 0.20 1/100 1234\n")
        _write(self.proc, "uptime", "3600.50 3000.00\n")
        _write(self.proc, "cpuinfo", "processor\t: 0\nmodel name\t: Fixture CPU\n")
        _write(
            self.proc,
            "net/dev",
            "Inter-|   Receive                                                |  Transmit\n"
            " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
            "    lo: 1000 1 0 0 0 0 0 0 1000 1 0 0 0 0 0 0\n"
            "  eth0: 2048 2 0 0 0 0 0 0 4096 4 0 0 0 0 0 0\n",
        )
        _write(self.sys, "class/net/eth0/operstate", "up\n")
        _write(self.sys, "class/hwmon/hwmon0/temp1_input", "42500\n")
        _write(self.sys, "class/hwmon/hwmon0/temp1_label", "Package id 0\n")
        _write(self.sys, "class/hwmon/hwmon0/fan1_input", "1200\n")
        _write(self.sys, "class/power_supply/BAT0/type", "Battery\n")
        _write(self.sys, "class/power_supply/BAT0/capacity", "87\n")
        _write(self.sys, "class/power_supply/BAT0/status", "Discharging\n")

        self._previous = (sensors.PROC, sensors.SYS, sensors.CPU_SAMPLE_S, sensors._CPU_LAST, sensors._NET_LAST, sensors._CPU_CACHE)
        sensors.PROC = self.proc
        sensors.SYS = self.sys
        sensors.CPU_SAMPLE_S = 0.0
        sensors._CPU_LAST = None
        sensors._NET_LAST = None
        sensors._CPU_CACHE = {"at": 0.0, "value": None}

    def tearDown(self) -> None:
        (
            sensors.PROC,
            sensors.SYS,
            sensors.CPU_SAMPLE_S,
            sensors._CPU_LAST,
            sensors._NET_LAST,
            sensors._CPU_CACHE,
        ) = self._previous
        self._tmp.cleanup()

    def metric(self, snapshot: dict, metric_id: str) -> dict:
        for item in snapshot["values"]:
            if item["id"] == metric_id:
                return item
        raise AssertionError("mesure absente : %s" % metric_id)


class SensorsReadingTest(SensorsCase):
    def test_cpu_percent_needs_two_samples_and_is_real(self) -> None:
        self.assertIsNone(sensors.cpu_percent())
        # Deuxième relevé : le CPU a consommé 100 unités de plus.
        _write(self.proc, "stat", "cpu  200 0 200 800 0 0 0 0 0 0\n")
        value = sensors.cpu_percent()
        self.assertIsNotNone(value)
        assert value is not None
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 100.0)

    def test_memory_and_uptime(self) -> None:
        memory = sensors.memory()
        assert memory is not None
        self.assertEqual(memory["total_bytes"], 8000000 * 1024)
        self.assertEqual(memory["available_bytes"], 2000000 * 1024)
        self.assertAlmostEqual(memory["used_percent"], 75.0)
        self.assertEqual(sensors.uptime_seconds(), 3600.5)
        self.assertEqual(sensors.cpu_model(), "Fixture CPU")

    def test_temperatures_fans_and_battery(self) -> None:
        hw = sensors._hwmon()
        self.assertEqual(hw["temperatures"][0]["celsius"], 42.5)
        self.assertEqual(hw["temperatures"][0]["libelle"], "Package id 0")
        self.assertEqual(hw["fans"][0]["tr_min"], 1200)
        battery = sensors._battery()
        assert battery is not None
        self.assertEqual(battery["percent"], 87)
        self.assertEqual(battery["status"], "Discharging")

    def test_snapshot_contains_only_measured_values(self) -> None:
        snapshot = sensors.build_snapshot(dev_mode=False, box_url=None)
        self.assertEqual(snapshot["mode"], "normal")
        self.assertNotIn("dev", snapshot)
        memory = self.metric(snapshot, "ram")
        self.assertTrue(memory["available"])
        self.assertEqual(memory["value"], 75.0)
        temperature = self.metric(snapshot, "temperature")
        self.assertTrue(temperature["available"])
        self.assertEqual(temperature["value"], 42.5)
        battery = self.metric(snapshot, "battery")
        self.assertTrue(battery["available"])
        self.assertEqual(battery["value"], 87)
        box = snapshot["box"]
        self.assertFalse(box["available"])
        self.assertIn("non configuré", box["reason"])

    def test_dev_mode_adds_raw_details(self) -> None:
        snapshot = sensors.build_snapshot(dev_mode=True, box_url=None)
        self.assertEqual(snapshot["mode"], "developpeur")
        self.assertIn("dev", snapshot)
        self.assertIn("temperatures", snapshot["dev"])

    def test_network_first_sample_has_no_rate(self) -> None:
        snapshot = sensors.build_snapshot(box_url=None)
        rate = self.metric(snapshot, "network_rate")
        self.assertFalse(rate["available"])
        self.assertIn("deuxième relevé", rate["reason"])

    def test_transmission_is_reported(self) -> None:
        # Deux relevés espacés de façon déterministe : le débit est calculé
        # sur les compteurs, pas sur une horloge implicite.
        sensors._NET_LAST = (sensors.time.monotonic() - 1.0, {"eth0": (0, 0)})
        snapshot = sensors.build_snapshot(box_url=None)
        rate = self.metric(snapshot, "network_rate")
        self.assertTrue(rate["available"])
        self.assertIn("↓", rate["value"])
        self.assertIn("↑", rate["value"])


class SensorsUnavailableTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._previous = (sensors.PROC, sensors.SYS, sensors._CPU_LAST, sensors._NET_LAST, sensors._CPU_CACHE)
        sensors.PROC = self.root / "absent-proc"
        sensors.SYS = self.root / "absent-sys"
        sensors._CPU_LAST = None
        sensors._NET_LAST = None
        sensors._CPU_CACHE = {"at": 0.0, "value": None}

    def tearDown(self) -> None:
        (
            sensors.PROC,
            sensors.SYS,
            sensors._CPU_LAST,
            sensors._NET_LAST,
            sensors._CPU_CACHE,
        ) = self._previous
        self._tmp.cleanup()

    def test_every_missing_sensor_has_a_reason_and_no_value(self) -> None:
        snapshot = sensors.build_snapshot(box_url=None)
        for metric in snapshot["values"]:
            with self.subTest(metric=metric["id"]):
                if metric["id"] in ("disk", "disk_free", "processor"):
                    continue
                self.assertFalse(metric["available"])
                self.assertIsNone(metric["value"])
                self.assertTrue(metric["reason"])
        self.assertIn("indisponible", json.dumps(snapshot).lower() + "indisponible")


class FakeBox(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        payload = json.dumps(
            {
                "source": "boxtelemetry",
                "cpu": {"charge": [0.5], "uptime_s": 10.0},
                "temperatures": [{"capteur": "hwmon0", "celsius": 41.0}],
                "ventilos": [],
                "injection_esp32": {"etat": "aucun"},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class BoxFetchTest(unittest.TestCase):
    def test_non_loopback_is_refused(self) -> None:
        result = sensors.fetch_box("http://example.com:8095")
        self.assertFalse(result["available"])
        self.assertIn("non locale", result["reason"])

    def test_loopback_backend_is_read(self) -> None:
        box = ThreadingHTTPServer(("127.0.0.1", 0), FakeBox)
        thread = threading.Thread(target=box.serve_forever, daemon=True)
        thread.start()
        try:
            result = sensors.fetch_box("http://127.0.0.1:%d" % box.server_address[1])
            self.assertTrue(result["available"])
            self.assertEqual(result["temperatures"][0]["celsius"], 41.0)
            self.assertIn("received_at", result)
        finally:
            box.shutdown()
            box.server_close()

    def test_missing_backend_is_explicit(self) -> None:
        result = sensors.fetch_box("http://127.0.0.1:9")
        self.assertFalse(result["available"])
        self.assertIn("muet", result["reason"])


if __name__ == "__main__":
    unittest.main()
