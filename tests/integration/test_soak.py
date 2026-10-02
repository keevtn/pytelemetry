"""Throughput/memory soak. Owner: test-engineer. Run with `pytest -m soak`.

PROTOCOL.md section 8: the pipeline must sustain >= 2,000 frames/s with zero drops.
"""

from __future__ import annotations

import time

import pytest

from pytelemetry.core.session import Session
from pytelemetry.core.store import TelemetryStore
from pytelemetry.core.transport.memory_transport import memory_pair
from pytelemetry.core.types import ValueType
from pytelemetry.sim.fake_device import FakeDevice


@pytest.mark.soak
def test_sustained_throughput_zero_drops() -> None:
    host_end, dev_end = memory_pair(timeout=0.01)
    dev_end.open()
    device = FakeDevice()
    store = TelemetryStore(history_samples=200_000)
    session = Session(host_end)
    session.add_sink(store)
    session.start()

    target = 60_000  # 30 s worth at 2k/s; runs much faster but exercises the path
    sent = 0
    start = time.monotonic()
    try:
        while sent < target:
            batch = bytearray()
            for _ in range(200):
                for f in device.telemetry("Voltage", ValueType.FLOAT, 12.0 + (sent % 100) * 0.01):
                    batch += f
                sent += 1
            dev_end.write(bytes(batch))
            time.sleep(0)
        # let the reader drain
        deadline = time.monotonic() + 10.0
        while session.stats.frames_ok < target and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        elapsed = time.monotonic() - start
        stats = session.stats
        session.stop()

    rate = stats.frames_ok / elapsed
    assert stats.frames_dropped == 0, f"dropped {stats.frames_dropped}"
    assert stats.frames_ok >= target, f"only {stats.frames_ok}/{target} decoded"
    assert rate >= 2000, f"throughput {rate:,.0f} frames/s below 2000"
