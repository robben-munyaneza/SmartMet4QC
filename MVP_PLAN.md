# SmartMet4QC — MVP Plan

This plan answers three questions before we build more:

1. How does the whole system work, from sensor to dashboard?
2. How does the simulator work, and how do we prove it is good enough to build on?
3. Which sensors does the MVP really need, and how do we test that?

[PLAN.md](PLAN.md) has the layer overview and the Layer 1 details.

---

## 1. What the MVP must do

**MVP goal:** one production batch is monitored from start to finish. The
system shows its measurements over time and warns the operator when something
goes wrong, early enough to act.

The MVP is finished when:

| # | The system can... | Proven by |
|---|---|---|
| 1 | Receive readings every few minutes for a batch | Simulator → API test |
| 2 | Store the full history of each batch | Database test |
| 3 | Show live values and charts per batch | Dashboard check |
| 4 | Raise an alert for overheating | `overheat` scenario |
| 5 | Raise an alert for stuck fermentation | `stuck` scenario |
| 6 | Raise an alert for contamination/souring | `contamination` scenario |
| 7 | Say when a batch looks finished (sugar stable) | `normal` scenario |
| 8 | Notice when a sensor is broken (missing, frozen, jumping) | `--fault-rate` runs |
| 9 | Raise **no** false alerts on a healthy batch | `normal` scenario, many seeds |
| 10 | Accept the same data from a real ESP32 | Hardware test (section 6) |

**Not in the MVP:** user accounts and roles, several factories, mobile app,
machine learning, automatic control of heaters/coolers, legal compliance
reports.

---

## 2. How the whole system works

```
 ┌──────────────┐    reading (JSON)    ┌──────────────┐    save    ┌────────────┐
 │  Simulator   │ ───────────────────▶ │  Backend API │ ─────────▶ │  Database  │
 │  (now)       │  POST /measurements  │  (FastAPI)   │            │  (SQLite)  │
 ├──────────────┤                      │              │            └─────┬──────┘
 │  ESP32 +     │ ───────────────────▶ │  - validate  │                  │
 │  sensors     │   same JSON shape    │  - QC rules  │ ──alerts──┐      │ history
 │  (later)     │                      └──────────────┘           ▼      ▼
 ├──────────────┤                                            ┌──────────────┐
 │ Manual entry │ ──── lab / hand-held readings ───────────▶ │  Dashboard   │
 │ (form)       │                                            │  charts +    │
 └──────────────┘                                            │  alerts      │
                                                             └──────────────┘
```

Life of one reading:

1. **Measure.** The simulator, an ESP32 or a person produces a reading:
   time, batch, source, and the measured values.
2. **Send.** It is sent as JSON to `POST /api/v1/measurements`.
3. **Validate.** The API rejects malformed data: wrong types, unknown batch,
   values outside what the sensor can physically report.
4. **Check quality.** QC rules compare the reading with the limits and with
   recent history. An alert is created if a rule fails.
5. **Store.** The reading and any alerts are saved.
6. **Show.** The dashboard shows the latest values, charts and open alerts.

The key idea is that **the source does not matter**. The simulator, the ESP32
and manual entry all send the same JSON shape, so everything after step 2 is
built and tested once, with the simulator, and keeps working when real
sensors arrive.

---

## 3. How the simulator works

```
 BatchProfile ──▶ FermentationModel ──▶ SensorArray ──▶ reading JSON
 (start/end       (true value at        (+ noise,        (data contract,
  values, speed)   hour h, scenario)     + faults)        + answer key)
```

1. **Model (truth).** For each simulated hour it calculates what a perfect
   sensor would read:
   - Sugar (Brix) falls along an S-curve: slow start, fast middle, slow end.
   - Ethanol rises as sugar is used up.
   - pH slowly falls.
   - Temperature stays near the set point and warms a little during peak
     activity.
   - Turbidity rises while yeast is active, then settles.
2. **Scenario.** Changes the truth to copy a real problem: `overheat`,
   `stuck`, `contamination` or `normal`.
3. **Sensors.** Add small random errors. Optionally inject faults: `spike`
   (a sudden wrong value), `dropout` (no value) or `stuck` (the same value
   repeated).
4. **Answer key.** Every reading carries `simulation.scenario` and
   `simulation.injected_faults`, so a test knows what the QC system *should*
   have found.

**Limits of the simulator.** The simulator follows *our assumptions* about
fermentation. It proves that **the software** reacts correctly to these
patterns. It cannot prove that real banana beer behaves this way, or that a
real sensor is accurate. Section 7 covers that.

---

## 4. Which sensors does the MVP really need?

Start with the problems we must catch, then ask which measurement shows each
one.

### Problem → measurement matrix

| Problem to catch | Temp | pH | Brix / gravity | Turbidity | Ethanol |
|---|:-:|:-:|:-:|:-:|:-:|
| Overheating / cooling failure | **main** | | | | |
| Too cold, so fermentation is too slow | **main** | | supports | | |
| Stuck fermentation | | | **main** (sugar stops falling) | | supports |
| Contamination / souring | | **main** | | supports | |
| Batch finished / ready | | | **main** (stable for 24–48 h) | supports | supports |
| Alcohol content of the product | | | estimate | | **main** |
| Appearance / clarity | | | | **main** | |

### Can each sensor be done cheaply and reliably with an ESP32?

| Measurement | Realistic MVP option | Reliability | Verdict |
|---|---|---|---|
| Temperature | Waterproof DS18B20 probe | High, cheap, easy | **Must have, automatic** |
| pH | Analog pH probe + board (e.g. DFRobot Gravity) | Medium: must be calibrated with buffer solutions; drifts | **Must have, automatic** (with a calibration routine) |
| Brix / gravity | Hand-held refractometer or hydrometer typed into a form; later a floating tilt hydrometer (iSpindel-style) | Manual: good. Note: alcohol distorts refractometer readings during fermentation, so gravity is better | **Must have; manual entry in the MVP** |
| Ethanol | Calculated from the gravity drop: `ABV ≈ (OG − SG) × 131.25`. Cheap MQ-3 gas sensors do **not** give a reliable % ABV | Estimate only; confirm in a lab at the end | **Calculated, not a sensor** |
| Turbidity | Analog turbidity sensor (e.g. DFRobot SEN0189) | Low–medium: made for water; dirties quickly in fermenting liquid | **Optional, after the MVP** |

### Recommendation

**MVP sensors = temperature + pH (automatic) + Brix/gravity (manual entry),
with ethanol calculated from the sugar drop.** Turbidity comes after the MVP.

This covers every problem in the matrix except clarity and the exact final
alcohol content, which a lab or hand-held check at bottling handles better
anyway. It also cuts out the two hardest and least reliable sensors.

This is a recommendation for you to decide on. The simulator test in
section 5 will check it with numbers instead of opinion.

**Update (Phase 4): the sensor test confirms this set.** It caught every
problem in 20/20 batches with no false alarms. Removing pH, temperature or
Brix each makes one problem undetectable. See
[docs/sensor_test_results.md](docs/sensor_test_results.md); rerun it with
`python -m smartmet_qc.evaluate`.

---

## 5. How we test the simulator and the sensor choice

### Level A — Unit tests (done, 11 tests)
`python -m unittest discover -s tests -v`
- Sugar never rises and ethanol never falls in a normal batch.
- Each scenario changes the value it should change.
- Faults appear when asked for, and values stay inside each sensor's range.
- The same seed gives the same results.
- Every reading has the agreed JSON shape.

### Level B — Visual check (next, small)
Plot one batch per scenario as a chart. A person who knows the process (you,
or the person who makes the beverage) looks at the curves and says "yes, this
looks like a real batch" or "no, pH falls too fast". Any corrections go into
`BatchProfile`.

### Level C — Sensor test, run with a simple version of the QC rules (next, key step)
This is how we **prove which sensors the MVP needs**:

1. Write a few simple detection rules, for example:
   - temperature above a limit for 2 readings in a row,
   - sugar not falling for 24 h while still above the expected end value,
   - pH below a limit.
2. For each scenario, run 20 batches with different seeds and a small fault
   rate.
3. Run the same batches again with sensors **turned off** (temperature + pH +
   Brix only, then each one removed in turn).
4. Count the results:

| Sensor set | overheat caught | stuck caught | contamination caught | false alerts on normal |
|---|---|---|---|---|
| all 5 | ? | ? | ? | ? |
| temp + pH + Brix | ? | ? | ? | ? |
| without pH | ? | ? | ? | ? |
| ... | | | | |

**Pass rule:** if "temp + pH + Brix" catches every problem in at least 95% of
runs with no extra false alerts, that sensor set is enough for the MVP. If
not, the table shows which sensor we are missing.

This also checks the faulty-sensor rules: every `injected_faults` entry should
be flagged, using the answer key.

### Level D — End-to-end test (after Layers 2–5)
Run the simulator against the real backend:
`python simulator.py --http ... --scenario overheat --interval 0`.
Then check that the readings are in the database, the alert exists, and the
dashboard shows it.

---

## 6. Moving from simulator to real hardware

1. **Bench test.** Connect the ESP32 with temperature + pH sensors and let it
   send to the same API. Compare its readings with a reference thermometer and
   with pH buffer solutions (4.0 and 7.0). Write down the error.
2. **Side by side.** Put the sensors in a real batch. Measure Brix, pH and
   temperature by hand 2–3 times a day and type them in as `source: manual`.
   The dashboard shows both, so you can compare.
3. **Calibrate the simulator.** Use the real batch data to correct
   `BatchProfile` (start/end sugar, speed, pH range). From then on the
   simulator copies *your* process, and new rules can be tested on it safely.

## 7. What must come from reality, not the simulator

- **Quality limits.** For example, the pH or temperature range that is
  acceptable. These must come from your process knowledge, lab tests, and any
  national standard for this beverage. The simulator numbers are placeholders.
- **Sensor accuracy and calibration interval.**
- **Food safety.** Probes in contact with the beverage must be food-safe and
  cleanable.

---

## 8. Roadmap with checkpoints

| Step | What | Checkpoint (must pass before the next step) |
|---|---|---|
| 1 ✅ | Simulator | Unit tests pass, scenarios behave as designed |
| 1.1 | Visual check + sensor test (section 5 B, C) | You approve the curves; the table confirms the MVP sensor set |
| 1.2 | Data contract update | Allows `source: manual`, optional measurements, calculated ethanol |
| 2 | Backend API | Simulator posts readings; bad data is rejected |
| 3 | Database | Full batch history is stored and can be read back |
| 4 | QC rules + alerts | Same pass rate as step 1.1, now inside the backend |
| 5 | Dashboard + manual-entry form | MVP checklist (section 1) items 1–9 pass |
| 6 | ESP32 (temp + pH) | Bench test and side-by-side batch; MVP item 10 passes |

## 9. Questions to answer before step 1.1

1. What is the process? Which steps are there (juice extraction, any added
   grain or sugar, fermentation, filtering, bottling)? How many days does
   fermentation take, and at what temperature?
2. What do you measure today, and with what tools?
3. Batch size and vessel type (bucket, tank, open/closed)?
4. Are there any official quality limits you must meet (national standard,
   buyer requirements)?
5. Rough hardware budget?
