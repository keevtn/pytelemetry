// PyTelemetry ESP32 / Arduino example. Owner: test-engineer.
//
// Exercises the unmodified device library over USB-CDC serial so PyTelemetry can watch it.
// Copy Dashboard.c, Dashboard.h, COBS.c, COBS.h (from firmware/) next to this sketch, or add
// firmware/ to your library path. Then open PyTelemetry, pick the ESP32's port, Connect.
//
// Wire: 115200 8N1, little-endian, device->host COBS-framed, host->device raw (see docs/PROTOCOL.md).

extern "C" {
#include "Dashboard.h"
}

static Dashboard_t g_dash;

// --- serial glue the library calls into -------------------------------------------------------
static bool sendData(const char *buf, uint32_t len) {
  return Serial.write((const uint8_t *)buf, len) == len;
}
static uint32_t readData(char *buf, uint32_t len) {
  return Serial.readBytes(buf, len);
}
static bool hasData(uint32_t *size) {
  int avail = Serial.available();
  if (avail <= 0) return false;
  *size = (uint32_t)avail;
  return true;
}

// --- a couple of live variables the host can read and tune ------------------------------------
static float   g_pitch  = 3.0f;    // id 1
static int32_t g_gain   = 10;      // id 2
static bool    g_enable = true;    // id 3

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(5);
  Dashboard_Init(&g_dash, sendData, readData, hasData);
  Dashboard_Register_LiveData(&g_dash, 1, &g_pitch,  TYPE_FLOAT);
  Dashboard_Register_LiveData(&g_dash, 2, &g_gain,   TYPE_INT32);
  Dashboard_Register_LiveData(&g_dash, 3, &g_enable, TYPE_BOOL);
}

void loop() {
  static uint32_t lastMs = 0;
  uint32_t now = millis();

  // ~20 Hz telemetry
  if (now - lastMs >= 50) {
    lastMs = now;
    float t = now / 1000.0f;
    Dashboard_Telemetry_Float(&g_dash, "Voltage", 12.0f + 0.5f * sinf(t * 2.0f));
    Dashboard_Telemetry_Int32(&g_dash, "RPM", (int32_t)(3000 + 1500 * sinf(t * 0.7f)));
    Dashboard_Telemetry_Uint32(&g_dash, "Uptime", now);
    if (g_enable && (now / 1000) % 10 == 0) {
      Dashboard_Alert(&g_dash, "heartbeat");
    }
  }

  // service inbound host packets (live-data read/modify)
  Dashboard_Update(&g_dash);
}
