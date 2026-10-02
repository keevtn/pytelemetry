"""Telemetry store: per-channel numpy ring buffers + latest/alerts/live-vars. Owner: core-engineer.

The UI drains this at 30 Hz; reads return oldest-first numpy copies (safe to hold across concurrent writes)
and all access is mutex-guarded because writes arrive on the reader thread. One ring buffer pair (time,
value) per numeric channel,
preallocated to history_samples (PROTOCOL.md section 8: >= 100k samples/channel).
"""

from __future__ import annotations

import threading
from collections import deque

import numpy as np

from pytelemetry.core.types import Alert, LiveVar, Telemetry, ValueType

__all__ = ["TelemetryStore", "RingBuffer"]


class RingBuffer:
    """Fixed-capacity numeric ring buffer. Reads return oldest-first copies, safe to hold across writes."""

    def __init__(self, capacity: int) -> None:
        self._cap = max(1, capacity)
        self._t = np.empty(self._cap, dtype=np.float64)
        self._v = np.empty(self._cap, dtype=np.float64)
        self._head = 0  # next write index
        self._count = 0

    def append(self, t: float, v: float) -> None:
        self._t[self._head] = t
        self._v[self._head] = v
        self._head = (self._head + 1) % self._cap
        if self._count < self._cap:
            self._count += 1

    def view(self) -> tuple[np.ndarray, np.ndarray]:
        # Copies, not views: the caller (pyqtgraph) holds the result until the next 30 Hz refresh, during
        # which the reader thread keeps appending; a bare slice would be mutated under it once the buffer
        # wraps. The full-buffer path already copies via fancy indexing; the partial path copies explicitly.
        if self._count < self._cap:
            return self._t[: self._count].copy(), self._v[: self._count].copy()
        # full: reorder oldest-first
        idx = np.arange(self._head, self._head + self._cap) % self._cap
        return self._t[idx], self._v[idx]

    def __len__(self) -> int:
        return self._count


_NUMERIC = (ValueType.UINT32, ValueType.INT32, ValueType.FLOAT, ValueType.BOOL)


class TelemetryStore:
    def __init__(self, history_samples: int = 100_000, alert_limit: int = 5000) -> None:
        self._history = history_samples
        self._lock = threading.Lock()
        self._latest: dict[str, Telemetry] = {}
        self._rings: dict[str, RingBuffer] = {}
        self._order: list[str] = []
        self._alerts: deque[Alert] = deque(maxlen=alert_limit)
        self._live: tuple[LiveVar, ...] = ()

    # ---- writes (reader thread) -----------------------------------------------------------------

    def on_telemetry(self, item: Telemetry) -> None:
        with self._lock:
            if item.key not in self._latest:
                self._order.append(item.key)
            self._latest[item.key] = item
            if item.type in _NUMERIC:
                ring = self._rings.get(item.key)
                if ring is None:
                    ring = RingBuffer(self._history)
                    self._rings[item.key] = ring
                ring.append(item.t, float(item.value))

    def on_alert(self, item: Alert) -> None:
        with self._lock:
            self._alerts.append(item)

    def on_live_data(self, items: tuple[LiveVar, ...]) -> None:
        with self._lock:
            self._live = items

    def on_stats(self, stats: object) -> None:  # store ignores stats; UI reads them from session
        return

    # ---- reads (UI thread) ----------------------------------------------------------------------

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._order)

    def latest(self, key: str) -> Telemetry | None:
        with self._lock:
            return self._latest.get(key)

    def history(self, key: str) -> tuple[np.ndarray, np.ndarray]:
        with self._lock:
            ring = self._rings.get(key)
            if ring is None:
                empty = np.empty(0, dtype=np.float64)
                return empty, empty
            return ring.view()

    def alerts(self, limit: int = 1000) -> list[Alert]:
        with self._lock:
            if limit >= len(self._alerts):
                return list(self._alerts)
            return list(self._alerts)[-limit:]

    def live_vars(self) -> tuple[LiveVar, ...]:
        with self._lock:
            return self._live
