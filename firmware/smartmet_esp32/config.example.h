// SmartMet4QC device settings.
// Copy this file to config.h (same folder) and fill in your values.
// config.h is ignored by git: it contains your Wi-Fi password and the device key.

#pragma once

// Wi-Fi (2.4 GHz network; the ESP32 cannot use 5 GHz)
#define WIFI_SSID        "your-wifi-name"
#define WIFI_PASSWORD    "your-wifi-password"

// The computer running the SmartMet4QC server. Use its address on your network
// (for example from `ipconfig`), not 127.0.0.1, and start the server with
//   python -m uvicorn smartmet_api.main:app --host 0.0.0.0 --port 8000
#define SERVER_URL       "http://192.168.1.50:8000/api/v1/measurements"

// From: python -m smartmet_db device add tank-1
#define DEVICE_API_KEY   "smk_paste-the-key-here"

// How often to measure and send
#define READ_INTERVAL_SECONDS  60

// Wiring (see docs/HARDWARE.md)
#define TEMP_PIN   4    // DS18B20 data wire, with 4.7 kOhm pull-up to 3.3 V
#define PH_PIN     34   // pH board analog output; must be an ADC1 pin (32-39) because ADC2 is unusable with Wi-Fi
