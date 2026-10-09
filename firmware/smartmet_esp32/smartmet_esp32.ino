/*
  SmartMet4QC ESP32 firmware (Phase 6)

  Measures temperature (DS18B20) and pH (analog pH board) every READ_INTERVAL_SECONDS
  and sends them to the SmartMet4QC server in the data-contract shape:

    {"timestamp": "2026-10-09T10:00:00Z", "source": "device",
     "measurements": {"temperature_c": 26.12, "ph": 4.51}}

  The server knows which batch this device measures (chosen on the dashboard),
  so the device never sends a batch id.

  Board: ESP32 Dev Module (Arduino core for ESP32, version 3.x)
  Libraries (Arduino Library Manager): OneWire, DallasTemperature, ArduinoJson (7.x)

  Setup: copy config.example.h to config.h and fill it in.
  pH calibration: open the Serial Monitor (115200 baud, "Newline") and type `help`.
  See docs/HARDWARE.md for wiring, calibration and the bench test.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <time.h>

#include "config.h"

// ---------------------------------------------------------------- settings

const int PH_SAMPLES = 30;                 // pH = median of this many ADC readings
const int BUFFER_SIZE = 120;               // readings kept while offline (2 h at 60 s)
const float MIN_CAL_SPAN_MV = 200.0;       // pH 7 and pH 4 buffers must differ at least this much
const time_t VALID_TIME = 1700000000;      // clock is set once time() is past this (Nov 2023)

// ---------------------------------------------------------------- state

OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);
Preferences prefs;

struct Calibration {
  float mv7;       // probe voltage in pH 7 buffer
  float mv4;       // probe voltage in pH 4 buffer
  float tempC;     // buffer temperature during calibration
  bool valid;
} cal;

struct Reading {
  time_t time;
  float temperature;
  bool hasTemperature;
  float ph;
  bool hasPh;
};

Reading buffer[BUFFER_SIZE];
int bufferStart = 0;   // oldest unsent reading
int bufferCount = 0;
unsigned long lastRead = 0;
String serialLine;

// ---------------------------------------------------------------- measuring

float readTemperature(bool &ok) {
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  // -127 = sensor not connected; 85.0 = sensor reset value before a real conversion
  ok = t != DEVICE_DISCONNECTED_C && t != 85.0 && t > -50 && t < 150;
  return t;
}

int compareFloats(const void *a, const void *b) {
  float x = *(const float *)a, y = *(const float *)b;
  return (x > y) - (x < y);
}

// Median of many readings: ignores electrical noise and single bad samples.
float readPhMillivolts() {
  float samples[PH_SAMPLES];
  for (int i = 0; i < PH_SAMPLES; i++) {
    samples[i] = analogReadMilliVolts(PH_PIN);  // uses the ESP32's factory ADC calibration
    delay(20);
  }
  qsort(samples, PH_SAMPLES, sizeof(float), compareFloats);
  return samples[PH_SAMPLES / 2];
}

// Two-point calibration with temperature compensation.
// The probe's mV per pH unit is proportional to absolute temperature (Nernst);
// pH 7 is taken as the point where the response does not depend on temperature.
float millivoltsToPh(float mv, float tempC) {
  float slopeAtCal = (cal.mv4 - cal.mv7) / (4.0 - 7.0);  // mV per pH unit
  float slope = slopeAtCal * (tempC + 273.15) / (cal.tempC + 273.15);
  return 7.0 + (mv - cal.mv7) / slope;
}

Reading measure() {
  Reading r;
  r.time = time(nullptr);
  r.temperature = readTemperature(r.hasTemperature);
  float mv = readPhMillivolts();
  // Without calibration the pH value would be meaningless, so it is not sent.
  // Without a temperature, compensate for 25 C.
  r.hasPh = cal.valid;
  r.ph = cal.valid ? millivoltsToPh(mv, r.hasTemperature ? r.temperature : 25.0) : NAN;
  if (r.hasPh && (r.ph < 0 || r.ph > 14)) r.hasPh = false;  // probe unplugged or broken
  Serial.printf("measured: temp %s C, pH %s (%.0f mV)%s\n",
                r.hasTemperature ? String(r.temperature, 2).c_str() : "--",
                r.hasPh ? String(r.ph, 2).c_str() : "--", mv,
                cal.valid ? "" : "  [pH not calibrated: type `help`]");
  return r;
}

// ---------------------------------------------------------------- sending

String toJson(const Reading &r) {
  char timestamp[25];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%SZ", gmtime(&r.time));
  JsonDocument doc;
  doc["timestamp"] = timestamp;
  doc["source"] = "device";
  JsonObject m = doc["measurements"].to<JsonObject>();
  // null tells the server the sensor gave no value (it raises a "sensor no value" alert)
  if (r.hasTemperature) m["temperature_c"] = serialized(String(r.temperature, 2));
  else m["temperature_c"] = nullptr;
  if (r.hasPh) m["ph"] = serialized(String(r.ph, 2));
  String body;
  serializeJson(doc, body);
  return body;
}

// Returns true when the reading is done with (stored, duplicate, or permanently refused),
// false when it should be kept and retried later (no network, server down).
bool send(const Reading &r) {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.setTimeout(5000);
  if (!http.begin(SERVER_URL)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", DEVICE_API_KEY);
  int code = http.POST(toJson(r));
  String answer = http.getString();
  http.end();

  if (code == 200 || code == 201) return true;
  if (code == 409) {
    Serial.println("server: this device has no batch assigned. Assign it on the dashboard; reading dropped.");
    return true;
  }
  if (code == 401) {
    Serial.println("server: API key refused. Check DEVICE_API_KEY in config.h; reading dropped.");
    return true;
  }
  if (code >= 400 && code < 500 && code != 408 && code != 429) {
    Serial.printf("server refused the reading (HTTP %d): %s\n", code, answer.c_str());
    return true;  // resending the same data would be refused again
  }
  Serial.printf("send failed (%d), will retry: %s\n", code, code < 0 ? http.errorToString(code).c_str() : answer.c_str());
  return false;
}

void addToBuffer(const Reading &r) {
  if (bufferCount == BUFFER_SIZE) {  // full: forget the oldest
    bufferStart = (bufferStart + 1) % BUFFER_SIZE;
    bufferCount--;
    Serial.println("offline buffer full: oldest reading dropped");
  }
  buffer[(bufferStart + bufferCount) % BUFFER_SIZE] = r;
  bufferCount++;
}

// Send the oldest readings first; stop at the first one that must be retried.
// Resending is safe: the server ignores readings it already has.
void flushBuffer() {
  while (bufferCount > 0 && send(buffer[bufferStart])) {
    bufferStart = (bufferStart + 1) % BUFFER_SIZE;
    bufferCount--;
  }
  if (bufferCount > 0) Serial.printf("%d reading(s) waiting to be sent\n", bufferCount);
}

// ---------------------------------------------------------------- calibration (serial commands)

void loadCalibration() {
  prefs.begin("smartmet", true);
  cal.mv7 = prefs.getFloat("mv7", NAN);
  cal.mv4 = prefs.getFloat("mv4", NAN);
  cal.tempC = prefs.getFloat("tcal", 25.0);
  prefs.end();
  cal.valid = !isnan(cal.mv7) && !isnan(cal.mv4) && fabs(cal.mv4 - cal.mv7) >= MIN_CAL_SPAN_MV;
}

void calibratePoint(float bufferPh) {
  bool tempOk;
  float t = readTemperature(tempOk);
  float mv = readPhMillivolts();
  prefs.begin("smartmet", false);
  prefs.putFloat(bufferPh == 7.0 ? "mv7" : "mv4", mv);
  if (tempOk) prefs.putFloat("tcal", t);
  prefs.end();
  Serial.printf("pH %.0f buffer: %.0f mV at %s C saved\n", bufferPh, mv, tempOk ? String(t, 1).c_str() : "?");
  loadCalibration();
  if (cal.valid) Serial.printf("calibration complete: %.1f mV per pH unit\n", (cal.mv4 - cal.mv7) / -3.0);
  else if (!isnan(cal.mv7) && !isnan(cal.mv4))
    Serial.println("WARNING: pH 7 and pH 4 voltages are too close; check the probe and buffers, then repeat");
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toLowerCase();
  if (cmd == "cal7") calibratePoint(7.0);
  else if (cmd == "cal4") calibratePoint(4.0);
  else if (cmd == "show") {
    Serial.printf("calibration: pH7 %.0f mV, pH4 %.0f mV, at %.1f C -> %s\n",
                  cal.mv7, cal.mv4, cal.tempC, cal.valid ? "valid" : "NOT valid");
    measure();
  } else if (cmd == "reset") {
    prefs.begin("smartmet", false);
    prefs.clear();
    prefs.end();
    loadCalibration();
    Serial.println("pH calibration cleared");
  } else {
    Serial.println("commands:\n"
                   "  cal7   probe in pH 7 buffer (wait until stable), store that point\n"
                   "  cal4   probe in pH 4 buffer (rinse first), store that point\n"
                   "  show   show calibration and take a measurement\n"
                   "  reset  clear the calibration");
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialLine.length()) handleCommand(serialLine);
      serialLine = "";
    } else if (serialLine.length() < 40) {
      serialLine += c;
    }
  }
}

// ---------------------------------------------------------------- main

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nSmartMet4QC device starting");

  tempSensor.begin();
  analogSetPinAttenuation(PH_PIN, ADC_11db);  // 0 to ~3.1 V input range
  loadCalibration();
  if (!cal.valid) Serial.println("pH is not calibrated yet: type `help` for the calibration commands");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.google.com");  // timestamps are sent in UTC
}

void loop() {
  readSerial();

  if (millis() - lastRead >= READ_INTERVAL_SECONDS * 1000UL || lastRead == 0) {
    lastRead = millis();
    if (WiFi.status() != WL_CONNECTED) Serial.println("Wi-Fi not connected (yet)");

    if (time(nullptr) < VALID_TIME) {
      // Without the real time a reading cannot be placed on the batch timeline.
      Serial.println("waiting for the internet time (NTP) before measuring");
    } else {
      addToBuffer(measure());
      flushBuffer();
    }
  }
  delay(50);
}
