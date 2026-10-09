"""API tests. They run the API against the smartmet4qc_test database and are
skipped if the libraries or PostgreSQL are not available."""

import unittest

from api_setup import client_for_tests

from smartmet_sim import Simulator
from smartmet_sim.cli import post_reading

URL = "/api/v1/measurements"


class ApiTests(unittest.TestCase):
    def setUp(self):
        global client
        client = client_for_tests()
        self.reading = next(Simulator(batch_id="BATCH-API", seed=1).readings())

    def test_health(self):
        self.assertEqual(client.get("/health").json(), {"status": "ok", "database": "ok"})

    def test_post_then_read_back(self):
        response = client.post(URL, json=self.reading)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(),
                         {"stored": True, "duplicate": False, "batch_id": "BATCH-API", "new_alerts": []})

        [batch] = client.get("/api/v1/batches").json()
        self.assertEqual((batch["code"], batch["readings"]), ("BATCH-API", 1))
        [stored] = client.get("/api/v1/batches/BATCH-API/readings").json()
        self.assertEqual(stored["ph"], self.reading["measurements"]["ph"])
        self.assertEqual(stored["source"], "simulated")

    def test_resending_is_safe(self):
        client.post(URL, json=self.reading)
        response = client.post(URL, json=self.reading)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["duplicate"])

    def test_reading_without_simulation_and_with_dropout(self):
        reading = {
            "timestamp": "2026-10-09T10:00:00+02:00",
            "batch_id": "BATCH-API",
            "source": "simulated",
            "measurements": {"temperature_c": 25.9, "ph": None},
        }
        self.assertEqual(client.post(URL, json=reading).status_code, 201)
        [stored] = client.get("/api/v1/batches/BATCH-API/readings").json()
        self.assertIsNone(stored["ph"])
        self.assertIsNone(stored["simulation"])

    def test_invalid_readings_get_422(self):
        m = self.reading["measurements"]
        cases = {
            "no timezone": {**self.reading, "timestamp": "2026-10-09T10:00:00"},
            "bad source": {**self.reading, "source": "phone"},
            "unknown sensor": {**self.reading, "measurements": {**m, "sugar": 1}},
            "text value": {**self.reading, "measurements": {**m, "ph": "4.5"}},
            "impossible pH": {**self.reading, "measurements": {**m, "ph": 20}},
            "no measurements": {**self.reading, "measurements": {}},
            "missing batch": {k: v for k, v in self.reading.items() if k != "batch_id"},
        }
        for name, body in cases.items():
            with self.subTest(name):
                self.assertEqual(client.post(URL, json=body).status_code, 422)

    def test_readings_limit_returns_newest(self):
        readings = list(Simulator(batch_id="BATCH-API", seed=2).readings(5))
        for r in readings:
            client.post(URL, json=r)
        newest = client.get("/api/v1/batches/BATCH-API/readings?limit=2").json()
        self.assertEqual(len(newest), 2)
        self.assertEqual(newest[-1]["brix"], readings[-1]["measurements"]["brix"])

    def test_overheat_batch_opens_one_alert(self):
        opened = []
        for r in Simulator(batch_id="BATCH-HOT", scenario="overheat", seed=1).readings():
            opened += client.post(URL, json=r).json()["new_alerts"]
        self.assertIn("temperature_high", [a["rule"] for a in opened])

        open_alerts = client.get("/api/v1/alerts", params={"batch": "BATCH-HOT"}).json()
        self.assertEqual([a["rule"] for a in open_alerts].count("temperature_high"), 1)
        self.assertEqual(open_alerts[0]["batch_id"], "BATCH-HOT")
        self.assertEqual(client.get("/api/v1/alerts", params={"batch": "NOPE"}).json(), [])

    def test_alert_resolves_when_problem_ends(self):
        base = {"batch_id": "BATCH-R", "source": "simulated"}
        for hour, ph in enumerate([4.5, 3.2, 3.1, 4.4]):
            client.post(URL, json={**base, "timestamp": f"2026-10-09T{hour:02d}:00:00+00:00",
                                   "measurements": {"ph": ph}})
        alerts = client.get("/api/v1/alerts", params={"status": "all", "batch": "BATCH-R"}).json()
        [alert] = [a for a in alerts if a["rule"] == "ph_low"]
        self.assertEqual((alert["status"], alert["severity"]), ("resolved", "critical"))
        open_rules = [a["rule"] for a in client.get("/api/v1/alerts", params={"batch": "BATCH-R"}).json()]
        self.assertNotIn("ph_low", open_rules)

    def test_unknown_batch_is_404(self):
        self.assertEqual(client.get("/api/v1/batches/NOPE/readings").status_code, 404)


class SimulatorSendTests(unittest.TestCase):
    def test_unreachable_backend_reports_error(self):
        body, error = post_reading("http://127.0.0.1:9/api/v1/measurements", {"x": 1})
        self.assertIsNone(body)
        self.assertIn("cannot reach", error)


if __name__ == "__main__":
    unittest.main()
