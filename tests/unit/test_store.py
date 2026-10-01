"""Ring buffer + store semantics. Owner: core-engineer."""

from __future__ import annotations

import time

from pytelemetry.core.store import RingBuffer, TelemetryStore
from pytelemetry.core.types import Alert, Telemetry, ValueType


def test_ring_buffer_before_full() -> None:
    rb = RingBuffer(5)
    for i in range(3):
        rb.append(float(i), float(i * 10))
    t, v = rb.view()
    assert list(t) == [0.0, 1.0, 2.0]
    assert list(v) == [0.0, 10.0, 20.0]
    assert len(rb) == 3


def test_ring_buffer_wraps_oldest_first() -> None:
    rb = RingBuffer(3)
    for i in range(5):  # 0,1,2,3,4 -> keeps 2,3,4
        rb.append(float(i), float(i))
    t, v = rb.view()
    assert list(t) == [2.0, 3.0, 4.0]
    assert list(v) == [2.0, 3.0, 4.0]
    assert len(rb) == 3


def test_store_tracks_latest_and_history() -> None:
    store = TelemetryStore(history_samples=100)
    now = time.monotonic()
    for i in range(10):
        store.on_telemetry(Telemetry("Voltage", ValueType.FLOAT, 12.0 + i, now + i))
    assert store.latest("Voltage").value == 21.0
    t, v = store.history("Voltage")
    assert len(v) == 10 and v[0] == 12.0 and v[-1] == 21.0
    assert store.keys() == ["Voltage"]


def test_store_bool_and_int_are_numeric() -> None:
    store = TelemetryStore()
    store.on_telemetry(Telemetry("Enable", ValueType.BOOL, True, 1.0))
    store.on_telemetry(Telemetry("Enable", ValueType.BOOL, False, 2.0))
    _, v = store.history("Enable")
    assert list(v) == [1.0, 0.0]


def test_store_string_has_latest_but_no_history() -> None:
    store = TelemetryStore()
    store.on_telemetry(Telemetry("Mode", ValueType.STRING, "RUN", 1.0))
    assert store.latest("Mode").value == "RUN"
    t, v = store.history("Mode")
    assert len(v) == 0


def test_store_alert_ring() -> None:
    store = TelemetryStore(alert_limit=3)
    for i in range(5):
        store.on_alert(Alert(f"a{i}", float(i)))
    msgs = [a.message for a in store.alerts()]
    assert msgs == ["a2", "a3", "a4"]
