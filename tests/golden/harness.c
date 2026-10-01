/*
 * Golden-vector harness for the PyTelemetry v1 protocol.
 * Compiles against the UNMODIFIED device library and prints JSON to stdout.
 *
 *   cc -std=c11 -I firmware -o build/golden_harness tests/golden/harness.c firmware/Dashboard.c firmware/COBS.c
 *   build/golden_harness > tests/golden/vectors.json
 *
 * tools/gen_golden.py wraps this. Every entry is captured from the real library, never typed by hand.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "Dashboard.h"
#include "COBS.h"

static char rx[256];
static uint32_t rxLen = 0, rxPos = 0;
static char captured[64][256];
static uint32_t capturedLen[64];
static uint32_t capturedCount = 0;

static bool sendData(const char *buf, uint32_t n) {
    if (capturedCount < 64 && n < 256) { memcpy(captured[capturedCount], buf, n); capturedLen[capturedCount] = n; capturedCount++; }
    return true;
}
static uint32_t readData(char *buf, uint32_t size) {
    uint32_t n = rxLen - rxPos; if (n > size) n = size; memcpy(buf, rx + rxPos, n); rxPos += n; return n;
}
static bool hasData(uint32_t *size) { *size = rxLen - rxPos; return *size > 0; }

static void printHex(const char *buf, uint32_t n) { for (uint32_t i = 0; i < n; i++) printf("%02x", (unsigned char) buf[i]); }
static int first = 1;
static void beginEntry(const char *section, const char *name, const char *call) {
    printf("%s\n    {\"section\": \"%s\", \"name\": \"%s\", \"call\": \"%s\"", first ? "" : ",", section, name, call);
    first = 0;
}
static void emitCaptured(void) {
    printf(", \"wire\": [");
    for (uint32_t i = 0; i < capturedCount; i++) { printf("%s\"", i ? ", " : ""); printHex(captured[i], capturedLen[i]); printf("\""); }
    printf("]}");
    capturedCount = 0;
}
static void emitRaw(const char *buf, uint32_t n) { printf(", \"wire\": [\""); printHex(buf, n); printf("\"]}"); }

static uint32_t buildHostFrame(char *out, uint8_t type, uint8_t ctype, const void *payload, uint16_t payloadLen) {
    DashboardPacketHeader_t h;
    /* Mirrors LiveDataPanel: Modify puts the LiveDataPacket in the *key* slot, Request has an empty payload. */
    craftDashboardHeaderPacket(&h, type, ctype, payloadLen, 0);
    uint32_t crc = crc32((const char *) payload, payloadLen, 0);
    memcpy(out, &h, sizeof h);
    memcpy(out + sizeof h, payload, payloadLen);
    memcpy(out + sizeof h + payloadLen, &crc, sizeof crc);
    return sizeof h + payloadLen + sizeof crc;
}
static void feedAndRun(Dashboard_t *d, const char *frame, uint32_t n) {
    memcpy(rx, frame, n); rxLen = n; rxPos = 0;
    Dashboard_Update(d); Dashboard_Update(d);
}

int main(void) {
    Dashboard_t d;
    Dashboard_Init(&d, sendData, readData, hasData);
    char frame[128];
    LiveDataPacket_t p;

    printf("{\n  \"generated_from\": \"firmware/Dashboard.c + COBS.c (upstream src/dashboard)\",\n");
    printf("  \"notes\": \"device_to_host entries are COBS-encoded with trailing 0x00; host_to_device entries are raw. "
           "Multi-frame entries list every frame the device sent, in order.\",\n");
    printf("  \"check_values\": {\"crc16_arc_123456789\": \"0x%04x\", \"crc32_payload_123456789\": \"0x%08x\", \"crc32_payload_empty\": \"0x%08x\", "
           "\"sizeof_header\": %zu, \"sizeof_livedata\": %zu, \"sizeof_tail\": %zu},\n",
           crc16("123456789", 9, 0), crc32("123456789", 9, 0), crc32("", 0, 0),
           sizeof(DashboardPacketHeader_t), sizeof(LiveDataPacket_t), sizeof(DashboardPacketTail_t));
    printf("  \"vectors\": [");

    /* ---- device -> host, one frame each ---- */
    beginEntry("device_to_host", "telemetry_float", "Dashboard_Telemetry_Float(\\\"Voltage\\\", 12.5f)");
    Dashboard_Telemetry_Float(&d, "Voltage", 12.5f); emitCaptured();
    beginEntry("device_to_host", "telemetry_int32_negative", "Dashboard_Telemetry_Int32(\\\"RPM\\\", -42)");
    Dashboard_Telemetry_Int32(&d, "RPM", -42); emitCaptured();
    beginEntry("device_to_host", "telemetry_uint32_with_zero_bytes", "Dashboard_Telemetry_Uint32(\\\"Ticks\\\", 0x01000200)");
    Dashboard_Telemetry_Uint32(&d, "Ticks", 0x01000200u); emitCaptured();
    beginEntry("device_to_host", "telemetry_uint32_zero", "Dashboard_Telemetry_Uint32(\\\"Z\\\", 0)");
    Dashboard_Telemetry_Uint32(&d, "Z", 0u); emitCaptured();
    beginEntry("device_to_host", "telemetry_float_nan", "Dashboard_Telemetry_Float(\\\"N\\\", NAN)");
    { float nan = 0.0f / 0.0f; Dashboard_Telemetry_Float(&d, "N", nan); } emitCaptured();
    beginEntry("device_to_host", "telemetry_string", "Dashboard_Telemetry_Str(\\\"Mode\\\", \\\"RUN\\\")");
    Dashboard_Telemetry_Str(&d, "Mode", "RUN"); emitCaptured();
    beginEntry("device_to_host", "telemetry_string_empty_value", "Dashboard_Telemetry_Str(\\\"E\\\", \\\"\\\")");
    Dashboard_Telemetry_Str(&d, "E", ""); emitCaptured();
    beginEntry("device_to_host", "alert", "Dashboard_Alert(\\\"Hello\\\")");
    Dashboard_Alert(&d, "Hello"); emitCaptured();
    {   /* largest frame the library can send: key 1 + value 82 = 83 bytes payload, raw 99 */
        char big[83]; memset(big, 'x', 82); big[82] = 0;
        beginEntry("device_to_host", "telemetry_string_max_size", "Dashboard_Telemetry_Str(\\\"k\\\", 82 x 'x')");
        Dashboard_Telemetry_Str(&d, "k", big); emitCaptured();
        char tooBig[84]; memset(tooBig, 'x', 83); tooBig[83] = 0;
        beginEntry("device_to_host", "telemetry_string_too_large_not_sent", "Dashboard_Telemetry_Str(\\\"k\\\", 83 x 'x') -> DASHBOARD_ERR_COBS_FAILED");
        Dashboard_Telemetry_Str(&d, "k", tooBig); emitCaptured();  /* expect [] */
    }

    /* ---- host -> device frames, built exactly as the C++ LiveDataPanel builds them ---- */
    uint32_t n = buildHostFrame(frame, ID_Request_LiveData, 0, "", 0);
    beginEntry("host_to_device", "request_live_data", "LiveDataPanel::refreshPackets()"); emitRaw(frame, n);

    memset(&p, 0, sizeof p); p.packetID = 7; p.valueType = TYPE_FLOAT; p.floatValue = 3.25f;
    n = buildHostFrame(frame, ID_Modify, TYPE_FLOAT, &p, sizeof p);
    beginEntry("host_to_device", "modify_float_id7", "sendModifyPacket(7, FLOAT 3.25)"); emitRaw(frame, n);

    /* ---- device receive path: register 4 vars, then replay host frames and capture everything it says ---- */
    float pitch = 1.5f; int32_t gain = 10; bool enable = true; uint32_t limit = 4000;
    Dashboard_Register_LiveData(&d, 1, &pitch, TYPE_FLOAT);
    Dashboard_Register_LiveData(&d, 2, &gain, TYPE_INT32);
    Dashboard_Register_LiveData(&d, 3, &enable, TYPE_BOOL);
    Dashboard_Register_LiveData(&d, 4, &limit, TYPE_UINT32);

    n = buildHostFrame(frame, ID_Request_LiveData, 0, "", 0);
    beginEntry("exchange", "request_live_data_4_vars", "vars {1:f32 1.5, 2:i32 10, 3:bool true, 4:u32 4000}; feed request_live_data");
    feedAndRun(&d, frame, n); emitCaptured();

    memset(&p, 0, sizeof p); p.packetID = 1; p.valueType = TYPE_FLOAT; p.floatValue = 3.25f;
    n = buildHostFrame(frame, ID_Modify, TYPE_FLOAT, &p, sizeof p);
    beginEntry("exchange", "modify_float_id1_ok", "feed modify(1, FLOAT 3.25); pitch becomes 3.25");
    feedAndRun(&d, frame, n); emitCaptured();

    memset(&p, 0, sizeof p); p.packetID = 3; p.valueType = TYPE_BOOL; p.boolValue = false;
    n = buildHostFrame(frame, ID_Modify, TYPE_BOOL, &p, sizeof p);
    beginEntry("exchange", "modify_bool_id3_false", "feed modify(3, BOOL false); enable becomes false");
    feedAndRun(&d, frame, n); emitCaptured();

    memset(&p, 0, sizeof p); p.packetID = 2; p.valueType = TYPE_FLOAT; p.floatValue = 1.0f;
    n = buildHostFrame(frame, ID_Modify, TYPE_FLOAT, &p, sizeof p);
    beginEntry("exchange", "modify_type_mismatch", "feed modify(2, FLOAT 1.0) but var 2 is INT32 -> 'Live Data Type Mismatch', gain unchanged");
    feedAndRun(&d, frame, n); emitCaptured();

    memset(&p, 0, sizeof p); p.packetID = 9; p.valueType = TYPE_INT32; p.int32Value = 5;
    n = buildHostFrame(frame, ID_Modify, TYPE_INT32, &p, sizeof p);
    beginEntry("exchange", "modify_unknown_id", "feed modify(9, INT32 5) -> ignored after generic alerts");
    feedAndRun(&d, frame, n); emitCaptured();

    n = buildHostFrame(frame, ID_Request_LiveData, 0, "", 0);
    frame[n - 1] ^= 0xFF;  /* corrupt payload CRC */
    beginEntry("exchange", "request_bad_payload_crc", "feed request_live_data with corrupted tail -> 'Payload checksum mismatch'");
    feedAndRun(&d, frame, n); emitCaptured();

    n = buildHostFrame(frame, ID_Request_LiveData, 0, "", 0);
    frame[10] ^= 0xFF;     /* corrupt header CRC: consumed silently */
    beginEntry("exchange", "request_bad_header_crc_silent", "feed request_live_data with corrupted header CRC -> nothing sent");
    feedAndRun(&d, frame, n); emitCaptured();

    printf("\n  ],\n  \"final_state\": {\"pitch\": %g, \"gain\": %d, \"enable\": %s, \"limit\": %u}\n}\n",
           pitch, gain, enable ? "true" : "false", limit);
    return 0;
}
