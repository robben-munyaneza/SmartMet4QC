"""Sensor test (MVP_PLAN.md §5C): which sensors does the MVP need?

Runs many simulated batches per scenario through the QC rules with different
sensor sets, and reports what was caught, how fast, and the false alarms.

    python -m smartmet_qc.evaluate
    python -m smartmet_qc.evaluate --runs 50 --fault-rate 0.05 --out results.md
"""

import argparse
from datetime import datetime
from statistics import median

from smartmet_sim import Simulator

from .alerts import replay
from .rules import Observation

ALL = ("temperature_c", "ph", "brix", "turbidity_ntu", "ethanol_percent")
MANUAL_EVERY_HOURS = 8  # Brix typed in by hand about 3 times a day

# name: (measurements from the automatic device every hour, measurements typed in by hand)
SENSOR_SETS = {
    "All 5 sensors, hourly": (ALL, ()),
    "MVP: T + pH hourly, Brix by hand /8 h": (("temperature_c", "ph"), ("brix",)),
    "T + pH + Brix hourly": (("temperature_c", "ph", "brix"), ()),
    "MVP without pH": (("temperature_c",), ("brix",)),
    "MVP without temperature": (("ph",), ("brix",)),
    "MVP without Brix": (("temperature_c", "ph"), ()),
    "MVP, turbidity instead of pH": (("temperature_c", "turbidity_ntu"), ("brix",)),
}

# scenario: rule that must catch it, hour the problem starts
EXPECTED = {
    "overheat": ("temperature_high", 24),
    "stuck": ("fermentation_stuck", 0),
    "contamination": ("ph_low", 48),
    "normal": ("batch_finished", None),
}
PROCESS_SEVERITIES = ("warning", "critical")


def to_observations(readings, device, manual):
    """Split simulator readings into what the chosen sensor set would really record."""
    observations, faults = [], {}
    for r in readings:
        t = datetime.fromisoformat(r["timestamp"])
        m = r["measurements"]
        injected = r["simulation"]["injected_faults"]
        faults[t] = {}
        if device:
            observations.append(Observation(t, "device", {k: m[k] for k in device}))
            faults[t].update({k: v for k, v in injected.items() if k in device})
        hour = r["simulation"]["elapsed_hours"]
        if manual and hour % MANUAL_EVERY_HOURS == 0:
            values = {k: m[k] for k in manual if m[k] is not None}
            if values:
                observations.append(Observation(t, "manual", values))
                # A spike in a hand-typed value is a typo. A person cannot "freeze" or "drop out".
                faults[t].update({k: v for k, v in injected.items() if k in values and v == "spike"})
    return observations, faults


def fault_episodes(faults):
    """Group injected faults into episodes: a frozen sensor over several readings is one episode."""
    episodes, current = [], {}
    for t in sorted(faults):
        for measurement, kind in faults[t].items():
            ep = current.get(measurement)
            if kind == "stuck" and ep and ep["kind"] == "stuck" and ep["end"] == prev:
                ep["times"].append(t)
                ep["end"] = t
            else:
                ep = {"measurement": measurement, "kind": kind, "times": [t], "end": t}
                episodes.append(ep)
                current[measurement] = ep
        prev = t
    return episodes


def run_one(scenario, seed, device, manual, fault_rate):
    readings = list(Simulator(scenario=scenario, seed=seed, fault_rate=fault_rate).readings())
    observations, faults = to_observations(readings, device, manual)
    start = datetime.fromisoformat(readings[0]["timestamp"])
    alerts = replay(observations, batch_start=start)

    expected_rule, _ = EXPECTED[scenario]
    hits = [a for a in alerts if a.rule == expected_rule]
    false_alarm = scenario == "normal" and any(
        a.severity in PROCESS_SEVERITIES and not a.rule.startswith("sensor_") for a in alerts)

    sensor_alerts = [a for a in alerts if a.rule.startswith("sensor_")]
    episodes = fault_episodes(faults)
    for ep in episodes:
        ep["detected"] = any(
            a.measurement == ep["measurement"] and any(a.covers(t) for t in ep["times"]) for a in sensor_alerts)
    times = sorted(faults)
    false_sensor = 0
    for a in sensor_alerts:
        i = times.index(a.opened_at) if a.opened_at in times else None
        nearby = [faults[times[j]] for j in (i, i - 1) if i is not None and j >= 0]
        if not any(a.measurement in f for f in nearby):
            false_sensor += 1

    return {
        "caught_hour": (hits[0].opened_at - start).total_seconds() / 3600 if hits else None,
        "false_alarm": false_alarm,
        "episodes": episodes,
        "false_sensor": false_sensor,
    }


def evaluate_set(device, manual, runs, fault_rate):
    result = {}
    for scenario in EXPECTED:
        outcomes = [run_one(scenario, seed, device, manual, fault_rate) for seed in range(1, runs + 1)]
        hours = [o["caught_hour"] for o in outcomes if o["caught_hour"] is not None]
        result[scenario] = {
            "caught": len(hours),
            "median_hour": median(hours) if hours else None,
            "false_alarms": sum(o["false_alarm"] for o in outcomes),
            "episodes": [ep for o in outcomes for ep in o["episodes"]],
            "false_sensor": sum(o["false_sensor"] for o in outcomes),
        }
    return result


def report(runs, fault_rate) -> str:
    lines = [
        f"# Sensor test results",
        "",
        f"{runs} simulated batches per scenario, sensor fault rate {fault_rate:.0%}. "
        "Cell = batches where the problem was caught, and the median hour it was caught.",
        "Problems start at: overheat h24, contamination h48, stuck from the start (visible after h36).",
        "",
        "| Sensor set | Overheat | Stuck | Contamination | Finished (normal) | False alarms (normal) | Verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    fault_lines = [
        "",
        "## Sensor faults flagged",
        "",
        "| Sensor set | Spikes | Missing values | Frozen sensors | False sensor alerts per batch |",
        "|---|---|---|---|---|",
    ]
    for name, (device, manual) in SENSOR_SETS.items():
        r = evaluate_set(device, manual, runs, fault_rate)

        def cell(scenario):
            s = r[scenario]
            hour = f" (h{s['median_hour']:.0f})" if s["median_hour"] is not None else ""
            return f"{s['caught']}/{runs}{hour}"

        problems_ok = all(r[s]["caught"] >= 0.95 * runs for s in ("overheat", "stuck", "contamination"))
        verdict = "PASS" if problems_ok and r["normal"]["false_alarms"] == 0 else "FAIL"
        lines.append(
            f"| {name} | {cell('overheat')} | {cell('stuck')} | {cell('contamination')} | "
            f"{cell('normal')} | {r['normal']['false_alarms']}/{runs} | **{verdict}** |")

        episodes = [ep for s in r.values() for ep in s["episodes"]]

        def rate(kind):
            eps = [ep for ep in episodes if ep["kind"] == kind]
            return f"{sum(ep['detected'] for ep in eps)}/{len(eps)}" if eps else "-"

        false_per_batch = sum(s["false_sensor"] for s in r.values()) / (runs * len(r))
        fault_lines.append(
            f"| {name} | {rate('spike')} | {rate('dropout')} | {rate('stuck')} | {false_per_batch:.2f} |")

    lines += fault_lines
    lines += [
        "",
        "Why some faults are not flagged:",
        "- Spikes that push a value below 0 are clipped to 0 and look like real values (turbidity, ethanol).",
        "- Spikes in Brix typed by hand every 8 h: real Brix can change several units between entries,",
        "  so a typo cannot be told apart from fast fermentation. The entry form must check typos instead.",
        "- A frozen sensor needs 6 identical values; one that freezes in the last hours of a batch is not",
        "  flagged before the batch ends.",
        "- A missing value in the very first reading: there is no earlier value to say the sensor worked.",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m smartmet_qc.evaluate", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=20, help="batches per scenario (default 20)")
    parser.add_argument("--fault-rate", type=float, default=0.02, help="sensor fault rate (default 0.02)")
    parser.add_argument("--out", metavar="FILE", help="also save the report to a Markdown file")
    args = parser.parse_args(argv)
    text = report(args.runs, args.fault_rate)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
