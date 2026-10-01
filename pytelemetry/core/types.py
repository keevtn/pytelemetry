"""Shared value types for the PyTelemetry v1 wire protocol. Contract: docs/PROTOCOL.md. Owner: lead."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

HEADER_SIZE = 12
TAIL_SIZE = 4
LIVE_DATA_PACKET_SIZE = 8
MAX_DEVICE_FRAME_RAW = 99  # 12 + key + value + 4; key + value <= 83
MAX_HOST_FRAME_RAW = 100
MAX_LIVE_VARS = 5


class PacketType(IntEnum):
    TELEMETRY = 0x30
    ALERT = 0x31
    MODIFY = 0x32
    REQUEST_LIVE_DATA = 0x33
    RESPONSE_LIVE_DATA = 0x34


class ValueType(IntEnum):
    UINT32 = 0
    INT32 = 1
    FLOAT = 2
    BOOL = 3
    STRING = 4


@dataclass(frozen=True, slots=True)
class Header:
    packet_type: int
    content_type: int
    key_size: int
    value_size: int
    timestamp: int
    checksum: int


@dataclass(frozen=True, slots=True)
class Frame:
    """One validated wire frame: header + raw key/value bytes + payload CRC."""

    header: Header
    key: bytes
    value: bytes
    tail: int


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Latest value of a named channel. `t` is the host receive timestamp (time.monotonic())."""

    key: str
    type: ValueType
    value: int | float | bool | str
    t: float


@dataclass(frozen=True, slots=True)
class Alert:
    """Free-text device event. `debug` marks known firmware chatter (PROTOCOL section 7)."""

    message: str
    t: float
    debug: bool = False


@dataclass(frozen=True, slots=True)
class LiveVar:
    """Firmware variable addressed by u16 id. Name/unit/limits come from config, never the wire."""

    id: int
    type: ValueType
    value: int | float | bool
    name: str | None = None
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True, slots=True)
class LinkStats:
    """Counters since connect. Errors are counted, not raised (CLAUDE.md conventions)."""

    rx_bytes: int = 0
    tx_bytes: int = 0
    frames_ok: int = 0
    frames_dropped: int = 0
    header_crc_errors: int = 0
    payload_crc_errors: int = 0
    length_errors: int = 0
    cobs_errors: int = 0
    resyncs: int = 0


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Display metadata for one live-var id, from pytelemetry.toml."""

    id: int
    name: str
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True, slots=True)
class AppConfig:
    """pytelemetry.toml contents."""

    port: str = ""
    baud: int = 115200
    history_samples: int = 100_000
    live_vars: tuple[ChannelConfig, ...] = field(default=())
