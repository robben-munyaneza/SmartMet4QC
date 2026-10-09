# Sensor test results

20 simulated batches per scenario, sensor fault rate 2%. Cell = batches where the problem was caught, and the median hour it was caught.
Problems start at: overheat h24, contamination h48, stuck from the start (visible after h36).

| Sensor set | Overheat | Stuck | Contamination | Finished (normal) | False alarms (normal) | Verdict |
|---|---|---|---|---|---|---|
| All 5 sensors, hourly | 20/20 (h39) | 20/20 (h73) | 20/20 (h66) | 20/20 (h91) | 0/20 | **PASS** |
| MVP: T + pH hourly, Brix by hand /8 h | 20/20 (h39) | 20/20 (h73) | 20/20 (h66) | 20/20 (h96) | 0/20 | **PASS** |
| T + pH + Brix hourly | 20/20 (h39) | 20/20 (h73) | 20/20 (h66) | 20/20 (h91) | 0/20 | **PASS** |
| MVP without pH | 20/20 (h39) | 20/20 (h73) | 0/20 | 20/20 (h96) | 0/20 | **FAIL** |
| MVP without temperature | 0/20 | 20/20 (h73) | 20/20 (h66) | 20/20 (h96) | 0/20 | **FAIL** |
| MVP without Brix | 20/20 (h39) | 0/20 | 20/20 (h66) | 0/20 | 0/20 | **FAIL** |
| MVP, turbidity instead of pH | 20/20 (h39) | 20/20 (h73) | 0/20 | 20/20 (h96) | 0/20 | **FAIL** |

## Sensor faults flagged

| Sensor set | Spikes | Missing values | Frozen sensors | False sensor alerts per batch |
|---|---|---|---|---|
| All 5 sensors, hourly | 267/296 | 376/380 | 300/320 | 0.04 |
| MVP: T + pH hourly, Brix by hand /8 h | 100/116 | 144/144 | 128/140 | 0.00 |
| T + pH + Brix hourly | 164/172 | 228/232 | 184/196 | 0.04 |
| MVP without pH | 40/52 | 68/68 | 52/60 | 0.00 |
| MVP without temperature | 60/76 | 76/76 | 76/80 | 0.00 |
| MVP without Brix | 100/104 | 144/144 | 128/140 | 0.00 |
| MVP, turbidity instead of pH | 80/104 | 148/148 | 100/116 | 0.00 |

Why some faults are not flagged:
- Spikes that push a value below 0 are clipped to 0 and look like real values (turbidity, ethanol).
- Spikes in Brix typed by hand every 8 h: real Brix can change several units between entries,
  so a typo cannot be told apart from fast fermentation. The entry form must check typos instead.
- A frozen sensor needs 6 identical values; one that freezes in the last hours of a batch is not
  flagged before the batch ends.
- A missing value in the very first reading: there is no earlier value to say the sensor worked.
