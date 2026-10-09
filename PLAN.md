# SmartMet4QC — Project Plan

SmartMet4QC is a quality-control (QC) monitoring system for a banana-based
alcoholic beverage. It collects measurements (temperature, pH, Brix, turbidity,
ethanol) for each production batch, stores them, shows them on a dashboard and
raises alerts when a reading is outside the configured quality limits.

> For the MVP scope, the sensor choice and the test strategy, see
> [MVP_PLAN.md](MVP_PLAN.md).

We build it in phases, in this order. Each phase must pass its checkpoint
before the next one starts, so there is always something you can run and test.

| Phase | Name | What we build | Checkpoint | Status |
|---|---|---|---|---|
| 1 | Simulator | Realistic fake sensor readings, scenarios, faults | Unit tests pass | ✅ done |
| 2 | Database | PostgreSQL database, tables for batches + readings, import simulator files | Simulated batch stored and read back; DB tests pass | ✅ done |
| 3 | Backend API | FastAPI: `POST /api/v1/measurements`, read endpoints; simulator `--http` | Simulator posts readings and they appear in the DB | ✅ done |
| 4 | QC rules + alerts | Limits, alert table, faulty-sensor checks; sensor test from [MVP_PLAN.md](MVP_PLAN.md) §5C | Every scenario caught, no false alerts on `normal` | ✅ done ([results](docs/sensor_test_results.md)) |
| 5 | Dashboard | Charts, batch history, alerts, manual-entry form | MVP checklist items 1–9 | next |
| 6 | Hardware | ESP32 with temperature + pH sending the same JSON | Bench test + side-by-side batch | |

The old "layers" in this file map to phases as: simulator → 1, database → 2,
backend → 3, QC → 4, dashboard → 5, hardware → 6. The database comes before
the API so that the API is built on a schema we have already tested.

## Phase 2 — Database (PostgreSQL)

- Server: the local PostgreSQL 17 service. It accepts connections from this
  computer without a password (`trust` in `pg_hba.conf`).
- The app gets its own login role `smartmet` and its own database
  `smartmet4qc`, so it never uses the `postgres` superuser. The password for
  `smartmet` is generated once and saved in `.env` (not committed to git).
- Tables:
  - `batches`: one row per production batch (`code` such as `BATCH-001`,
    status, start/end time).
  - `readings`: one row per reading. It has one nullable column per
    measurement, a `source` (`simulated` / `device` / `manual`), and the
    simulator's answer key in a `simulation` JSON column. The same batch,
    time and source can only be stored once, so importing a file twice does
    not create duplicates.
- Commands: `python -m smartmet_db setup | init | import FILE | summary`.
- Quality limits and alerts tables come in Phase 4. They are not needed yet.

## Phase 3 — Backend API (FastAPI)

- Run: `python -m uvicorn smartmet_api.main:app --reload`. Interactive docs
  are at http://127.0.0.1:8000/docs.
- Endpoints:
  - `POST /api/v1/measurements`: one reading in the data-contract shape.
    Returns `201` when stored, `200` when the same reading was already stored
    (so a device can safely resend after a network error), and `422` with a
    reason when the reading is invalid.
  - `GET /api/v1/batches`: all batches with reading counts.
  - `GET /api/v1/batches/{code}/readings?limit=N`: the newest N readings,
    oldest first.
  - `GET /health`: the API and the database are reachable.
- Validation (Pydantic): time zone required; source must be `simulated`,
  `device` or `manual`; only known measurements; numbers only (no text);
  physically possible values; at least one measurement. `null` = sensor
  dropout and is accepted.
- The simulator sends readings with `--http`. If the backend is down it
  reports the error and keeps going, like a real sensor would.
- Not yet: authentication for devices (before real hardware, Phase 6) and
  database migrations (Alembic, added the first time an existing table must
  change).

The **data contract** (the JSON shape of one reading) is what connects the
layers. If the simulator and later the ESP32 send the same shape, the backend
never needs to know which one is talking to it.

---

## Analysis of the starting point (from the planning chat)

The chat gives a first simulator that uses `random.uniform(...)` for every
value. That is a good "hello world", but it is too random to test a QC system:

| Problem with pure random values | Why it matters for later layers |
|---|---|
| Brix and ethanol jump around independently | Real fermentation: sugar (Brix) **falls** while ethanol **rises**. Charts would look meaningless. |
| Every value is equally likely in the range | Alerts (Layer 4) would fire randomly; you cannot tell if the alert logic is right. |
| No time progression | Batch history (Layer 3/5) needs a batch that starts, ferments and finishes. |
| No sensor problems | Real sensors drift, spike or drop out. QC must be tested against bad data too. |
| No repeatability | A bug you saw once cannot be reproduced. |
| Output only printed | Nothing to feed into the backend/database later. |

## Phase 1 — Simulator

### Goal
A command-line program that behaves like a set of sensors on one fermentation
batch, producing readings that are **realistic in shape**, **reproducible**,
and **useful for testing the later layers**.

### What it does
1. **Fermentation model (the "truth")** — for each simulated hour of the batch:
   - Brix falls along an S-curve (slow start, active phase, slowdown).
   - Ethanol rises in proportion to the sugar consumed.
   - pH drifts down slowly (the beverage gets more acidic).
   - Temperature stays near a set point, warming slightly during the most
     active fermentation.
   - Turbidity rises while yeast is active, then settles back down.
2. **Scenarios** to test QC behaviour:
   - `normal` — a healthy batch.
   - `overheat` — temperature control fails and temperature climbs.
   - `stuck` — fermentation stops halfway (Brix stays high, ethanol stays low).
   - `contamination` — pH drops too far and turbidity rises (spoilage).
3. **Sensor layer** on top of the truth:
   - small measurement noise on every reading,
   - optional injected faults: `spike` (sudden wrong value), `dropout`
     (no value = `null`), `stuck` (sensor repeats its last value).
4. **Output**:
   - readable line in the terminal (default) or raw JSON (`--json`),
   - optional JSON Lines file (`--jsonl readings.jsonl`) — one reading per line,
     which Layer 2/3 can import later.
5. **Options**: batch id, scenario, seconds between readings, simulated hours
   per reading, number of readings, fault rate, random seed.

### Data contract (one reading)
```json
{
  "timestamp": "2026-10-09T10:00:00+00:00",
  "batch_id": "BATCH-001",
  "source": "simulated",
  "measurements": {
    "temperature_c": 26.12,
    "ph": 4.51,
    "brix": 19.84,
    "turbidity_ntu": 15.7,
    "ethanol_percent": 0.09
  },
  "simulation": {
    "scenario": "normal",
    "elapsed_hours": 3.0,
    "injected_faults": {}
  }
}
```
- `timestamp`, `batch_id`, `source`, `measurements` = what a real sensor
  device (ESP32) will also send.
- `simulation` = extra "answer key" only the simulator knows. Layer 4 can use
  it to check whether the QC system caught the injected faults. Real devices
  will not send it, and the backend must treat it as optional.
- A measurement may be `null` (sensor dropout). The backend must accept that.
- `timestamp` follows the **simulated clock**: batch start + elapsed simulated
  hours, so a 5-day batch has 5 days of timestamps even if it runs in minutes.

### Design decisions
- **Python standard library only** — nothing to `pip install` for Layer 1.
- **Package + thin entry script**: code in `smartmet_sim/`, run with
  `python simulator.py`.
- **Seeded randomness** (`--seed`) so a run can be repeated exactly.
- **Numbers are illustrative**, chosen to look plausible for a fermented fruit
  beverage. They are NOT validated process limits or safety thresholds; real
  limits must come from your own lab measurements.

### Files
```
SmartMet4QC/
  PLAN.md                 this plan
  README.md               how to run
  simulator.py            entry point: python simulator.py ...
  smartmet_sim/
    __init__.py
    model.py              fermentation model + scenarios (true values)
    sensors.py            noise + fault injection (what sensors report)
    simulator.py          builds readings in the data-contract shape
    cli.py                command-line options and output
  tests/
    test_simulator.py     automated checks (python -m unittest)
```

### Done when
- `python simulator.py` streams readings every 5 s and stops cleanly on Ctrl+C.
- Brix falls and ethanol rises over a `normal` batch.
- Each scenario visibly changes the behaviour it is meant to.
- The same `--seed` gives the same readings.
- `--jsonl` writes valid JSON Lines.
- `python -m unittest` passes.

---

## Phase 4 — QC rules and alerts

### How it works
After each new reading is stored, the backend checks the recent history of
that batch (the last 30 hours). The result is a set of **conditions** that are
true right now, for example "temperature too high". The conditions are compared
with the batch's **open alerts**:

- condition true, no open alert → **open** a new alert
- condition true, alert already open → keep it open and update its last value
  (no duplicate alerts when the problem lasts for hours)
- alert open, condition no longer true → **resolve** the alert

The rules live in a separate package (`smartmet_qc`) that does not need the
database. The API, the import command and the sensor test all use the same
code.

### Rules (limits are placeholders until real batch data exists)

| Rule | Measurement | Fires when | Severity | Catches |
|---|---|---|---|---|
| `temperature_high` | temperature | above 30 °C for 2 readings in a row | warning | overheating |
| `temperature_low` | temperature | below 18 °C for 2 readings in a row | warning | too cold / slow |
| `ph_low` | pH | below 3.5 for 2 readings in a row | critical | souring / contamination |
| `turbidity_high` | turbidity | above 90 NTU for 2 readings in a row | warning | spoilage (weak signal) |
| `fermentation_stuck` | Brix | batch is at least 36 h old, Brix is still above 9, and it fell less than 1 Brix/day over the last 24 h | warning | stuck fermentation |
| `batch_finished` | Brix | Brix is below 9 and changed less than 0.3/day over the last 24 h | info | batch ready |
| `sensor_spike` | any | the value jumps far from the median of the previous 3 values (allowing for time between readings) | warning | broken sensor / typo |
| `sensor_stuck` | any (not manual) | 6 identical values in a row from the same source | warning | frozen sensor |
| `sensor_missing` | any (not manual) | the sensor sent no value, but it did send values earlier | warning | disconnected sensor |

"2 readings in a row" means a single wrong value (a spike) cannot raise a
process alert. The trend rules use a robust slope (Theil–Sen), so they also
work with only 3 manual Brix readings a day and are not thrown off by one bad
value.

### Changes
- **Simulator:** a `stuck` sensor fault now lasts 6–12 readings. A frozen sensor
  stays frozen, and a single repeated value cannot be told apart from normal
  noise.
- **Database:** new `alerts` table: batch, rule, measurement, severity,
  status (`open` / `resolved`), message, value, opened / last seen / resolved
  times. A batch can have only one open alert per rule and measurement.
  Existing tables do not change, so no migration tool is needed yet. (Alembic
  will be added the first time an existing table must change.)
- **API:** `POST /api/v1/measurements` also returns the alerts that this
  reading opened. New `GET /api/v1/alerts?status=open&batch=CODE`.
- **Simulator `--http`:** prints the alerts the backend reports.
- **Import:** after importing a file, alerts for that batch are rebuilt by
  replaying its readings in order.
- **Sensor test** (`python -m smartmet_qc.evaluate`): the experiment from
  [MVP_PLAN.md](MVP_PLAN.md) §5C. It runs 20 batches per scenario with a 2%
  sensor fault rate for several sensor sets, including the MVP set
  (temperature + pH every hour, Brix typed in by hand every 8 h). It then
  reports what was caught, how fast, and the false alarms.

### Done when
- In the MVP sensor set, each problem scenario is caught in ≥95% of runs.
- No warning or critical alert on any `normal` batch.
- Injected sensor faults are flagged, and the report shows the rate.
- Alerts appear through the API when the simulator sends a problem batch.

### Result
All four criteria are met. See [docs/sensor_test_results.md](docs/sensor_test_results.md).

- **MVP set (T + pH hourly, Brix by hand every 8 h): PASS.** It caught 20/20
  of each problem with 0 false alarms, as fast as having all 5 sensors.
  The only difference: "finished" is reported 5 h later (h96 instead of h91)
  because Brix is measured less often.
- **Removing any one of the three fails:**
  - without pH, contamination is missed (0/20)
  - without temperature, overheating is missed (0/20)
  - without Brix, stuck fermentation and "finished" are missed (0/20)
- **Turbidity cannot replace pH:** contamination was caught 0/20.
- **Ethanol** added nothing to detection.
- **Sensor faults:** missing values and frozen sensors are almost always
  flagged. Most spikes are flagged too. The report lists the exceptions and
  why they happen.
- **Known gap for Phase 5:** typos in hand-typed Brix are not flagged
  automatically (12 of 12 missed). The manual-entry form must catch them,
  for example by asking for confirmation when a value differs a lot from the
  last one.
- These are results on **simulated** batches with our assumed fermentation
  curve. The rule limits must be re-checked on real batch data (Phase 6).

## Next phases (overview; detailed plans come when we start each one)

Phases 2 and 3 are described above.

**Phase 4 — QC rules and alerts.** Per-measurement limits stored in config/DB
(min/max, rate of change), plus data-quality checks (missing value, spike,
stuck sensor). Use the simulator scenarios and the `simulation.injected_faults`
answer key to check that alerts fire correctly.

**Phase 5 — Dashboard.** Live chart per measurement, batch list and history,
alert list. Start simple (server-rendered pages or a small JS frontend).

**Phase 6 — Hardware.** ESP32 reads physical sensors and POSTs the same JSON
shape (without `simulation`). Sensor calibration and accuracy are checked
separately; simulated data cannot prove that.
