# How SmartMet4QC works: the complete guide

This guide explains the whole project, from the sensor to the screen: where
every number comes from, every calculation, how the parts talk to each other,
and how the database is connected. Read it next to the code. Every section
links to the file it explains.

**How to study it:** read Part 0 first (the big picture). Then follow one
reading through the system in Part 8, and come back to the detailed parts when
you want to understand one piece deeply. Part 11 has questions to test
yourself: if you can answer them, you can explain the project to anyone.

---

## Contents

- [Part 0. The big picture](#part-0-the-big-picture)
- [Part 1. The data contract: the shape of one reading](#part-1-the-data-contract-the-shape-of-one-reading)
- [Part 2. The simulator (`smartmet_sim/`)](#part-2-the-simulator-smartmet_sim)
- [Part 3. The database (`smartmet_db/`)](#part-3-the-database-smartmet_db)
- [Part 4. The backend API (`smartmet_api/`)](#part-4-the-backend-api-smartmet_api)
- [Part 5. Quality control (`smartmet_qc/`)](#part-5-quality-control-smartmet_qc)
- [Part 6. The dashboard (`frontend/`)](#part-6-the-dashboard-frontend)
- [Part 7. The ESP32 firmware (`firmware/`)](#part-7-the-esp32-firmware-firmware)
- [Part 8. Follow one reading through everything](#part-8-follow-one-reading-through-everything)
- [Part 9. Every calculation in one place](#part-9-every-calculation-in-one-place)
- [Part 10. The tests (`tests/`)](#part-10-the-tests-tests)
- [Part 11. Check your understanding](#part-11-check-your-understanding)
- [Glossary](#glossary)

---

## Part 0. The big picture

### What the system does
SmartMet4QC watches a fermenting banana beverage. Measurements come in
(temperature, pH, sugar, cloudiness, alcohol). The system stores them, checks
them against quality rules, and shows the result on a dashboard, with
warnings when something goes wrong.

### The parts and how they connect

```
 SOURCES OF DATA                 SERVER (one Python program)                  STORAGE
┌─────────────────┐            ┌───────────────────────────────────┐      ┌──────────────┐
│ Simulator       │──┐         │ FastAPI app  (smartmet_api)       │      │ PostgreSQL   │
│ (smartmet_sim)  │  │  HTTP   │  ├─ checks the JSON  (Pydantic)   │ SQL  │ database     │
├─────────────────┤  │  POST   │  ├─ saves it ───────(smartmet_db)─┼─────▶│ "smartmet4qc"│
│ ESP32 + sensors │──┼────────▶│  ├─ runs the rules  (smartmet_qc) │◀─────│  batches     │
│ (firmware/)     │  │  JSON   │  └─ answers the dashboard         │      │  readings    │
├─────────────────┤  │         └───────────────▲───────────────────┘      │  alerts      │
│ Person typing   │──┘                         │ HTTP GET every 10 s      │  devices     │
│ (dashboard form)│                            │ (JSON)                   └──────────────┘
└─────────────────┘                  ┌─────────┴──────────┐
                                     │ Dashboard (React)  │  runs in the browser
                                     │ (frontend/)        │
                                     └────────────────────┘
```

Three rules hold everything together:

1. **One data shape (the "data contract").** Everything that sends a reading
   sends the same JSON (Part 1), so the server never needs to know who sent it.
2. **One door.** All data goes in and out through the API. The dashboard and
   the sensors never touch the database directly.
3. **One set of rules.** The quality rules are one Python package used
   everywhere: live readings, imports and the sensor test.

### Technologies, and why each was chosen

| Technology | Used for | Why |
|---|---|---|
| **Python 3.13** | simulator, server, rules, database code | easy to read, strong libraries |
| **FastAPI** | the web API | checks incoming data automatically, writes the API docs page (`/docs`) itself |
| **Uvicorn** | runs the FastAPI app | the program that listens on port 8000 and passes requests to FastAPI |
| **Pydantic** | checking JSON | describe the expected shape once; bad data is refused with a clear reason |
| **PostgreSQL 17** | the database | reliable, handles many readings, runs on your PC now and on a server later |
| **SQLAlchemy** | Python ↔ database | write database code in Python classes instead of raw SQL strings |
| **psycopg** | the database driver | the low-level connection SQLAlchemy uses to talk to PostgreSQL |
| **Alembic** | database migrations | changes the tables safely when the code changes |
| **React + TypeScript** | the dashboard | builds interactive pages out of reusable components; TypeScript catches mistakes |
| **Tailwind CSS** | dashboard styling | style directly in the components with small class names |
| **TanStack Query** | dashboard data | loads data from the API and refreshes it every 10 seconds |
| **Recharts** | charts | chart components for React |
| **Vite** | building the dashboard | turns the React code into plain files the browser can run |
| **Arduino C++** | ESP32 firmware | the standard way to program an ESP32 |

### Folder map

```
SmartMet4QC/
├── simulator.py            entry point:  python simulator.py ...
├── smartmet_sim/           PART 2  fake sensors
│   ├── model.py              the fermentation curves ("true" values)
│   ├── sensors.py            noise and sensor faults
│   ├── simulator.py          builds readings in the data-contract shape
│   └── cli.py                command-line options, printing, sending over HTTP
├── smartmet_db/            PART 3  database
│   ├── config.py             reads .env (where the database is)
│   ├── models.py             the tables, as Python classes
│   ├── db.py                 connecting, creating databases, migrations
│   ├── store.py              saving and reading readings
│   ├── devices.py            device keys and batch assignment
│   ├── migrations/           Alembic: step-by-step table changes
│   └── __main__.py           terminal commands: python -m smartmet_db ...
├── smartmet_api/           PART 4  backend
│   ├── main.py               every API address (endpoint) and the dashboard pages
│   └── schemas.py            the JSON shapes in and out (Pydantic)
├── smartmet_qc/            PART 5  quality control
│   ├── config.py             all limits in one place
│   ├── rules.py              "what is wrong right now?"
│   ├── alerts.py             open / keep / resolve alerts; replay
│   ├── service.py            runs the rules against the database
│   ├── plausibility.py       typo check for hand-typed values
│   └── evaluate.py           the sensor test (which sensors does the MVP need?)
├── frontend/               PART 6  dashboard (React)
│   ├── src/main.tsx          starts the app, sets the 10-second refresh
│   ├── src/App.tsx           which page for which address
│   ├── src/lib/              API calls, texts, formatting, calculations
│   ├── src/components/       building blocks: cards, charts, forms, sidebar
│   └── src/pages/            Overview, Batch, Alerts, Devices
├── firmware/               PART 7  ESP32 program
├── tests/                  PART 10 automated tests
├── docs/                   guides and results
├── .env                    database address + password (secret, not in git)
├── alembic.ini             migration settings
└── requirements.txt        Python libraries
```

---

## Part 1. The data contract: the shape of one reading

Every reading, from any source, is this JSON:

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
  "simulation": { "scenario": "normal", "elapsed_hours": 3.0, "injected_faults": {} }
}
```

| Field | Meaning | Rules |
|---|---|---|
| `timestamp` | when it was measured | ISO 8601 **with a time zone** (`+00:00` or `Z`); without a zone the time is ambiguous, so it is refused |
| `batch_id` | which batch it belongs to | text, 1–50 characters; **devices leave it out**, and the server fills in the device's batch |
| `source` | who made it | `simulated`, `device` or `manual` |
| `measurements` | the values | any of the 5 names; a number, or `null` = "the sensor gave no value" |
| `simulation` | the simulator's answer key | only from the simulator: which problem and which faults it injected |

The 5 measurements:

| Name | Unit | What it tells you |
|---|---|---|
| `temperature_c` | °C | is the yeast too hot or too cold? |
| `ph` | pH (0–14) | how acidic it is; too low = souring or contamination |
| `brix` | °Bx | sugar content; falls as yeast turns sugar into alcohol |
| `turbidity_ntu` | NTU | cloudiness |
| `ethanol_percent` | % | alcohol content |

The shape is defined in code in [smartmet_api/schemas.py](../smartmet_api/schemas.py)
(`ReadingIn` and `Measurements`).

---

## Part 2. The simulator (`smartmet_sim/`)

The simulator is a **fake sensor box**. It is built in three layers, each in
its own file:

```
model.py: what the beverage really is  →  sensors.py: what imperfect sensors report  →  simulator.py: packs it as JSON
```

### 2.1 The fermentation model ([smartmet_sim/model.py](../smartmet_sim/model.py))

**The idea:** yeast eats sugar slowly at first, then fast, then slowly again as
the sugar runs out. That gives an **S-shaped curve**, modelled with the
*logistic function*:

```
L(h) = 1 / (1 + e^(−k · (h − m)))
      h = hours since the start
      k = 0.12  (rate_per_hour: how steep the S is)
      m = 36    (midpoint_hours: the moment half the sugar is used)
```

`L(0)` is not exactly 0 (it is 0.013), so the code **normalises** it to start
at exactly 0:

```
progress(h) = (L(h) − L(0)) / (1 − L(0))        → 0 at the start, 1 at the end
```

**Yeast activity** is highest in the middle of the S. The code uses
`4 · L · (1 − L)`, which is 0 at the ends and exactly 1 when L = 0.5:

```
activity(h) = 4 · L(h) · (1 − L(h))
```

From progress and activity, the five true values are calculated
(`true_values`), with the numbers from `BatchProfile`:

| Value | Formula | Start → end |
|---|---|---|
| Brix | `20 − (20 − 6) · progress` | 20 → 6 |
| Ethanol | `(20 − Brix) · 0.55` (alcohol made from the sugar used) | 0 → 7.7 % |
| pH | `4.6 − (4.6 − 3.8) · progress` | 4.6 → 3.8 |
| Temperature | `26 + 2 · activity` (yeast gives off heat when busy) | 26, peak 28 |
| Turbidity | `15 + 60 · activity` (busy yeast clouds the liquid) | 15, peak 75 |

**Worked example**, calculated from the real code:

| Hour | L | progress | activity | Brix | Ethanol | pH | Temp | Turbidity |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.013 | 0.000 | 0.05 | 20.00 | 0.00 | 4.60 | 26.1 | 18 |
| 24 | 0.192 | 0.181 | 0.62 | 17.47 | 1.39 | 4.46 | 27.2 | 52 |
| 36 | 0.500 | 0.493 | 1.00 | 13.09 | 3.80 | 4.21 | 28.0 | 75 |
| 48 | 0.808 | 0.806 | 0.62 | 8.72 | 6.21 | 3.96 | 27.2 | 52 |
| 72 | 0.987 | 0.987 | 0.05 | 6.19 | 7.60 | 3.81 | 26.1 | 18 |
| 120 | 1.000 | 1.000 | 0.00 | 6.00 | 7.70 | 3.80 | 26.0 | 15 |

Check one row yourself. At hour 36, progress is 0.493, so
Brix = 20 − 14 × 0.493 = 13.09, and ethanol = (20 − 13.09) × 0.55 = 3.80.

**Scenarios** change the truth to imitate a problem:

| Scenario | What the code changes | Example |
|---|---|---|
| `normal` | nothing | — |
| `overheat` | after hour 24, temperature `+ 0.15 · (h − 24)`, at most +10 °C | hour 48: 30.8 °C |
| `stuck` | progress and activity × 0.45: the yeast stops before half the sugar is used | Brix stays at 13.7 |
| `contamination` | after hour 48, pH `− 0.02 · (h − 48)` (not below 3.0), turbidity `+ 1 · (h − 48)` | hour 72: pH 3.33 |

These numbers are **made up but plausible**. They are not measured from your
beverage.

### 2.2 The sensors ([smartmet_sim/sensors.py](../smartmet_sim/sensors.py))

A real sensor is never perfect. `SensorArray.read()` turns each true value
into what a sensor would report:

1. **Noise.** `value = true + random.gauss(0, noise_std)`. The noise is a
   normal (bell-curve) random error, for example 0.1 °C for temperature and
   0.02 for pH (the `SENSORS` table).
2. **Faults.** With probability `fault_rate` (for example 0.02 = 2 %) per
   sensor per reading, one of three faults is injected:
   - `spike`: the value jumps by `± spike_size` (temperature ± 8 °C, pH ± 1.0 …)
   - `dropout`: the value becomes `None` (JSON `null`): "no value"
   - `stuck`: the sensor repeats its last good value for **6–12 readings**,
     like a frozen sensor. `_stuck_left` counts the readings left.
3. **Clamp and round.** The value is kept inside the sensor's physical range
   (pH 0–14, …) and rounded to 2 decimals.

Every injected fault is recorded in `faults`, which becomes
`simulation.injected_faults`, the **answer key** that tests use to check
whether the rules caught it.

**Randomness and seeds.** All randomness comes from one `random.Random(seed)`.
The same seed gives the same "random" numbers, so `--seed 7` repeats a run
exactly. That makes bugs reproducible.

### 2.3 Building readings ([smartmet_sim/simulator.py](../smartmet_sim/simulator.py))

`Simulator.reading_at(hours)` does three things: it asks the model for the
truth, asks the sensors what they report, and packs the result into the
data-contract JSON.

- The **timestamp** is `start_time + hours`. This is the **simulated clock**:
  with `--hours-per-reading 1`, every reading is one batch hour later, so a
  5-day batch takes 121 readings (hour 0 to hour 120). That is why simulated
  batches show future dates.
- `readings(count)` produces readings one after another. By default it stops
  at the batch length (120 h).

### 2.4 The command line ([smartmet_sim/cli.py](../smartmet_sim/cli.py))

`python simulator.py ...` runs `main()`, which:

1. reads the options (`parse_args`): `--scenario`, `--interval` (real seconds
   between readings), `--fault-rate`, `--seed`, `--http`, `--device`,
   `--api-key`, `--manual-brix-every` …
2. loops over the readings, waits `--interval` seconds between them, and
   prints each one (`format_reading`)
3. with `--http`, sends each reading with `post_reading()`. This uses Python's
   built-in `urllib`: an HTTP POST with the JSON body and, for devices, the
   `X-API-Key` header. If the server is down, it prints the error and keeps
   going, as a real sensor would.
4. with `--device`, first converts the reading with `as_device_reading()`:
   only temperature and pH, `source: device`, no batch id, no answer key.
   That is exactly what the ESP32 sends.
5. with `--manual-brix-every 8`, also acts like a person: every 8 batch hours
   it sends the Brix value to the **hand-entry** address
   (`type_brix_by_hand`), which runs the same typo check as the dashboard form.

---

## Part 3. The database (`smartmet_db/`)

### 3.1 What PostgreSQL is
PostgreSQL is a database **server**: a program running on your computer (the
Windows service `postgresql-x64-17`) that stores tables and answers questions
written in **SQL**. Our Python code connects to it over the network port
**5432**, even on the same computer.

There are two databases:
- `smartmet4qc`: the real data
- `smartmet4qc_test`: used only by the automated tests, which empty it again and again

### 3.2 How Python finds and connects to the database

1. **`.env`** (in the project folder, secret, not in git) holds the address:
   ```
   DATABASE_URL=postgresql+psycopg://smartmet:PASSWORD@localhost:5432/smartmet4qc
                ─────────┬────────── ───┬─── ───┬──── ────┬──── ─┬── ─────┬─────
                 database + driver     user  password    host  port  database
   ```
2. [smartmet_db/config.py](../smartmet_db/config.py) loads `.env`
   (`load_dotenv`), and `database_url()` returns that address.
3. [smartmet_db/db.py](../smartmet_db/db.py), `get_engine()`, calls
   `create_engine(url)`. The **engine** is SQLAlchemy's connection manager. It
   opens connections to PostgreSQL through the **psycopg** driver and keeps a
   few open for reuse (a "connection pool").
4. `get_sessionmaker()` makes **sessions**. A session is one conversation with
   the database: you read and change things, then `commit()` saves everything
   at once, or nothing is saved if an error happens.

**Who created the user and the databases?** `python -m smartmet_db setup`
(`setup_databases()` in `db.py`). It connects as the PostgreSQL superuser
`postgres`, which needs no password on this computer because `pg_hba.conf`
trusts local connections. Then it:
- creates the login `smartmet` with a random password (`secrets.token_urlsafe`)
- creates both databases, owned by `smartmet`
- writes the addresses into `.env`

From then on, the app only uses `smartmet`, never the superuser.

### 3.3 The tables ([smartmet_db/models.py](../smartmet_db/models.py))

Each Python class is one table. Each `mapped_column` is one column.

```
batches                          readings                               alerts
───────                          ────────                               ──────
id  (PK)  ◀──────────────────┐   id (PK)                                id (PK)
code   "BATCH-001" (unique)  ├── batch_id (FK → batches.id) ◀───────── batch_id (FK → batches.id)
product                      │   measured_at   when measured            rule  "ph_low"
status  active|finished|     │   received_at   when the server got it   measurement  "ph"
        aborted              │   source  simulated|device|manual        severity info|warning|critical
started_at, ended_at, notes  │   device_id (FK → devices.id, or empty)  status open|resolved
created_at                   │   temperature_c, ph, brix,               message, value
                             │   turbidity_ntu, ethanol_percent         opened_at, last_seen_at,
devices                      │     (each may be empty = no value)       resolved_at
───────                      │   simulation  (JSON answer key)
id (PK)                      │
name  "tank-1" (unique)      │
api_key_hash (unique)        │
batch_id (FK) ───────────────┘   which batch the device measures now
last_seen_at
```

- **PK (primary key)** = the row's unique number.
- **FK (foreign key)** = a link to another table's row. `readings.batch_id = 3`
  means "this reading belongs to the batch whose id is 3".
- `ondelete="CASCADE"` = deleting a batch also deletes its readings and alerts.

**Constraints:** rules the database itself enforces, even if the Python code
has a bug:

| Constraint | Rule |
|---|---|
| `reading_unique` | the same batch + time + source + device can only be stored **once**. `NULLS NOT DISTINCT` means two readings with no device still count as the same. |
| `ph_range`, `temperature_range`, … | impossible values are refused (pH must be 0–14, …) |
| `reading_source_valid`, `batch_status_valid`, … | only the allowed words |
| `one_open_alert` | a batch can have only **one open** alert per rule and measurement |

### 3.4 Saving a reading ([smartmet_db/store.py](../smartmet_db/store.py))

`store_readings(session, readings, device_id)`:

1. `parse_reading()` checks each reading again (time zone, known names,
   numbers) and turns it into column values. The API already checked it with
   Pydantic; this second check protects the **import** command, which does not
   go through the API.
2. `get_or_create_batch()` finds the batch by code, or creates it. It uses
   `INSERT … ON CONFLICT DO NOTHING`, so two devices starting the same batch at
   the same moment cannot crash each other.
3. It inserts the reading with this SQL, generated by SQLAlchemy:
   ```sql
   INSERT INTO readings (batch_id, device_id, measured_at, source, temperature_c, ph, ...)
   VALUES (...)
   ON CONFLICT ON CONSTRAINT reading_unique DO NOTHING
   RETURNING id
   ```
   If the reading already exists, PostgreSQL skips it and returns no row. So
   the code knows "inserted" or "duplicate". This is what makes **resending
   safe**.

The read helpers:
- `batch_summaries()`: each batch with its reading count, first and last time
  (SQL `COUNT`, `MIN`, `MAX`, `GROUP BY`)
- `batch_readings(code, limit)`: the newest N readings, returned oldest first
- `latest_values()`: for each measurement, the newest non-empty value
- `first_value()`: the first non-empty value (used for "sugar at the start")

### 3.5 Devices and keys ([smartmet_db/devices.py](../smartmet_db/devices.py))

- `add_device()` makes a key: `"smk_" + secrets.token_urlsafe(32)`, about 43
  random characters.
- Only `hash_key(key)` is stored: **SHA-256**, a one-way scramble. Anyone
  reading the database sees the hash and cannot rebuild the key from it.
- When a device sends its key, `device_for_key()` hashes it again and looks
  for that hash.
- `revoke_key()` empties the hash, so the old key stops working while the
  device's history is kept.

### 3.6 Migrations ([smartmet_db/migrations/](../smartmet_db/migrations/))

When the code needs a table change (Phase 6 added `devices` and
`readings.device_id`), you cannot just delete the database: it contains data.
**Alembic** applies changes as numbered steps:

- `0001_baseline.py`: the tables of phases 2–5
- `0002_devices.py`: adds `devices` and `readings.device_id`, and widens the
  unique rule

PostgreSQL remembers the current step in a small table, `alembic_version`.
`db.migrate()`, run by `python -m smartmet_db migrate` and at every API start:
1. if the tables exist but `alembic_version` does not (a database from before
   migrations existed), marks it as step `0001` ("stamp")
2. runs every missing step up to the newest ("upgrade head")

A test checks that the migrations build **exactly** the tables described in
`models.py`.

### 3.7 Terminal commands ([smartmet_db/__main__.py](../smartmet_db/__main__.py))

`python -m smartmet_db <command>` runs `main()`, which picks a `cmd_…`
function: `setup`, `migrate`, `import`, `summary`, `alerts`, `device …`.

---

## Part 4. The backend API (`smartmet_api/`)

### 4.1 What happens when you start the server
```
python -m uvicorn smartmet_api.main:app --reload
```
- **uvicorn** imports `smartmet_api/main.py` and finds the object `app` (the
  FastAPI application).
- **lifespan()** runs once at startup:
  - it makes the engine
  - `db.migrate()` brings the tables up to date
  - it stores a session maker in `app.state`
- uvicorn then listens on **port 8000**. `--reload` restarts it when you save
  a Python file.

### 4.2 What happens on every request
```
browser / sensor ──HTTP──▶ uvicorn ──▶ FastAPI finds the route (e.g. POST /api/v1/measurements)
                                       ├─ Pydantic checks the JSON body  → 422 + reason if bad
                                       ├─ get_session() opens a database session (a "dependency")
                                       ├─ your function runs
                                       └─ the return value is turned into JSON → response
```
`get_session()` uses `yield`: FastAPI gives the session to the function and
closes it afterwards, even after an error.

### 4.3 Input checking ([smartmet_api/schemas.py](../smartmet_api/schemas.py))

Pydantic classes describe what is allowed:
- `Measurements`:
  - every value is a number or `null`, inside the physical range
    (`Field(ge=0, le=14)` for pH)
  - `extra="forbid"` refuses unknown names
  - `strict=True` refuses `"4.5"` written as text
  - `at_least_one` refuses an empty reading
- `ReadingIn`: the time must have a time zone (`AwareDatetime`), and the
  source must be one of the three words.
- `ManualReadingIn`: hand entries, with `confirm` for the typo check.
- The `…Out` classes describe the answers.

### 4.4 Every endpoint ([smartmet_api/main.py](../smartmet_api/main.py))

| Method and address | Function | Does |
|---|---|---|
| `POST /api/v1/measurements` | `post_measurement` | reading from the simulator or a device (below) |
| `POST /api/v1/manual-readings` | `post_manual_reading` | hand entry with the typo check (Part 5.5) |
| `GET /api/v1/batches` | `list_batches` | every batch + health, latest values, progress |
| `POST /api/v1/batches` | `create_batch` | start a batch |
| `GET /api/v1/batches/{code}` | `get_batch` | one batch: details, health, ethanol estimate, limits |
| `PATCH /api/v1/batches/{code}` | `update_batch` | mark finished, aborted or active |
| `GET /api/v1/batches/{code}/readings` | `get_batch_readings` | the readings, for charts |
| `GET /api/v1/alerts` | `get_alerts` | alerts (`?status=open\|resolved\|all&batch=CODE`) |
| `GET /api/v1/devices` | `get_devices` | devices + online or offline |
| `PATCH /api/v1/devices/{name}` | `update_device` | assign a device to a batch |
| `GET /api/v1/limits` | `qc_limits` | the QC limits, for the dashboard |
| `GET /health` | `health` | "is the server and database alive?" |
| `GET /`, `/batches/…`, `/alerts`, `/devices` | `dashboard_page` | the React app's `index.html` |

**`post_measurement`, step by step:**
1. Pydantic has already checked the body.
2. `device_for_key(api_key)`: if a key was sent but is wrong → **401**.
3. If `source == "device"`:
   - no valid key → **401**
   - `mark_seen()` records "this device is alive now"
   - no `batch_id` in the body → use the device's assigned batch; no assigned
     batch → **409** (the device's "alive" time is still saved)
4. If `source == "simulated"` and `.env` has `ALLOW_SIMULATED=false` → **403**.
5. `store_and_check()`:
   - **saves** the reading (`store_readings`)
   - if it was new, runs the **rules** (`check_batch`)
   - **commits**, so the reading and the alert changes are saved together
   - answers 201 + new alerts (or 200 + `duplicate: true`)

### 4.5 Calculations done in the API

**Batch health** (`batch_health`), checked in this order, first match wins:

| Health | When |
|---|---|
| `closed` | status is finished or aborted |
| `problem` | at least one open **critical** alert |
| `watch` | at least one open **warning** |
| `ready` | an open `batch_finished` alert |
| `no-data` | no readings yet |
| `good` | none of the above |

**Fermentation progress:**
```
progress = (Brix at start − Brix now) / (Brix at start − 9)      clipped to 0…1
```
For example, start 20, now 13.09 → (20 − 13.09) / (20 − 9) = 6.91 / 11 = 0.63
→ **63 %**. It reaches 100 % when Brix is down to 9 (`brix_done`). It is an
estimate for the progress bar, not a measurement.

**Estimated alcohol** (shown when no ethanol is measured):
```
ethanol ≈ (Brix at start − Brix now) × 0.55
```
For example, (20 − 6) × 0.55 = **7.7 %**. It is a rough rule of thumb and must
be confirmed in a lab.

**Online device:** `now − last_seen_at < 5 minutes`.

### 4.6 Serving the dashboard
React is built into plain files in `frontend/dist`. `dashboard_page()` returns
`dist/index.html` for every dashboard address, and `/assets/...` serves the
JavaScript and CSS. If the dashboard is not built, it shows the build
instructions (HTTP 503).

---

## Part 5. Quality control (`smartmet_qc/`)

### 5.1 The idea
After each new reading, ask: **"what is wrong at the time of the latest
reading?"** The answer is a list of **conditions**. Then compare them with
the batch's **open alerts**:

```
condition true,  no open alert   →  OPEN a new alert
condition true,  alert open      →  KEEP it (update value and "last seen")
condition false, alert open      →  RESOLVE it
```
This is `reconcile()` in [smartmet_qc/alerts.py](../smartmet_qc/alerts.py).
Because of it, a problem that lasts 2 days is **one** alert, not 48.

### 5.2 The inputs ([smartmet_qc/rules.py](../smartmet_qc/rules.py))
- `Observation`: one reading (time, source, values).
- `history`: the batch's readings from the **last 30 hours** (`history_hours`),
  oldest first. `service._observations()` reads them from the database.
- `_series(history, "ph")`: the list of (time, value) pairs that have a pH
  value, skipping empty ones. Most rules use this.

### 5.3 The rules, with their calculations

All limits live in [smartmet_qc/config.py](../smartmet_qc/config.py)
(`QCConfig`). They are **placeholders** until real batch data exists.

**A. Limit rules** (`_limit_rules`): the last **2** values (`consecutive`)
must **both** be beyond the limit.

| Rule | Condition | Severity |
|---|---|---|
| `temperature_high` | last 2 temperatures > 30 °C | warning |
| `temperature_low` | last 2 temperatures < 18 °C | warning |
| `ph_low` | last 2 pH values < 3.5 | **critical** |
| `turbidity_high` | last 2 turbidities > 90 NTU | warning |

Why 2? A single spike (for example 34 °C once) cannot raise a false alarm.

**B. Fermentation rules** (`_fermentation_rules`) use the **Brix trend** over
the last 24 h:

1. Take the Brix values of the last 24 h. You need at least 3, covering at
   least 18 h (75 % of 24 h), or the trend means nothing.
2. Calculate the **slope** with **Theil–Sen**: for every pair of points,
   compute (change in value) / (hours between them), then take the
   **median** of all those slopes. Because it's a median, one wrong value
   cannot pull the result much. An ordinary average would be pulled a lot.
   ```
   points (h, Brix): (0, 20), (8, 19), (16, 30 ← typo), (24, 17)
   pair slopes: (0→8) −0.125   (0→16) +0.625   (0→24) −0.125
                (8→16) +1.375  (8→24) −0.125   (16→24) −1.625
   sorted: [−1.625, −0.125, −0.125, −0.125, +0.625, +1.375]
   median = (−0.125 + −0.125) / 2 = −0.125 per hour
   per day = −0.125 × 24 = −3.0 Brix/day   → still clearly falling, the typo did not fool it
   (an ordinary average of the slopes would give +0.0 per hour: "not falling", which is wrong)
   ```
3. `level` = the median of the last 3 Brix values (also robust).
4. Decide:
   - **`fermentation_stuck`** (warning): the batch is at least 36 h old AND
     level > 9 AND it fell less than **1 Brix/day**.
   - **`batch_finished`** (info): level ≤ 9 AND it changed less than
     **0.3 Brix/day**.

**C. Sensor rules** (`_sensor_rules`) are checked **per source**: a broken
device sensor is a different thing from a typing error.

- **`sensor_missing`**: the source's latest reading has an empty value for a
  measurement that the same source **did** send earlier. This is not checked
  for `manual`, where partial entries are normal.
- **`sensor_spike`**: compare the newest value with the **median of the 3
  values before it**:
  ```
  allowed change = spike_base + spike_rate_per_hour × (hours since the middle one of those 3)
  spike if |new value − median| > allowed change
  ```
  For example, temperature with values 26.0, 26.1, 25.9 one hour apart, then
  34.0:
  - median = 26.0
  - allowed = 2.0 + 0.2 × 2 h = 2.4
  - |34.0 − 26.0| = 8.0 > 2.4 → **spike**

  The time allowance matters for sparse values: Brix typed by hand every 8 h
  may genuinely change several units between entries.
- **`sensor_stuck`**: the last **6** values from that source are **exactly
  identical**. Real sensors always jitter a little, so 6 identical values
  means a frozen sensor. This is not checked for `manual`.

### 5.4 Running the rules on the database ([smartmet_qc/service.py](../smartmet_qc/service.py))

`check_batch(session, code)`, called by the API after each new reading:
1. **Locks the batch row** (`with_for_update`). If two readings for the same
   batch arrive at once, the second waits, so the same alert cannot be opened
   twice.
2. Finds the latest reading time and loads the last 30 h of readings.
3. `evaluate()` → conditions.
4. `reconcile()` with the open alerts in the `alerts` table → creates,
   updates or resolves rows. Alert times use the **reading time** (the batch
   clock), not the server's clock.

`rebuild_batch_alerts()` deletes a batch's alerts and **replays** all its
readings one by one (`alerts.replay()`), exactly as if they arrived live.
The import command uses it.

### 5.5 The typo check for hand entries ([smartmet_qc/plausibility.py](../smartmet_qc/plausibility.py))

Before a hand-typed value is stored, it is compared with the batch's
**previous value** of that measurement, from any source:

| Check | Warning when |
|---|---|
| Brix rises | new − previous > **1.0**: sugar only falls during fermentation |
| Ethanol falls | previous − new > **1.0**: alcohol only rises |
| Anything changes too fast | \|new − previous\| > `spike_base + spike_rate_per_hour × hours between` |

For example, Brix 13.0 entered, then 31.0 eight hours later: a rise of 18 >
1.0 → warning. The API answers **409** with the warning text, and nothing is
stored. The form shows the warning; if the person confirms, the form resends
with `confirm: true` and the value is stored.

**Known gap:** the **first** value of a batch has nothing to compare with, so
it is not checked. For example, pH 10 entered first is accepted.

### 5.6 The sensor test ([smartmet_qc/evaluate.py](../smartmet_qc/evaluate.py))

This answers **"which sensors does the MVP need?"** For each sensor set, for
example "temperature + pH automatic, Brix by hand every 8 h", it:
1. simulates 20 batches per scenario, with 2 % sensor faults
2. removes the sensors the set does not have (`to_observations`)
3. replays them through the real rules
4. counts:
   - was the expected problem caught, and at what hour?
   - were there false alarms on normal batches?
   - how many injected faults were flagged?

The result: temperature + pH + hand-typed Brix catch everything; remove any
one of them and a problem goes unseen. See
[sensor_test_results.md](sensor_test_results.md).

---

## Part 6. The dashboard (`frontend/`)

### 6.1 How React code reaches the browser
- You write **TypeScript + React** in `frontend/src`.
- `npm run build` runs:
  - `tsc`, which checks the types and catches mistakes
  - **Vite**, which bundles everything into `frontend/dist`: one HTML file, one
    JavaScript file and one CSS file
- The Python server sends those files to the browser (Part 4.6). From then
  on, the page runs **in the browser** and only asks the API for JSON.
- While developing, `npm run dev` serves the code live on port 5173 and
  forwards `/api` calls to port 8000 (`vite.config.ts`, `proxy`).

### 6.2 Startup ([src/main.tsx](../frontend/src/main.tsx))
- `QueryClient` with `refetchInterval: 10_000` makes **every data request
  repeat every 10 seconds**. That is why the dashboard is "live".
- `BrowserRouter` lets the address bar (`/batches/BATCH-001`) choose the page
  without reloading.

### 6.3 Pages and layout ([src/App.tsx](../frontend/src/App.tsx), [src/components/Layout.tsx](../frontend/src/components/Layout.tsx))
```
<Layout>                       sidebar + page area (Outlet)
  /                → Overview
  /batches/:code   → BatchPage
  /alerts          → AlertsPage
  /devices         → DevicesPage
```

### 6.4 Getting data ([src/lib/api.ts](../frontend/src/lib/api.ts), [src/lib/queries.ts](../frontend/src/lib/queries.ts))
- `api.ts` has one function per endpoint, for example
  `api.batches()` → `fetch('/api/v1/batches')`. It also has TypeScript types
  matching the server's JSON shapes. Errors become an `ApiError` with the
  server's reason.
- `queries.ts` wraps them in hooks such as `useBatches()`. A component writes
  `const batches = useBatches()` and gets `batches.data`, `isLoading` and
  `isError`, refreshed every 10 s. Two components using the same hook share
  one request, which TanStack Query caches.
- Changing data uses `useMutation`, for example `api.createBatch`. Afterwards
  `invalidateQueries()` makes everything reload at once.

### 6.5 Texts and calculations in the browser
- [src/lib/meta.ts](../frontend/src/lib/meta.ts):
  - the **plain-language texts**: names, units and normal ranges of each
    measurement; health labels; every rule's title, explanation and **"What
    to do"**
  - `outOfRange()` decides "too high" or "too low" using the limits from
    `/api/v1/limits`
- [src/lib/format.ts](../frontend/src/lib/format.ts):
  - `formatAgo()`: "5 min ago"
  - `dayNumber()`: day of fermentation = floor((time − start) / 24 h) + 1
  - `trend()`: the change over the last 6 h = median(last 3 values) −
    median(3 values around 6 h earlier). Below the measurement's noise level
    (`noise` in meta.ts, for example 0.3 °C), it shows "Steady".

### 6.6 The main components

| Component | Shows |
|---|---|
| `BatchCard` | the overview card: health, day, progress bar, 3 latest values, main problem |
| `MeasurementChart` | one chart: blue sensor line, orange hand-typed dots, green **normal-range band** (`ReferenceArea`), Brix "nearly done" line, hover tooltip |
| `ManualEntry` | the hand-entry form; on **409** shows the warnings with "save it" / "let me correct it" |
| `BatchDevices` | the devices on this batch, and "Measure this batch" |
| `AlertItem` | one alert with its explanation and what to do |
| `ui.tsx` | small shared pieces: `Card`, `Chip` (icon + word + colour), `Button`, `ProgressBar` |

Colours come from CSS variables in [src/index.css](../frontend/src/index.css),
with light and dark values. A status is always **icon + word + colour**, so
colour-blind users can read it too.

---

## Part 7. The ESP32 firmware (`firmware/`)

[firmware/smartmet_esp32/smartmet_esp32.ino](../firmware/smartmet_esp32/smartmet_esp32.ino)
runs on the sensor box. Arduino programs have two functions: `setup()` runs
once, and `loop()` repeats forever.

**`setup()`:** starts the temperature sensor, loads the pH calibration from
the board's memory (`Preferences`), connects to Wi-Fi, and asks the internet
for the time (`configTime`, NTP).

**`loop()`, every 60 s:**
1. If the clock is not set yet, wait. A reading without the real time cannot
   be placed on the batch timeline.
2. `measure()`:
   - **temperature**: the DS18B20 gives °C directly. −127 means unplugged and
     85 means "not ready"; both are treated as "no value".
   - **pH**:
     - 30 voltage readings (`analogReadMilliVolts`), sorted, the middle one
       taken (the **median**), to ignore electrical noise
     - then converted with the calibration (below)
3. `addToBuffer()`: put it in a queue of up to 120 readings (2 h).
4. `flushBuffer()`: send the oldest first.
   - success (200/201) → remove it
   - wrong key (401) or no batch (409) → drop it and print why
   - network error or server error → keep it and try again next minute

**pH from voltage (two-point calibration with temperature compensation):**
```
during calibration: probe in pH 7 buffer → mv7 (e.g. 1500 mV)
                    probe in pH 4 buffer → mv4 (e.g. 2030 mV), at temperature Tcal (e.g. 25 °C)

slope at calibration = (mv4 − mv7) / (4 − 7) = (2030 − 1500) / −3 = −176.7 mV per pH unit
slope now            = slope at calibration × (T + 273.15) / (Tcal + 273.15)   ← probes react more when warmer
pH                   = 7 + (mV now − mv7) / slope now
```
For example, 1765 mV at 25 °C → pH = 7 + (1765 − 1500) / −176.7 = 7 − 1.50 =
**5.50**.

The firmware does **not send pH until it is calibrated**.

---

## Part 8. Follow one reading through everything

A device sends temperature 31.2 °C and pH 4.10 for batch BATCH-007, and the
previous reading was 30.6 °C.

```
1. ESP32 measures                     temp 31.2, pH 4.10 (median of 30 samples, calibrated)
2. ESP32 sends                        POST /api/v1/measurements
                                      header  X-API-Key: smk_…
                                      body    {"timestamp":"2026-10-12T08:00:00Z","source":"device",
                                               "measurements":{"temperature_c":31.2,"ph":4.10}}
3. uvicorn → FastAPI                  route post_measurement
4. Pydantic (schemas.ReadingIn)       time has zone ✓, source valid ✓, numbers in range ✓
5. device_for_key                     SHA-256(key) found → device "tank-1" ✓
6. mark_seen                          devices.last_seen_at = now      (dashboard: "online")
7. batch from assignment              tank-1 measures BATCH-007 → batch_id = "BATCH-007"
8. store_readings                     INSERT INTO readings … ON CONFLICT DO NOTHING RETURNING id → new ✓
9. check_batch                        lock batch, load last 30 h, evaluate():
                                        _limit_rules: last 2 temps 30.6 and 31.2 both > 30 → temperature_high
10. reconcile                         no open temperature_high alert → OPEN one (warning)
11. commit                            reading + alert saved together
12. response 201                      {"stored":true,"new_alerts":[{"rule":"temperature_high",…}]}
13. dashboard, within 10 s            useBatches() refetches GET /api/v1/batches:
                                        open warning → health "watch"
                                      Overview: yellow "Watch" card, "Batch is too warm"
                                      Batch page: temperature tile "Too high", the line above the green band,
                                        "What to do: Check the cooling…"
14. later readings below 30 °C        condition gone → reconcile RESOLVES the alert → it moves to the history
```

**The same for a hand-typed Brix:**
`ManualEntry` form → `POST /api/v1/manual-readings` → `check_manual_values`
(typo check) → `store_and_check` (`source: manual`) → the rules → an orange
dot on the Brix chart.

---

## Part 9. Every calculation in one place

| What | Formula | File |
|---|---|---|
| fermentation S-curve | `L = 1/(1+e^(−0.12(h−36)))`, progress = `(L−L(0))/(1−L(0))` | sim `model.py` |
| yeast activity | `4·L·(1−L)` | sim `model.py` |
| simulated Brix | `20 − 14·progress` | sim `model.py` |
| simulated ethanol | `(20 − Brix)·0.55` | sim `model.py` |
| simulated pH | `4.6 − 0.8·progress` | sim `model.py` |
| simulated temperature | `26 + 2·activity` | sim `model.py` |
| simulated turbidity | `15 + 60·activity` | sim `model.py` |
| sensor noise | `value + gauss(0, noise_std)` | sim `sensors.py` |
| limit alert | last 2 values beyond the limit | qc `rules.py` |
| Brix trend | Theil–Sen: median of all pairwise slopes × 24 | qc `rules.py` |
| stuck | age ≥ 36 h, level > 9, drop < 1/day | qc `rules.py` |
| finished | level ≤ 9, change < 0.3/day | qc `rules.py` |
| spike | `|v − median(prev 3)| > base + rate·hours` | qc `rules.py` |
| frozen | 6 identical values | qc `rules.py` |
| typo check | Brix rise > 1, ethanol drop > 1, or the spike formula | qc `plausibility.py` |
| health | closed › problem › watch › ready › no-data › good | api `main.py` |
| progress | `(Brix start − now)/(Brix start − 9)`, 0…1 | api `main.py` |
| estimated alcohol | `(Brix start − now)·0.55` | api `main.py` |
| online | last contact < 5 min | api `main.py` |
| day of fermentation | `floor((t − start)/24 h) + 1` | frontend `format.ts` |
| 6-hour trend | `median(last 3) − median(3 around 6 h earlier)` | frontend `format.ts` |
| pH from voltage | `7 + (mV − mv7)/slope`, slope temperature-compensated | firmware `.ino` |

---

## Part 10. The tests (`tests/`)

Run them all with `python -m unittest discover -s tests -v`.

| File | Proves |
|---|---|
| `test_simulator.py` | the curves are right (Brix only falls, ethanol only rises), each scenario changes what it should, faults happen, same seed = same data |
| `test_qc.py` | each rule fires when it should and stays quiet when it should; alerts open and resolve; Theil–Sen ignores outliers; the typo check; the MVP sensor set catches everything |
| `test_database.py` | saving and reading, no duplicates, `null` stored as empty, impossible values refused; migrations build exactly the model |
| `test_api.py` | the endpoints, the 422 reasons, resending is safe, alerts through the API |
| `test_dashboard.py` | batches, status changes, hand entry and its typo check, health and progress, the dashboard pages |
| `test_devices.py` | keys (401), batch assignment (409), two devices on one batch, revoked keys, the emulator's shape |

The database tests use `smartmet4qc_test`, so your real data is never touched.
`tests/api_setup.py` starts one API for all API tests and empties the test
database before each test.

---

## Part 11. Check your understanding

Try to answer each question, then check the part in brackets.

1. Why does a device not send a `batch_id`, and how does the server know the
   batch? (4.4)
2. What happens if the same reading is sent twice? Which line of SQL makes it
   safe? (3.4)
3. Why do limit rules need **2** readings beyond the limit? (5.3 A)
4. Calculate the spike threshold for pH when the 3 previous values are 1 h
   apart. (5.3 C: 0.3 + 0.03 × 2 = 0.36)
5. Why is Theil–Sen used for the Brix trend instead of "last value minus
   first value"? (5.3 B)
6. A problem lasts 2 days. How many alerts does it create, and why? (5.1)
7. Where is the database password stored, who created it, and why is it not
   in git? (3.2)
8. What does `refetchInterval: 10_000` do, and where is it set? (6.2)
9. Brix started at 20 and is now 12. What progress and estimated alcohol does
   the dashboard show? (4.5: 8/11 = 73 %, 8 × 0.55 = 4.4 %)
10. Why does the simulator show dates in the future? (2.3)
11. Why is the first hand-typed value of a batch not checked for typos? (5.5)
12. What does `migrate` do with a database from before migrations existed? (3.6)
13. Why does the ESP32 keep readings in a buffer, and when does it drop one? (7)
14. Which file would you change to make the temperature limit 28 °C? (5.3:
    `smartmet_qc/config.py`, `temp_max_c`)

---

## Glossary

| Word | Meaning |
|---|---|
| **API** | the set of addresses (endpoints) other programs use to talk to the server |
| **endpoint** | one address + method, for example `POST /api/v1/measurements` |
| **HTTP status** | the answer's code: 200 OK, 201 created, 401 not allowed, 404 not found, 409 conflict, 422 invalid data, 503 not available |
| **JSON** | the text format for data: `{"name": value}` |
| **batch** | one production run (one tank load), from start to finish |
| **Brix (°Bx)** | sugar content; falls during fermentation |
| **pH** | acidity; lower = more acidic |
| **NTU** | unit of turbidity (cloudiness) |
| **SQL** | the language for asking a database questions |
| **primary / foreign key** | a row's id / a link to another table's row |
| **constraint** | a rule the database enforces itself |
| **migration** | a numbered step that changes the tables safely |
| **engine / session** | SQLAlchemy's connection manager / one conversation with the database |
| **commit** | save all changes of a session at once |
| **Pydantic model** | a Python class describing allowed JSON |
| **hash (SHA-256)** | a one-way scramble; used so device keys are never stored in readable form |
| **median** | the middle value after sorting; not pulled by one extreme value |
| **Theil–Sen** | a slope that is the median of all pairwise slopes; robust to bad points |
| **component** (React) | a reusable piece of the page, written as a function |
| **hook** (React) | a function starting with `use…` that gives a component data or state |
| **build** | turning the React source code into files the browser runs |
| **firmware** | the program running on the ESP32 |
| **calibration** | measuring known references (pH 7 and pH 4 buffers) to convert voltage to pH correctly |
| **NTP** | the internet time service the ESP32 uses to set its clock |
