# SmartMet4QC — Hardware guide (Phase 6)

This guide covers building the MVP measuring device: temperature and pH on an
ESP32. Brix is still typed in by hand on the dashboard (see
[MVP_PLAN.md](../MVP_PLAN.md)).

> **Check before buying.** The parts below are common, inexpensive choices.
> If you buy different ones, the firmware settings in `config.h` usually cover
> it. The one exception is a pH board whose output goes above 3.3 V (see the
> warning below).

## 1. Parts

| Qty | Part | Notes |
|---|---|---|
| 1 | ESP32 DevKit board (ESP32-WROOM-32, "ESP32 Dev Module") | With a USB cable that carries data, not only power |
| 1 | DS18B20 waterproof temperature probe (stainless steel, 1 m cable) | Three wires: red = VCC, black = GND, yellow (or white) = data |
| 1 | 4.7 kΩ resistor | Pull-up for the DS18B20 data line |
| 1 | DFRobot Gravity analog pH sensor/meter **V2** (SEN0161-V2), with probe | Output 0–3.0 V, safe for the ESP32 |
| 1 set | pH buffer solutions **4.00** and **7.00** (or 6.86) | For calibration; fresh, in date |
| — | Breadboard or perfboard, jumper wires, small plastic box | Keep the electronics away from liquid |
| — | Distilled water and paper tissue | Rinse and dab the probe between buffers |
| — | Reference thermometer | For the bench test |

**Warning:** many cheap pH boards (for example "PH-4502C") are powered by
5 V and their output can reach 5 V. The ESP32 input allows **at most 3.3 V**.
With such a board, put a voltage divider on the output (for example
10 kΩ + 20 kΩ) and calibrate afterwards. Never connect a 5 V signal directly.

**Food contact:** the DS18B20 probe should have a food-grade stainless steel
sleeve. Lab pH probes are glass; they are made for dipping into samples, not
for permanent installation in a fermenter. For the MVP, measure in a sample
cup or a sampling port, and clean the probes as your hygiene plan requires.

## 2. Wiring

```
                 ESP32 DevKit
             ┌──────────────────┐
  DS18B20    │                  │      DFRobot pH V2 board
  red ───────┤ 3V3          3V3 ├────── + (VCC)
  black ─────┤ GND          GND ├────── − (GND)
  yellow ──┬─┤ GPIO 4   GPIO 34 ├────── A (signal)
           │ │                  │
  4.7 kΩ   │ └──────────────────┘
  between ─┘
  yellow and 3V3
```

- DS18B20 data → **GPIO 4**, with the 4.7 kΩ resistor between data and 3.3 V.
- pH signal → **GPIO 34**. pH must use an ADC1 pin (GPIO 32–39), because
  ADC2 pins do not work while Wi-Fi is on.
- Both sensors are powered from **3.3 V**.
- Different pins? Change `TEMP_PIN` / `PH_PIN` in `config.h`.

## 3. Software on the server computer

1. Add the device and copy the key it prints (it is shown only once):
   ```
   python -m smartmet_db device add tank-1
   ```
   Lost the key? `python -m smartmet_db device rotate-key tank-1` makes a new one.
2. Start the server so that other devices on the network can reach it:
   ```
   python -m uvicorn smartmet_api.main:app --host 0.0.0.0 --port 8000
   ```
   Windows will ask whether Python may accept network connections. Allow it
   for **private networks**.
3. Find the computer's address with `ipconfig` ("IPv4 Address", for example
   192.168.1.50).
4. On the dashboard, open the batch and use **Measure this batch** to assign
   `tank-1`. Until it is assigned, the server refuses the device's readings.

**Test without hardware first.** The emulator sends exactly what the
ESP32 will send:
```
python simulator.py --device --api-key smk_... --http --interval 5
```

## 4. Flashing the firmware

1. Install the **Arduino IDE 2**.
2. Add ESP32 support:
   - **File → Preferences → Additional boards manager URLs**:
     `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
   - **Tools → Board → Boards Manager**: install **esp32 by Espressif**
     (version 3.x).
3. **Tools → Manage Libraries**: install **OneWire**, **DallasTemperature**
   and **ArduinoJson** (version 7).
4. Copy `firmware/smartmet_esp32/config.example.h` to `config.h` in the same
   folder. Fill in the Wi-Fi name and password, `SERVER_URL` (with the
   computer's address from step 3.3) and `DEVICE_API_KEY`.
5. Open `firmware/smartmet_esp32/smartmet_esp32.ino`. Choose **Tools → Board
   → ESP32 Dev Module** and the right **Port**, then click **Upload**.
6. Open **Tools → Serial Monitor** at **115200 baud** with line ending
   **Newline**. You should see `measured: temp 23.4 C, pH -- ...  [pH not
   calibrated]`.

## 5. pH calibration

The firmware does **not send pH until it is calibrated**, because an
uncalibrated pH value is meaningless. Calibrate when the device is new,
then regularly (start with weekly), and whenever the probe is replaced.

1. Let the buffers reach room temperature. Put the temperature probe in the
   same buffer as the pH probe so the firmware records the buffer temperature.
2. Rinse the pH probe with distilled water and dab it dry (do not rub).
3. Put it in the **pH 7** buffer. Wait 1–2 minutes until `show` gives a stable
   mV value, then type `cal7`.
4. Rinse and dab dry, then put it in the **pH 4** buffer. Wait until stable,
   then type `cal4`. You should see `calibration complete: about -59 mV per
   pH unit` (a value between about −50 and −62 at 25 °C is normal).
5. The calibration is saved on the board and survives restarts. `reset`
   clears it.

If you see "voltages are too close", the probe is broken, dry or dirty, or
the buffers are old.

## 6. Bench test (MVP checklist item 10)

Write the results down. They go into the project as proof that the device works.

| Check | How | Pass |
|---|---|---|
| Temperature | Probe and reference thermometer side by side in water at about 20 °C and about 30 °C | within ±0.5 °C |
| pH accuracy | After calibration, measure the pH 4 and pH 7 buffers again (and pH 10 if you have it) | within ±0.1 pH |
| pH stability | Leave the probe in the pH 7 buffer for 30 minutes | drift less than 0.05 pH |
| End to end | Device assigned to a test batch; readings appear on the dashboard every minute | values match the serial monitor |
| Offline buffer | Stop the server for 10 minutes, then start it again | the missing readings appear, nothing duplicated |
| Sensor fault | Unplug the DS18B20 for 2 minutes | "Sensor no value" alert for temperature |

Then do the **side-by-side batch** from the MVP plan. Run one real batch with
the device, and also measure pH and temperature by hand 2–3 times a day with
your current instruments, entered on the dashboard. The charts show both, so
the device can be compared with what you trust today.

## 7. What the firmware does

- Every 60 s it measures:
  - temperature, once
  - pH, as the median of 30 samples, with temperature compensation
- It sends `{"timestamp", "source": "device", "measurements": {...}}` with
  the `X-API-Key` header. The server adds the batch.
- It does not measure until it has the real time from the internet (NTP).
  Without it, a reading cannot be placed on the batch timeline.
- If Wi-Fi or the server is down, it keeps up to 120 readings (2 hours) and
  sends them later, oldest first. Duplicates are ignored by the server.
- Readings the server refuses for good are dropped and the reason is printed
  on the serial monitor:
  - wrong key
  - no batch assigned
- A disconnected temperature probe is sent as `null`, which raises the
  "Sensor no value" alert.

The firmware has not been compiled or tested on a real board yet. Report any
build errors and they will be fixed.
