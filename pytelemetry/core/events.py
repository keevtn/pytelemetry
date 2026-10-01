"""Thread-safe event bus between the reader thread and sinks. Owner: core-engineer.

Fan-out is synchronous on the caller's thread; sinks must be cheap and non-blocking (the UI sink just
enqueues). A raising sink is isolated and logged so one bad sink can't stall the reader.
"""

from __future__ import annotations

import logging
import threading

from pytelemetry.core.interfaces import EventSink
from pytelemetry.core.types import Alert, LinkStats, LiveVar, Telemetry

__all__ = ["EventBus"]

_log = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._sinks: list[EventSink] = []
        self._lock = threading.Lock()

    def add_sink(self, sink: EventSink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def _snapshot(self) -> list[EventSink]:
        with self._lock:
            return list(self._sinks)

    def emit_telemetry(self, item: Telemetry) -> None:
        for sink in self._snapshot():
            try:
                sink.on_telemetry(item)
            except Exception:
                _log.exception("sink.on_telemetry failed")

    def emit_alert(self, item: Alert) -> None:
        for sink in self._snapshot():
            try:
                sink.on_alert(item)
            except Exception:
                _log.exception("sink.on_alert failed")

    def emit_live_data(self, items: tuple[LiveVar, ...]) -> None:
        for sink in self._snapshot():
            try:
                sink.on_live_data(items)
            except Exception:
                _log.exception("sink.on_live_data failed")

    def emit_stats(self, stats: LinkStats) -> None:
        for sink in self._snapshot():
            try:
                sink.on_stats(stats)
            except Exception:
                _log.exception("sink.on_stats failed")
