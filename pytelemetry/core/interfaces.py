"""Protocol interfaces every component codes against. Owner: lead. Changes go through the lead only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pytelemetry.core.types import Alert, Frame, LinkStats, LiveVar, Telemetry


@runtime_checkable
class Transport(Protocol):
    """A byte pipe. Implementations: serial_for_url (COM5, /dev/tty*, socket://, loop://), in-memory."""

    def open(self) -> None: ...

    def close(self) -> None: ...

    def read(self, max_bytes: int) -> bytes:
        """Return up to max_bytes; empty bytes on timeout. Never blocks forever."""
        ...

    def write(self, data: bytes) -> int:
        """Write all of data in one call (device parses per-write). Returns bytes written."""
        ...

    @property
    def is_open(self) -> bool: ...


class Framer(Protocol):
    """Device->host byte stream -> validated Frames. Stateful; drops bad chunks and counts them."""

    def feed(self, data: bytes) -> list[Frame]: ...

    @property
    def stats(self) -> LinkStats: ...


class EventSink(Protocol):
    """Receives decoded events from the session's reader thread. Must be thread-safe and non-blocking."""

    def on_telemetry(self, item: Telemetry) -> None: ...

    def on_alert(self, item: Alert) -> None: ...

    def on_live_data(self, items: tuple[LiveVar, ...]) -> None: ...

    def on_stats(self, stats: LinkStats) -> None: ...


class Session(Protocol):
    """Owns the I/O thread over one Transport; dispatches decoded events to sinks."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def add_sink(self, sink: EventSink) -> None: ...

    def request_live_data(self) -> None: ...

    def modify_live_var(self, var_id: int, value_type: int, value: int | float | bool) -> None: ...

    @property
    def stats(self) -> LinkStats: ...


class TelemetryStore(Protocol):
    """Read view the UI drains at 30 Hz. History is numpy ring buffers; views, not copies."""

    def keys(self) -> list[str]: ...

    def latest(self, key: str) -> Telemetry | None: ...

    def history(self, key: str) -> tuple[object, object]:
        """(times, values) as numpy array views, oldest first."""
        ...

    def alerts(self, limit: int = 1000) -> list[Alert]: ...

    def live_vars(self) -> tuple[LiveVar, ...]: ...
