"""Phase 5 tests: batch endpoints, manual entry with typo check, dashboard pages.
Uses the smartmet4qc_test database; skipped if it is not available."""

import unittest

try:
    from api_setup import client_for_tests
except unittest.SkipTest:
    raise
except ImportError as exc:
    raise unittest.SkipTest(f"API libraries not installed: {exc}")

from smartmet_sim import Simulator

MANUAL = "/api/v1/manual-readings"


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.client = client_for_tests()

    def create(self, code="BATCH-D1", **extra):
        return self.client.post("/api/v1/batches", json={"code": code, **extra})

    def test_create_batch_and_read_details(self):
        response = self.create(notes="40 L")
        self.assertEqual(response.status_code, 201)
        detail = response.json()
        self.assertEqual((detail["code"], detail["status"], detail["notes"]), ("BATCH-D1", "active", "40 L"))
        self.assertEqual(detail["latest"], {})
        self.assertEqual(detail["limits"]["ph_min"], 3.5)
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.create(code="bad code!").status_code, 422)

    def test_latest_values_and_ethanol_estimate(self):
        for r in Simulator(batch_id="BATCH-D2", seed=1).readings(60):
            self.client.post("/api/v1/measurements", json=r)
        detail = self.client.get("/api/v1/batches/BATCH-D2").json()
        self.assertEqual(set(detail["latest"]), {"temperature_c", "ph", "brix", "turbidity_ntu", "ethanol_percent"})
        self.assertGreater(detail["ethanol_estimate"], 5)

    def test_status_change(self):
        self.create()
        finished = self.client.patch("/api/v1/batches/BATCH-D1", json={"status": "finished"}).json()
        self.assertEqual(finished["status"], "finished")
        self.assertIsNotNone(finished["ended_at"])
        reopened = self.client.patch("/api/v1/batches/BATCH-D1", json={"status": "active"}).json()
        self.assertIsNone(reopened["ended_at"])
        self.assertEqual(self.client.patch("/api/v1/batches/NOPE", json={"status": "finished"}).status_code, 404)

    def test_manual_typo_needs_confirmation(self):
        self.create()
        first = {"batch_id": "BATCH-D1", "timestamp": "2026-10-09T08:00:00+00:00", "measurements": {"brix": 13.0}}
        self.assertEqual(self.client.post(MANUAL, json=first).status_code, 201)

        typo = {**first, "timestamp": "2026-10-09T16:00:00+00:00", "measurements": {"brix": 31.0}}
        response = self.client.post(MANUAL, json=typo)
        self.assertEqual(response.status_code, 409)
        self.assertIn("typo", response.json()["warnings"][0])
        self.assertEqual(len(self.client.get("/api/v1/batches/BATCH-D1/readings").json()), 1)  # not stored

        response = self.client.post(MANUAL, json={**typo, "confirm": True})
        self.assertEqual(response.status_code, 201)
        [_, stored] = self.client.get("/api/v1/batches/BATCH-D1/readings").json()
        self.assertEqual((stored["source"], stored["brix"]), ("manual", 31.0))

    def test_plausible_manual_value_is_stored_directly(self):
        self.create()
        for hour, brix in [(8, 13.0), (16, 10.5)]:
            body = {"batch_id": "BATCH-D1", "timestamp": f"2026-10-09T{hour:02d}:00:00+00:00",
                    "measurements": {"brix": brix}}
            self.assertEqual(self.client.post(MANUAL, json=body).status_code, 201)

    def test_manual_entry_rules(self):
        self.assertEqual(self.client.post(MANUAL, json={"batch_id": "NOPE", "measurements": {"brix": 12}}).status_code, 404)
        self.create()
        self.assertEqual(self.client.post(MANUAL, json={"batch_id": "BATCH-D1", "measurements": {"brix": None}}).status_code, 422)
        no_time = self.client.post(MANUAL, json={"batch_id": "BATCH-D1", "measurements": {"ph": 4.4}})
        self.assertEqual(no_time.status_code, 201)  # time defaults to now

    def test_pages_are_served(self):
        for path in ("/", "/batches/BATCH-D1", "/static/common.js", "/static/vendor/chart.umd.js"):
            with self.subTest(path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
