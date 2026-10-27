"""Tests de la télémétrie réelle du poste (`GET /api/device`).

Deux niveaux, comme pour le cockpit :

- le module ``device_telemetry`` mesure réellement la machine (aucune valeur
  inventée, capteurs absents déclarés indisponibles) ;
- la route HTTP exige une session et ne divulgue aucun secret.
"""

from __future__ import annotations

import os
import platform
import unittest
from pathlib import Path

from app.interface import device_telemetry
from tests.web_test_support import WebTestServer, build_app


class TestDeviceTelemetry(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = device_telemetry.build_telemetry(
            provider={
                "name": "fournisseur de test",
                "mode": "remote",
                "model": "modele-de-test",
                "availability": "non testée",
            },
            memory_available=True,
        )

    def test_host_values_are_measured(self) -> None:
        host = self.payload["host"]
        self.assertTrue(host["available"])
        self.assertEqual(host["name"], platform.node())
        self.assertEqual(host["system"], platform.system())
        self.assertEqual(host["cpu_count"], os.cpu_count())
        self.assertEqual(self.payload["process"]["pid"], os.getpid())

    def test_disk_usage_is_coherent(self) -> None:
        disk = self.payload["disk"]
        self.assertTrue(disk["available"])
        self.assertGreater(disk["total_bytes"], 0)
        self.assertGreaterEqual(disk["used_percent"], 0.0)
        self.assertLessEqual(disk["used_percent"], 100.0)
        self.assertEqual(
            disk["total_bytes"], disk["used_bytes"] + disk["free_bytes"]
        )

    def test_uptime_is_not_negative(self) -> None:
        self.assertGreaterEqual(self.payload["process"]["uptime_seconds"], 0)

    def test_sensors_are_declared_unavailable_with_a_reason(self) -> None:
        sensors = self.payload["sensors"]
        self.assertEqual(
            [s["id"] for s in sensors],
            [sensor_id for sensor_id, _, _ in device_telemetry.SENSOR_IDS],
        )
        for sensor in sensors:
            self.assertFalse(sensor["available"], sensor["id"])
            self.assertIsNone(sensor["value"], sensor["id"])
            self.assertTrue(sensor["reason"], sensor["id"])
        self.assertEqual(
            self.payload["unavailable"], [s["id"] for s in sensors]
        )

    def test_no_secret_is_exposed(self) -> None:
        import json

        flat = json.dumps(self.payload, ensure_ascii=False).lower()
        for forbidden in ("api_key", "authorization", "bearer", "password", "token"):
            self.assertNotIn(forbidden, flat)

    def test_provider_is_summarised_without_base_url(self) -> None:
        provider = self.payload["provider"]
        self.assertEqual(provider["name"], "fournisseur de test")
        self.assertEqual(provider["model"], "modele-de-test")
        self.assertNotIn("base_url", provider)

    def test_missing_provider_is_explicit(self) -> None:
        payload = device_telemetry.build_telemetry(provider=None, memory_available=False)
        self.assertFalse(payload["provider"]["available"])
        self.assertEqual(payload["provider"]["name"], "non configuré")
        self.assertFalse(payload["memory"]["available"])

    def test_root_parameter_changes_disk_path(self) -> None:
        here = Path.cwd()
        payload = device_telemetry.build_telemetry(root=here)
        self.assertEqual(payload["disk"]["path"], str(here.resolve()))


class TestDeviceRoute(unittest.TestCase):
    def build(self):
        return build_app()

    def test_device_route_requires_session(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/device", authenticate=False)
        self.assertEqual(result["status"], 401)

    def test_device_route_returns_measured_payload(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/device")
        self.assertEqual(result["status"], 200)
        payload = result["json"]
        for section in ("host", "process", "disk", "provider", "memory", "sensors"):
            self.assertIn(section, payload)
        self.assertEqual(payload["process"]["pid"], os.getpid())
        self.assertTrue(all(not s["available"] for s in payload["sensors"]))

    def test_unknown_route_still_returns_404_with_session(self) -> None:
        with WebTestServer(self.build()) as server:
            result = server.raw_request("GET", "/api/inconnu")
        self.assertEqual(result["status"], 404)


if __name__ == "__main__":
    unittest.main()
