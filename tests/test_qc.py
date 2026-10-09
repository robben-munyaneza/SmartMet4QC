"""QC rule tests. No database needed."""

import unittest
from datetime import datetime, timedelta, timezone

from smartmet_qc import Observation, evaluate, reconcile, replay
from smartmet_qc.evaluate import SENSOR_SETS, evaluate_set
from smartmet_qc.rules import theil_sen_slope
from smartmet_sim import Simulator

T0 = datetime(2026, 10, 9, tzinfo=timezone.utc)


def obs(hour, source="device", **values):
    return Observation(T0 + timedelta(hours=hour), source, values)


def simulated(scenario, seed=1, fault_rate=0.0):
    return [
        Observation(datetime.fromisoformat(r["timestamp"]), r["source"], r["measurements"])
        for r in Simulator(scenario=scenario, seed=seed, fault_rate=fault_rate).readings()
    ]


def rules(alerts):
    return {a.rule for a in alerts}


class ScenarioTests(unittest.TestCase):
    def test_each_scenario_raises_its_alert(self):
        expected = {"overheat": "temperature_high", "stuck": "fermentation_stuck", "contamination": "ph_low"}
        for scenario, rule in expected.items():
            with self.subTest(scenario):
                self.assertIn(rule, rules(replay(simulated(scenario))))

    def test_normal_batch_only_reports_finished(self):
        alerts = replay(simulated("normal"))
        self.assertEqual(rules(alerts), {"batch_finished"})
        self.assertEqual(alerts[0].severity, "info")


class AlertLifecycleTests(unittest.TestCase):
    def test_lasting_problem_is_one_alert_that_resolves(self):
        temps = [26, 26, 31, 32, 33, 31, 27, 26]
        alerts = replay([obs(h, temperature_c=t) for h, t in enumerate(temps)])
        [alert] = [a for a in alerts if a.rule == "temperature_high"]
        self.assertEqual(alert.opened_at, T0 + timedelta(hours=3))  # 2nd reading above the limit
        self.assertEqual(alert.resolved_at, T0 + timedelta(hours=6))
        self.assertEqual(alert.status, "resolved")

    def test_reconcile(self):
        cond = evaluate([obs(0, ph=3.2), obs(1, ph=3.1)], T0)
        self.assertEqual(reconcile([], cond), (cond, [], []))
        self.assertEqual(reconcile([("ph_low", "ph")], cond), ([], cond, []))
        self.assertEqual(reconcile([("ph_low", "ph")], []), ([], [], [("ph_low", "ph")]))


class SensorFaultTests(unittest.TestCase):
    def test_single_spike_is_flagged_but_raises_no_process_alert(self):
        temps = [26.0, 26.1, 25.9, 26.0, 34.0, 26.1, 26.0]
        alerts = replay([obs(h, temperature_c=t) for h, t in enumerate(temps)])
        self.assertEqual(rules(alerts), {"sensor_spike"})
        self.assertEqual(alerts[0].opened_at, T0 + timedelta(hours=4))
        self.assertEqual(alerts[0].resolved_at, T0 + timedelta(hours=5))

    def test_frozen_sensor_after_six_identical_values(self):
        values = [4.50, 4.49, 4.48] + [4.47] * 6
        alerts = replay([obs(h, ph=v) for h, v in enumerate(values)])
        [alert] = alerts
        self.assertEqual((alert.rule, alert.opened_at), ("sensor_stuck", T0 + timedelta(hours=8)))

    def test_missing_value_from_a_sensor_that_worked(self):
        history = [obs(0, temperature_c=26.0, ph=4.5), obs(1, temperature_c=26.0, ph=None)]
        self.assertEqual({c.rule for c in evaluate(history, T0)}, {"sensor_missing"})

    def test_sensor_that_never_reported_is_not_missing(self):
        history = [obs(0, temperature_c=26.0, ph=None), obs(1, temperature_c=26.1, ph=None)]
        self.assertEqual(evaluate(history, T0), [])

    def test_partial_manual_readings_are_normal(self):
        history = [obs(0, temperature_c=26.0, ph=4.5), obs(0, "manual", brix=20.0),
                   obs(1, temperature_c=26.1, ph=4.5)]
        self.assertEqual(evaluate(history, T0), [])


class TrendTests(unittest.TestCase):
    def test_theil_sen_ignores_one_outlier(self):
        points = [(T0 + timedelta(hours=h), 20 - 0.5 * h) for h in range(10)]
        points[4] = (points[4][0], 40.0)
        self.assertAlmostEqual(theil_sen_slope(points), -0.5)

    def test_stuck_fermentation_with_manual_brix_three_times_a_day(self):
        history = [obs(h, "manual", brix=b) for h, b in [(32, 14.2), (40, 14.0), (48, 13.9), (56, 13.9)]]
        [cond] = evaluate(history, T0)
        self.assertEqual(cond.rule, "fermentation_stuck")

    def test_young_batch_is_not_stuck(self):
        history = [obs(h, "manual", brix=b) for h, b in [(0, 20.0), (8, 19.9), (16, 19.8), (24, 19.6)]]
        self.assertEqual(evaluate(history, T0), [])


class SensorTestHarness(unittest.TestCase):
    """The MVP sensor decision from MVP_PLAN.md §5C, on a few runs."""

    def test_mvp_sensor_set_catches_everything(self):
        r = evaluate_set(*SENSOR_SETS["MVP: T + pH hourly, Brix by hand /8 h"], runs=3, fault_rate=0.02)
        for scenario in ("overheat", "stuck", "contamination"):
            self.assertEqual(r[scenario]["caught"], 3, scenario)
        self.assertEqual(r["normal"]["false_alarms"], 0)

    def test_without_ph_contamination_is_missed(self):
        r = evaluate_set(*SENSOR_SETS["MVP without pH"], runs=3, fault_rate=0.0)
        self.assertEqual(r["contamination"]["caught"], 0)


if __name__ == "__main__":
    unittest.main()
