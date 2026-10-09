"""Phase 6 tests: device API keys, batch assignment, device emulator."""

import os
import unittest
from datetime import datetime, timedelta, timezone

from api_setup import client_for_tests

from smartmet_db import db
from smartmet_db.devices import add_device, revoke_key
from smartmet_sim import Simulator
from smartmet_sim.cli import as_device_reading

URL = "/api/v1/measurements"
T = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)


def device_reading(minutes=0, **values):
    return {"timestamp": (T + timedelta(minutes=minutes)).isoformat(), "source": "device",
            "measurements": values or {"temperature_c": 26.0, "ph": 4.5}}


def setUpModule():
    global engine
    engine = db.get_engine(test=True)


def tearDownModule():
    engine.dispose()


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.client = client_for_tests()
        self.Session = db.get_sessionmaker(engine)
        with self.Session.begin() as session:
            self.key = add_device(session, "tank-1")
            self.key2 = add_device(session, "tank-2")
        self.client.post("/api/v1/batches", json={"code": "BATCH-E1"})

    def post(self, body, key=None):
        return self.client.post(URL, json=body, headers={"X-API-Key": key} if key else {})

    def assign(self, name, batch):
        return self.client.patch(f"/api/v1/devices/{name}", json={"batch_id": batch})

    def test_device_readings_need_a_valid_key(self):
        self.assertEqual(self.post(device_reading()).status_code, 401)
        self.assertEqual(self.post(device_reading(), key="smk_wrong").status_code, 401)

    def test_unassigned_device_is_refused_but_seen(self):
        response = self.post(device_reading(), key=self.key)
        self.assertEqual(response.status_code, 409)
        self.assertIn("no batch assigned", response.json()["detail"])
        [dev] = [d for d in self.client.get("/api/v1/devices").json() if d["name"] == "tank-1"]
        self.assertTrue(dev["online"])
        self.assertIsNone(dev["batch_id"])

    def test_assigned_device_readings_go_to_its_batch(self):
        self.assertEqual(self.assign("tank-1", "BATCH-E1").json()["batch_id"], "BATCH-E1")
        response = self.post(device_reading(), key=self.key)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["batch_id"], "BATCH-E1")
        [stored] = self.client.get("/api/v1/batches/BATCH-E1/readings").json()
        self.assertEqual(stored["source"], "device")
        self.assertEqual(self.post(device_reading(), key=self.key).status_code, 200)  # resend = duplicate

    def test_two_devices_on_one_batch_at_the_same_moment(self):
        self.assign("tank-1", "BATCH-E1")
        self.assign("tank-2", "BATCH-E1")
        self.assertEqual(self.post(device_reading(ph=4.5), key=self.key).status_code, 201)
        self.assertEqual(self.post(device_reading(ph=4.6), key=self.key2).status_code, 201)
        self.assertEqual(len(self.client.get("/api/v1/batches/BATCH-E1/readings").json()), 2)

    def test_unassign_and_unknown(self):
        self.assign("tank-1", "BATCH-E1")
        self.assertIsNone(self.assign("tank-1", None).json()["batch_id"])
        self.assertEqual(self.assign("tank-9", "BATCH-E1").status_code, 404)
        self.assertEqual(self.assign("tank-1", "NOPE").status_code, 404)

    def test_revoked_key_stops_working(self):
        self.assign("tank-1", "BATCH-E1")
        with self.Session.begin() as session:
            revoke_key(session, "tank-1")
        self.assertEqual(self.post(device_reading(), key=self.key).status_code, 401)
        [dev] = [d for d in self.client.get("/api/v1/devices").json() if d["name"] == "tank-1"]
        self.assertFalse(dev["active"])

    def test_simulated_readings_can_be_switched_off(self):
        reading = next(Simulator(batch_id="BATCH-E1", seed=1).readings())
        os.environ["ALLOW_SIMULATED"] = "false"
        try:
            self.assertEqual(self.post(reading).status_code, 403)
        finally:
            del os.environ["ALLOW_SIMULATED"]
        self.assertEqual(self.post(reading).status_code, 201)

    def test_only_devices_may_leave_out_the_batch(self):
        reading = next(Simulator(seed=1).readings())
        del reading["batch_id"]
        self.assertEqual(self.post(reading).status_code, 422)

    def test_emulator_sends_what_the_esp32_sends(self):
        self.assign("tank-1", "BATCH-E1")
        sent = as_device_reading(next(Simulator(seed=1).readings()))
        self.assertEqual(set(sent), {"timestamp", "source", "measurements"})
        self.assertEqual(set(sent["measurements"]), {"temperature_c", "ph"})
        self.assertEqual(self.post(sent, key=self.key).status_code, 201)


if __name__ == "__main__":
    unittest.main()
