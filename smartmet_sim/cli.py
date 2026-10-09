"""Command-line interface: python simulator.py --help"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

from .model import SCENARIOS
from .simulator import Simulator

LABELS = (
    ("temperature_c", "T", "C"),
    ("ph", "pH", ""),
    ("brix", "Brix", ""),
    ("turbidity_ntu", "Turb", "NTU"),
    ("ethanol_percent", "EtOH", "%"),
)


DEVICE_SENSORS = ("temperature_c", "ph")  # what the MVP ESP32 measures (PLAN.md, Phase 6)


def as_device_reading(reading: dict) -> dict:
    """Exactly what the ESP32 sends: no batch (the server knows it), no answer key."""
    return {
        "timestamp": reading["timestamp"],
        "source": "device",
        "measurements": {k: reading["measurements"][k] for k in DEVICE_SENSORS},
    }


def format_reading(reading: dict) -> str:
    m = reading["measurements"]
    sim = reading.get("simulation")
    parts = [reading["timestamp"][:16].replace("T", " ")]
    if sim:
        parts[0] += f"  h={sim['elapsed_hours']:6.1f}"
    for key, label, unit in LABELS:
        if key in m:
            value = "----" if m[key] is None else f"{m[key]:.2f}"
            parts.append(f"{label}={value}{unit}")
    line = "  ".join(parts)
    if sim and sim["injected_faults"]:
        line += "  FAULT: " + ", ".join(f"{k}={v}" for k, v in sim["injected_faults"].items())
    return line


def post_reading(url: str, reading: dict, api_key: str | None = None) -> tuple:
    """Send one reading to the backend. Returns (response body, None) or (None, error message)."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        url,
        data=json.dumps(reading).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read() or b"{}"), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, f"cannot reach {url}: {getattr(exc, 'reason', exc)}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="simulator.py",
        description="SmartMet4QC virtual sensors for one fermentation batch.",
    )
    parser.add_argument("--batch-id", default="BATCH-001")
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="real seconds to wait between readings (default 5, use 0 for no wait)")
    parser.add_argument("--hours-per-reading", type=float, default=1.0,
                        help="simulated batch hours that pass per reading (default 1)")
    parser.add_argument("--count", type=int, default=None,
                        help="number of readings (default: until the batch is finished)")
    parser.add_argument("--fault-rate", type=float, default=0.0,
                        help="chance (0-1) that each sensor reading has an injected fault")
    parser.add_argument("--seed", type=int, default=None, help="repeat the exact same run")
    parser.add_argument("--json", action="store_true", help="print raw JSON instead of a summary line")
    parser.add_argument("--jsonl", metavar="FILE", help="also append each reading to a JSON Lines file")
    parser.add_argument("--http", metavar="URL", nargs="?", const="http://127.0.0.1:8000/api/v1/measurements",
                        help="also send each reading to the backend (default URL: %(const)s)")
    parser.add_argument("--device", action="store_true",
                        help="act like the ESP32: send only temperature and pH, as source 'device', without "
                             "batch id (the server uses the batch assigned to the device); needs --api-key")
    parser.add_argument("--api-key", help="device API key (from: python -m smartmet_db device add NAME)")
    args = parser.parse_args(argv)
    if args.device and not args.api_key:
        parser.error("--device needs --api-key")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        sim = Simulator(
            batch_id=args.batch_id,
            scenario=args.scenario,
            hours_per_reading=args.hours_per_reading,
            fault_rate=args.fault_rate,
            seed=args.seed,
        )
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    target = "the device's assigned batch" if args.device else f"batch {args.batch_id}"
    print(f"SmartMet4QC simulator - {target}, scenario '{args.scenario}'. Press Ctrl+C to stop.")
    out_file = open(args.jsonl, "a", encoding="utf-8") if args.jsonl else None
    sent = failed = 0
    try:
        for i, reading in enumerate(sim.readings(args.count)):
            if i and args.interval > 0:
                time.sleep(args.interval)
            if args.device:
                reading = as_device_reading(reading)
            print(json.dumps(reading) if args.json else format_reading(reading), flush=True)
            if out_file:
                out_file.write(json.dumps(reading) + "\n")
                out_file.flush()
            if args.http:
                # Like a real sensor: report the problem and keep measuring.
                body, error = post_reading(args.http, reading, args.api_key)
                if error:
                    failed += 1
                    print(f"  SEND FAILED: {error}", flush=True)
                else:
                    sent += 1
                    for alert in body.get("new_alerts", []):
                        print(f"  ALERT [{alert['severity']}] {alert['rule']}: {alert['message']}", flush=True)
        print("Batch finished.")
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    finally:
        if out_file:
            out_file.close()
        if args.http:
            print(f"Sent to backend: {sent} ok, {failed} failed.")
