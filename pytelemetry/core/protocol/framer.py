"""Device->host stream framer (docs/PROTOCOL.md section 2). Owner: protocol-engineer.

Splits on 0x00, COBS-decodes, validates. Bad chunks are dropped and counted; the stream
resynchronises at the next delimiter. Chunking of the input never changes the output.
"""

from __future__ import annotations

from pytelemetry.core.protocol import cobs
from pytelemetry.core.protocol.codec import parse_header
from pytelemetry.core.protocol.crc import crc32
from pytelemetry.core.types import HEADER_SIZE, TAIL_SIZE, Frame, LinkStats

__all__ = ["StreamFramer"]

_MAX_BUFFER = 4096  # a legal encoded frame is <= 101 bytes; anything near this is garbage


class StreamFramer:
    def __init__(self) -> None:
        self._buf = bytearray()
        self._rx_bytes = 0
        self._frames_ok = 0
        self._dropped = 0
        self._header_crc = 0
        self._payload_crc = 0
        self._length = 0
        self._cobs = 0
        self._resyncs = 0

    def feed(self, data: bytes) -> list[Frame]:
        self._rx_bytes += len(data)
        self._buf += data
        frames: list[Frame] = []
        while True:
            cut = self._buf.find(0)
            if cut < 0:
                if len(self._buf) > _MAX_BUFFER:
                    self._buf.clear()
                    self._resyncs += 1
                return frames
            chunk = bytes(self._buf[:cut])
            del self._buf[: cut + 1]
            if not chunk:
                continue
            frame = self._decode(chunk)
            if frame is not None:
                self._frames_ok += 1
                frames.append(frame)
            else:
                self._dropped += 1

    def _decode(self, chunk: bytes) -> Frame | None:
        raw = cobs.decode(chunk)
        if raw is None:
            self._cobs += 1
            return None
        header = parse_header(raw)
        if header is None:
            self._header_crc += 1
            return None
        expected = HEADER_SIZE + header.key_size + header.value_size + TAIL_SIZE
        if len(raw) != expected:
            self._length += 1
            return None
        key = raw[HEADER_SIZE : HEADER_SIZE + header.key_size]
        value = raw[HEADER_SIZE + header.key_size : expected - TAIL_SIZE]
        tail = int.from_bytes(raw[expected - TAIL_SIZE :], "little")
        if crc32(value, crc32(key)) != tail:
            self._payload_crc += 1
            return None
        return Frame(header, key, value, tail)

    @property
    def stats(self) -> LinkStats:
        return LinkStats(
            rx_bytes=self._rx_bytes,
            frames_ok=self._frames_ok,
            frames_dropped=self._dropped,
            header_crc_errors=self._header_crc,
            payload_crc_errors=self._payload_crc,
            length_errors=self._length,
            cobs_errors=self._cobs,
            resyncs=self._resyncs,
        )
