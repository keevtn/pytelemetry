"""Session: owns the serial I/O thread, decodes frames, dispatches events. Owner: core-engineer.

Serial reads run on one background thread (CLAUDE.md thread rule); decoded events fan out through the
EventBus to sinks. Host->device writes (request/modify) go out in a single transport.write() each, as the
firmware requires. Nothing here imports Qt.
"""

from __future__ import annotations

import logging
import threading
import time

from pytelemetry.core.events import EventBus
from pytelemetry.core.interfaces import EventSink, Transport
from pytelemetry.core.protocol import codec
from pytelemetry.core.protocol.framer import StreamFramer
from pytelemetry.core.types import (
    Alert,
    ChannelConfig,
    Frame,
    LinkStats,
    LiveVar,
    PacketType,
    Telemetry,
    ValueType,
)

__all__ = ["Session", "DEVICE_DEBUG_ALERTS"]

_log = logging.getLogger(__name__)

# Firmware chatter (PROTOCOL.md section 7): surfaced at lower severity than user-facing alerts.
DEVICE_DEBUG_ALERTS = frozenset(
    {
        "Received packet header",
        "Received packet too large",
        "Processing packet",
        "Live Data Requested",
        "Live Data Modify Received",
        "Live Data Type Mismatch",
        "Payload checksum mismatch",
    }
)


class Session:
    def __init__(
        self,
        transport: Transport,
        live_var_config: dict[int, ChannelConfig] | None = None,
        poll_chunk: int = 4096,
    ) -> None:
        self._transport = transport
        self._bus = EventBus()
        self._framer = StreamFramer()
        self._cfg = live_var_config or {}
        self._chunk = poll_chunk
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tx_bytes = 0

    def add_sink(self, sink: EventSink) -> None:
        self._bus.add_sink(sink)

    def start(self) -> None:
        if self._thread is not None:
            return
        if not self._transport.is_open:
            self._transport.open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pytelemetry-reader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._transport.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data = self._transport.read(self._chunk)
            except Exception:
                _log.exception("transport.read failed; stopping reader")
                return
            if not data:
                time.sleep(0.001)
                continue
            for frame in self._framer.feed(data):
                self._dispatch(frame)
            self._bus.emit_stats(self.stats)

    def _dispatch(self, frame: Frame) -> None:
        ptype = frame.header.packet_type
        now = time.monotonic()
        if ptype == PacketType.TELEMETRY:
            value = codec.decode_value(frame.header.content_type, frame.value)
            if value is None:
                return
            key = frame.key.decode("ascii", errors="replace")
            self._bus.emit_telemetry(Telemetry(key, ValueType(frame.header.content_type), value, now))
        elif ptype == PacketType.ALERT:
            msg = frame.value.decode("utf-8", errors="replace")
            self._bus.emit_alert(Alert(msg, now, debug=msg in DEVICE_DEBUG_ALERTS))
        elif ptype == PacketType.RESPONSE_LIVE_DATA:
            parsed = codec.parse_live_data(frame.value)
            if parsed is None:
                return
            self._bus.emit_live_data(tuple(self._to_livevar(i, t, v) for i, t, v in parsed))

    def _to_livevar(self, var_id: int, vtype: int, value: int | float | bool) -> LiveVar:
        cfg = self._cfg.get(var_id)
        return LiveVar(
            id=var_id,
            type=ValueType(vtype),
            value=value,
            name=cfg.name if cfg else None,
            unit=cfg.unit if cfg else None,
            minimum=cfg.minimum if cfg else None,
            maximum=cfg.maximum if cfg else None,
        )

    # ---- host -> device --------------------------------------------------------------------------

    def request_live_data(self) -> None:
        self._write(codec.encode_request_live_data())

    def modify_live_var(self, var_id: int, value_type: int, value: int | float | bool) -> None:
        self._write(codec.encode_modify(var_id, value_type, value))

    def _write(self, frame: bytes) -> None:
        self._tx_bytes += self._transport.write(frame)

    @property
    def stats(self) -> LinkStats:
        base = self._framer.stats
        return LinkStats(
            rx_bytes=base.rx_bytes,
            tx_bytes=self._tx_bytes,
            frames_ok=base.frames_ok,
            frames_dropped=base.frames_dropped,
            header_crc_errors=base.header_crc_errors,
            payload_crc_errors=base.payload_crc_errors,
            length_errors=base.length_errors,
            cobs_errors=base.cobs_errors,
            resyncs=base.resyncs,
        )
