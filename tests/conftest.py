"""Shared fixtures. Owner: test-engineer."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pytelemetry.core.types import Alert, LinkStats, LiveVar, Telemetry
from pytelemetry.sim.server import SimServer


class CaptureSink:
    """EventSink that records everything, for assertions."""

    def __init__(self) -> None:
        self.telemetry: list[Telemetry] = []
        self.alerts: list[Alert] = []
        self.live: tuple[LiveVar, ...] | None = None
        self.stats: LinkStats | None = None

    def on_telemetry(self, item: Telemetry) -> None:
        self.telemetry.append(item)

    def on_alert(self, item: Alert) -> None:
        self.alerts.append(item)

    def on_live_data(self, items: tuple[LiveVar, ...]) -> None:
        self.live = items

    def on_stats(self, stats: LinkStats) -> None:
        self.stats = stats


@pytest.fixture
def capture_sink() -> CaptureSink:
    return CaptureSink()


@pytest.fixture
def sim_server() -> Iterator[SimServer]:
    server = SimServer(port=0, rate_hz=200.0)
    server.start()
    try:
        yield server
    finally:
        server.stop()
