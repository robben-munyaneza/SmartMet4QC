# SmartMet4QC

Quality-control monitoring for a banana-based alcoholic beverage.
See [PLAN.md](PLAN.md) for the full layered plan.

**Current status: Phases 1–4 are done: simulator, PostgreSQL database,
backend API, and QC rules + alerts.**
See the phase table in [PLAN.md](PLAN.md).

## One-time setup (Windows)

This computer has two Pythons. Plain `python` is the MSYS2 one, which cannot
install the PostgreSQL driver. So the project uses a virtual environment made
with the official Python (`py`):

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\activate
```

After `activate`, `python` means the project's Python in that terminal. In VS
Code, use **Python: Select Interpreter** and choose `.venv` so new terminals
activate it automatically.

## Database (PostgreSQL)

```
python -m smartmet_db setup      # once: creates role "smartmet", databases, tables, .env
python -m smartmet_db import data\batch-001.jsonl
python -m smartmet_db summary
```

- No PostgreSQL password is needed. The local server trusts connections from
  this computer. `setup` creates an app login `smartmet` with a random
  password and saves it in `.env`. That file is git-ignored and must not be
  shared.
- `setup` is safe to run again.
- Importing the same file twice does not create duplicate readings.
- To look at the data yourself:
  `"C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -U smartmet -d smartmet4qc`
  (or connect pgAdmin to `localhost`, user `smartmet`).

Full example: simulate a contaminated batch and store it:

```
python simulator.py --batch-id BATCH-002 --scenario contamination --fault-rate 0.03 --interval 0 --jsonl data\batch-002.jsonl
python -m smartmet_db import data\batch-002.jsonl
```

## Run the simulator

Open this folder in VS Code, open **Terminal → New Terminal**, then run:

```
python simulator.py
```

You get one reading every 5 seconds. Each reading is one simulated hour of a
5-day (120-hour) fermentation batch. Press **Ctrl+C** to stop.

```
2026-10-09 10:00  h=   0.0  T=26.07C  pH=4.61  Brix=20.03  Turb=16.95NTU  EtOH=0.00%
2026-10-09 11:00  h=   1.0  T=26.13C  pH=4.58  Brix=19.93  Turb=17.82NTU  EtOH=0.05%
```

### Useful options

| Command | What it does |
|---|---|
| `python simulator.py --interval 0` | Run the whole batch instantly |
| `python simulator.py --scenario overheat` | Temperature control fails after 24 h |
| `python simulator.py --scenario stuck` | Fermentation stops halfway |
| `python simulator.py --scenario contamination` | pH drops and turbidity rises after 48 h |
| `python simulator.py --fault-rate 0.05` | 5% of sensor readings have a spike, dropout or stuck fault |
| `python simulator.py --seed 7` | Same numbers every time you use seed 7 |
| `python simulator.py --json` | Print the raw JSON that will be sent to the backend |
| `python simulator.py --jsonl data/batch1.jsonl` | Also save every reading to a file |
| `python simulator.py --help` | Show all options |

Options can be combined, for example:

```
python simulator.py --batch-id BATCH-002 --scenario contamination --fault-rate 0.03 --interval 0 --jsonl data/batch2.jsonl
```

## Backend API

Terminal 1 starts the API. Leave it running.

```
python -m uvicorn smartmet_api.main:app --reload
```

Terminal 2 sends a simulated batch to it:

```
python simulator.py --batch-id BATCH-010 --scenario overheat --http
```

`--http` sends each reading to `http://127.0.0.1:8000/api/v1/measurements`.
To send to another address, give it after the flag, e.g. `--http http://host:8000/api/v1/measurements`.

See the results:

- http://127.0.0.1:8000/docs: interactive API page. You can send a test
  reading from there with **Try it out**.
- http://127.0.0.1:8000/api/v1/batches: all batches
- http://127.0.0.1:8000/api/v1/batches/BATCH-010/readings?limit=10: latest readings

Note: each simulator run starts its clock at "now". Running the same
`--batch-id` again therefore adds a second set of readings to that batch.
Use a new batch id for each run.

## QC alerts

Each reading that reaches the API is checked against the rules listed in
[PLAN.md](PLAN.md) (Phase 4): too hot/cold, pH too low, stuck fermentation,
batch finished, and sensor faults. With `--http`, the simulator prints each
alert as soon as the backend opens it:

```
  ALERT [critical] ph_low: pH below 3.5: possible souring or contamination
```

- http://127.0.0.1:8000/api/v1/alerts: open alerts
  (`?status=all` includes resolved ones, `&batch=BATCH-004` shows one batch)
- `python -m smartmet_db alerts`: open alerts in the terminal
  (`--all` includes resolved ones, `--rebuild` recomputes them from the readings)
- Importing a `.jsonl` file rebuilds the alerts of the imported batches.

### Sensor test (which sensors does the MVP need?)

```
python -m smartmet_qc.evaluate --out docs\sensor_test_results.md
```

This runs 20 simulated batches per scenario through the rules for several
sensor sets and shows what each set catches. The current results are in
[docs/sensor_test_results.md](docs/sensor_test_results.md).

## Run the tests

```
python -m unittest discover -s tests -v
```

The database tests use the separate `smartmet4qc_test` database, so they
never touch your real data.

## Important

The simulated values are made up but look plausible. They test the software
workflow only. They are not real measurements of the beverage, validated
quality limits or proof of product safety.
