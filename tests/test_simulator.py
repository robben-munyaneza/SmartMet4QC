import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

from smartmet_sim import SENSORS, FermentationModel, SensorArray, Simulator
from smartmet_sim.cli import main

KEYS = set(SENSORS)


class ModelTests(unittest.TestCase):
    def test_normal_batch_ferments(self):
        model = FermentationModel()
        start, end = model.true_values(0), model.true_values(120)
        self.assertAlmostEqual(start["brix"], 20.0, places=3)
        self.assertAlmostEqual(start["ethanol_percent"], 0.0, places=3)
        self.assertLess(end["brix"], 7.0)
        self.assertGreater(end["ethanol_percent"], 7.0)
        self.assertLess(end["ph"], start["ph"])

    def test_brix_never_rises_and_ethanol_never_falls(self):
        model = FermentationModel()
        values = [model.true_values(h) for h in range(121)]
        for before, after in zip(values, values[1:]):
            self.assertLessEqual(after["brix"], before["brix"])
            self.assertGreaterEqual(after["ethanol_percent"], before["ethanol_percent"])

    def test_scenarios_change_the_expected_measurement(self):
        normal = FermentationModel(scenario="normal").true_values(96)
        self.assertGreater(FermentationModel(scenario="overheat").true_values(96)["temperature_c"],
                           normal["temperature_c"] + 5)
        self.assertGreater(FermentationModel(scenario="stuck").true_values(96)["brix"],
                           normal["brix"] + 5)
        contaminated = FermentationModel(scenario="contamination").true_values(96)
        self.assertLess(contaminated["ph"], normal["ph"] - 0.5)
        self.assertGreater(contaminated["turbidity_ntu"], normal["turbidity_ntu"] + 30)

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            FermentationModel(scenario="banana")


class SensorTests(unittest.TestCase):
    def test_no_faults_by_default(self):
        sensors = SensorArray(random.Random(1))
        truth = FermentationModel().true_values(10)
        for _ in range(200):
            measurements, faults = sensors.read(truth)
            self.assertEqual(faults, {})
            for key, value in measurements.items():
                self.assertAlmostEqual(value, truth[key], delta=SENSORS[key].noise_std * 6)

    def test_fault_rate_one_injects_every_fault_type(self):
        sensors = SensorArray(random.Random(2))
        truth = FermentationModel().true_values(10)
        sensors.read(truth)  # one good reading so a "stuck" sensor has a value to repeat
        sensors.fault_rate = 1.0
        seen = set()
        for _ in range(100):
            measurements, faults = sensors.read(truth)
            self.assertEqual(set(faults), KEYS)
            seen.update(faults.values())
            for key, kind in faults.items():
                if kind == "dropout":
                    self.assertIsNone(measurements[key])
        self.assertEqual(seen, {"spike", "dropout", "stuck"})

    def test_stuck_fault_lasts_several_readings(self):
        sensors = SensorArray(random.Random(4))
        truth = FermentationModel().true_values(10)
        good, _ = sensors.read(truth)
        sensors.fault_rate = 0.3
        for _ in range(500):
            measurements, faults = sensors.read(truth)
            if faults.get("ph") == "stuck":
                break
        sensors.fault_rate = 0.0
        frozen = [measurements["ph"]]
        while True:
            measurements, faults = sensors.read(truth)
            if faults.get("ph") != "stuck":
                break
            frozen.append(measurements["ph"])
        self.assertGreaterEqual(len(frozen), 6)
        self.assertLessEqual(len(frozen), 12)
        self.assertEqual(len(set(frozen)), 1)

    def test_values_stay_in_sensor_range(self):
        sensors = SensorArray(random.Random(3), fault_rate=0.5)
        for h in range(0, 121, 5):
            measurements, _ = sensors.read(FermentationModel(scenario="contamination").true_values(h))
            for key, value in measurements.items():
                if value is not None:
                    self.assertGreaterEqual(value, SENSORS[key].min_value)
                    self.assertLessEqual(value, SENSORS[key].max_value)


class SimulatorTests(unittest.TestCase):
    def test_reading_matches_data_contract(self):
        reading = next(Simulator(seed=1).readings())
        self.assertEqual(set(reading), {"timestamp", "batch_id", "source", "measurements", "simulation"})
        self.assertEqual(reading["source"], "simulated")
        self.assertEqual(set(reading["measurements"]), KEYS)
        self.assertEqual(set(reading["simulation"]), {"scenario", "elapsed_hours", "injected_faults"})
        json.dumps(reading)  # must be JSON-serialisable

    def test_same_seed_same_readings(self):
        a = Simulator(seed=42, fault_rate=0.2)
        b = Simulator(seed=42, fault_rate=0.2, start_time=a.start_time)
        self.assertEqual(list(a.readings()), list(b.readings()))

    def test_default_run_covers_whole_batch(self):
        readings = list(Simulator(seed=1, hours_per_reading=2).readings())
        self.assertEqual(len(readings), 61)
        self.assertEqual(readings[-1]["simulation"]["elapsed_hours"], 120)


class CliTests(unittest.TestCase):
    def test_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.jsonl")
            with redirect_stdout(StringIO()):
                main(["--count", "5", "--interval", "0", "--seed", "1", "--jsonl", path])
            with open(path, encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0]["batch_id"], "BATCH-001")


if __name__ == "__main__":
    unittest.main()
