"""Scripted telemetry signals for the simulator. Owner: test-engineer.

Pure functions of time so output is deterministic and testable. Each channel yields (key, ValueType, value)
when sampled at monotonic time t. No device/transport knowledge here.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from pytelemetry.core.types import ValueType

__all__ = ["Channel", "default_channels", "DEFAULT_LIVE_VARS"]


@dataclass(frozen=True, slots=True)
class Channel:
    key: str
    type: ValueType
    fn: Callable[[float], int | float | bool | str]
    period_s: float = 0.05  # 20 Hz default

    def sample(self, t: float) -> tuple[str, ValueType, int | float | bool | str]:
        return self.key, self.type, self.fn(t)


def default_channels() -> list[Channel]:
    return [
        Channel("Voltage", ValueType.FLOAT, lambda t: round(12.0 + 0.5 * math.sin(t * 2.0), 4)),
        Channel("Current", ValueType.FLOAT, lambda t: round(1.5 + 0.3 * math.sin(t * 3.1 + 1.0), 4)),
        Channel("RPM", ValueType.INT32, lambda t: int(3000 + 1500 * math.sin(t * 0.7))),
        Channel("Ticks", ValueType.UINT32, lambda t: int(t * 1000) & 0xFFFFFFFF, period_s=0.1),
        Channel("Temp", ValueType.FLOAT, lambda t: round(40.0 + 5.0 * math.sin(t * 0.25), 4), period_s=0.2),
        Channel("Mode", ValueType.STRING, lambda t: "RUN" if int(t) % 2 == 0 else "IDLE", period_s=1.0),
    ]


# (id, ValueType, initial value, name, unit) — names/units are host-side only (not on the wire).
DEFAULT_LIVE_VARS: list[tuple[int, ValueType, int | float | bool, str, str]] = [
    (1, ValueType.FLOAT, 3.0, "Pitch", "deg"),
    (2, ValueType.INT32, 10, "Gain", ""),
    (3, ValueType.BOOL, True, "Enable", ""),
    (4, ValueType.UINT32, 4000, "Limit", "rpm"),
]
