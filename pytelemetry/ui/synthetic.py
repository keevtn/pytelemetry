"""Synthetic source for `pytelemetry --demo` (dev only). Owner: ui-engineer.

Same shape as Session (add_sink/start/stop/request_live_data/modify_live_var/stats) so the window treats
them interchangeably. Pushes plausible channels through an EventBus on a background thread, nothing connected.
"""

from __future__ import annotations

import math
import threading
import time

from pytelemetry.core.events import EventBus
from pytelemetry.core.interfaces import EventSink
from pytelemetry.core.types import Alert, LinkStats, LiveVar, Telemetry, ValueType

__all__ = ["SyntheticSource"]


class SyntheticSource:
    def __init__(self, rate_hz: float = 200.0) -> None:
        self._dt = 1.0 / rate_hz
        self._bus = EventBus()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames = 0
        self._live = {
            1: LiveVar(1, ValueType.FLOAT, 3.0, "Pitch", "deg", -45.0, 45.0),
            2: LiveVar(2, ValueType.INT32, 10, "Gain", ""),
            3: LiveVar(3, ValueType.BOOL, True, "Enable", ""),
            4: LiveVar(4, ValueType.UINT32, 4000, "Limit", "rpm"),
        }

    def add_sink(self, sink: EventSink) -> None:
        self._bus.add_sink(sink)

    def start(self) -> None:
        self._bus.emit_live_data(tuple(self._live.values()))
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="synthetic", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def request_live_data(self) -> None:
        self._bus.emit_live_data(tuple(self._live.values()))

    def modify_live_var(self, var_id: int, value_type: int, value: int | float | bool) -> None:
        cur = self._live.get(var_id)
        if cur is not None:
            self._live[var_id] = LiveVar(cur.id, cur.type, value, cur.name, cur.unit, cur.minimum, cur.maximum)
            self._bus.emit_live_data(tuple(self._live.values()))

    @property
    def stats(self) -> LinkStats:
        return LinkStats(frames_ok=self._frames)

    def _run(self) -> None:
        start = time.monotonic()
        last_mode = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            t = now - start
            self._bus.emit_telemetry(Telemetry("Voltage", ValueType.FLOAT, 12.0 + 0.5 * math.sin(t * 2), now))
            self._bus.emit_telemetry(Telemetry("Current", ValueType.FLOAT, 1.5 + 0.3 * math.sin(t * 3 + 1), now))
            self._bus.emit_telemetry(Telemetry("RPM", ValueType.INT32, int(3000 + 1500 * math.sin(t * 0.7)), now))
            self._bus.emit_telemetry(Telemetry("Noise", ValueType.FLOAT, math.sin(t * 50) * 0.2, now))
            self._frames += 4
            if now - last_mode > 1.0:
                last_mode = now
                mode = "RUN" if int(t) % 2 == 0 else "IDLE"
                self._bus.emit_telemetry(Telemetry("Mode", ValueType.STRING, mode, now))
                self._bus.emit_alert(Alert(f"synthetic tick t={t:.0f}s", now, debug=False))
            time.sleep(self._dt)
