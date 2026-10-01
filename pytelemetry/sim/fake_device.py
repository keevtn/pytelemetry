"""Faithful Python port of firmware/Dashboard.c device behaviour. Owner: test-engineer.

Mirrors the rx state machine and the exact reply chatter in docs/PROTOCOL.md section 7, verified
byte-for-byte against the golden "exchange" vectors. Host->device framing is raw (no COBS); every
device->host frame this emits is COBS-encoded with a trailing 0x00, exactly like the firmware.
"""

from __future__ import annotations

from dataclasses import dataclass

from pytelemetry.core.protocol import codec
from pytelemetry.core.protocol.crc import crc16, crc32
from pytelemetry.core.types import HEADER_SIZE, MAX_LIVE_VARS, PacketType, ValueType

# kAlertBufCOBSize in firmware: 100 + 100/254 + 1 = 101. A frame whose total size >= this is "too large".
_MAX_TOTAL = 101

_WAITING = 0
_HEADER_RECEIVED = 1


@dataclass
class _LiveVar:
    var_id: int
    value_type: int
    value: int | float | bool


class FakeDevice:
    """One simulated microcontroller. Register live vars, feed host bytes, collect device replies."""

    def __init__(self) -> None:
        self._rx = bytearray()
        self._status = _WAITING
        self._header: bytes = b""
        self._live: list[_LiveVar] = []
        self._out: list[bytes] = []

    # ---- live-var registry (firmware: Dashboard_Register_LiveData, max 5) ------------------------

    def register_live(self, var_id: int, value_type: int, value: int | float | bool) -> None:
        if len(self._live) >= MAX_LIVE_VARS:
            return
        self._live.append(_LiveVar(var_id, value_type, value))

    def live_value(self, var_id: int) -> int | float | bool | None:
        for v in self._live:
            if v.var_id == var_id:
                return v.value
        return None

    def live_snapshot(self) -> dict[int, int | float | bool]:
        return {v.var_id: v.value for v in self._live}

    # ---- device->host emitters (each appends one COBS frame) -------------------------------------

    def _alert(self, message: str) -> None:
        frame = codec.encode_alert(message)
        if frame is not None:
            self._out.append(frame)

    def _telemetry_u32(self, key: str, value: int) -> None:
        frame = codec.encode_telemetry(key, ValueType.UINT32, value & 0xFFFFFFFF)
        if frame is not None:
            self._out.append(frame)

    def telemetry(self, key: str, value_type: int, value: int | float | bool | str) -> list[bytes]:
        """Proactively emit one telemetry frame (used by scripted channels). Returns the frames emitted."""
        before = len(self._out)
        frame = codec.encode_telemetry(key, value_type, value)
        if frame is not None:
            self._out.append(frame)
        out = self._out[before:]
        return out

    def alert(self, message: str) -> list[bytes]:
        before = len(self._out)
        self._alert(message)
        return self._out[before:]

    # ---- rx state machine (firmware: Dashboard_Update) ------------------------------------------

    def feed(self, data: bytes) -> list[bytes]:
        """Feed raw host bytes; return every device frame emitted in response, in order."""
        self._rx += data
        before = len(self._out)
        while self._step():
            pass
        return self._out[before:]

    def _step(self) -> bool:
        """One Dashboard_Update pass. Returns True if it made progress (so the caller loops)."""
        progressed = False
        if self._status == _WAITING and len(self._rx) > HEADER_SIZE:
            header = bytes(self._rx[:HEADER_SIZE])
            del self._rx[:HEADER_SIZE]
            progressed = True
            # header CRC over bytes 0..9
            if crc16(header[:10]) == int.from_bytes(header[10:12], "little"):
                key_size = int.from_bytes(header[2:4], "little")
                value_size = int.from_bytes(header[4:6], "little")
                total = HEADER_SIZE + key_size + value_size + 4
                if total < _MAX_TOTAL:
                    self._alert("Received packet header")
                    self._header = header
                    self._status = _HEADER_RECEIVED
                else:
                    self._alert("Received packet too large")
            # bad header CRC: consumed silently; next bytes get misparsed as a header on a later pass
        if self._status == _HEADER_RECEIVED:
            key_size = int.from_bytes(self._header[2:4], "little")
            value_size = int.from_bytes(self._header[4:6], "little")
            need = key_size + value_size + 4
            if len(self._rx) >= need:
                body = bytes(self._rx[:need])
                del self._rx[:need]
                self._status = _WAITING
                progressed = True
                key = body[:key_size]
                value = body[key_size : key_size + value_size]
                tail = int.from_bytes(body[key_size + value_size : need], "little")
                calc = crc32(value, crc32(key))
                self._telemetry_u32("CalculuatedCRC", calc)  # firmware's spelling, kept on purpose
                self._telemetry_u32("ReceivedCRC", tail)
                if calc == tail:
                    self._alert("Processing packet")
                    self._process(self._header, key, value)
                else:
                    self._alert("Payload checksum mismatch")
        return progressed

    def _process(self, header: bytes, key: bytes, value: bytes) -> None:
        packet_type = header[0]
        if packet_type == PacketType.REQUEST_LIVE_DATA:
            self._alert("Live Data Requested")
            items = tuple((v.var_id, v.value_type, v.value) for v in self._live)
            frame = codec.encode_response_live_data(items)
            if frame is not None:
                self._out.append(frame)
        elif packet_type == PacketType.MODIFY:
            self._alert("Live Data Modify Received")
            if len(key) < codec.LIVE_DATA_STRUCT.size:
                return
            var_id, vtype, raw4 = codec.LIVE_DATA_STRUCT.unpack_from(key, 0)
            for v in self._live:
                if v.var_id == var_id:
                    if v.value_type != vtype:
                        self._alert("Live Data Type Mismatch")
                        return
                    decoded = codec.unpack_live_value(vtype, raw4)
                    if decoded is not None:
                        v.value = decoded
                    return
            # unknown id: generic alert already sent, value left untouched
