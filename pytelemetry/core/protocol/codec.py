"""Frame encode/decode for PyTelemetry v1 (docs/PROTOCOL.md sections 3-5). Owner: protocol-engineer.

Pure functions, stdlib only. Malformed input returns None; callers count drops (never raise in the hot path).
Device->host frames are COBS-wrapped by the caller (framer/sim); host->device frames are raw.
"""

from __future__ import annotations

import struct

from pytelemetry.core.protocol import cobs
from pytelemetry.core.protocol.crc import crc16, crc32
from pytelemetry.core.types import (
    HEADER_SIZE,
    MAX_DEVICE_FRAME_RAW,
    TAIL_SIZE,
    Frame,
    Header,
    PacketType,
    ValueType,
)

__all__ = [
    "HEADER_STRUCT",
    "TAIL_STRUCT",
    "LIVE_DATA_STRUCT",
    "build_header",
    "parse_header",
    "decode_chunk",
    "decode_value",
    "pack_live_value",
    "unpack_live_value",
    "parse_live_data",
    "encode_device_raw",
    "encode_telemetry",
    "encode_alert",
    "encode_response_live_data",
    "encode_request_live_data",
    "encode_modify",
]

HEADER_STRUCT = struct.Struct("<BBHHIH")
TAIL_STRUCT = struct.Struct("<I")
LIVE_DATA_STRUCT = struct.Struct("<HH4s")

_F32 = struct.Struct("<f")
_I32 = struct.Struct("<i")
_U32 = struct.Struct("<I")


def build_header(packet_type: int, content_type: int, key_size: int, value_size: int) -> bytes:
    body = HEADER_STRUCT.pack(packet_type, content_type, key_size, value_size, 0, 0)[:10]
    return body + struct.pack("<H", crc16(body))


def parse_header(data: bytes) -> Header | None:
    if len(data) < HEADER_SIZE:
        return None
    ptype, ctype, ksize, vsize, ts, csum = HEADER_STRUCT.unpack_from(data)
    if crc16(data[:10]) != csum:
        return None
    return Header(ptype, ctype, ksize, vsize, ts, csum)


def decode_chunk(raw: bytes) -> Frame | None:
    """One COBS-decoded device->host chunk -> validated Frame. None on any header/length/payload failure."""
    header = parse_header(raw)
    if header is None:
        return None
    expected = HEADER_SIZE + header.key_size + header.value_size + TAIL_SIZE
    if len(raw) != expected:
        return None
    key = raw[HEADER_SIZE : HEADER_SIZE + header.key_size]
    value = raw[HEADER_SIZE + header.key_size : expected - TAIL_SIZE]
    (tail,) = TAIL_STRUCT.unpack_from(raw, expected - TAIL_SIZE)
    if crc32(value, crc32(key)) != tail:
        return None
    return Frame(header, key, value, tail)


def decode_value(value_type: int, data: bytes) -> int | float | bool | str | None:
    """4-byte numerics / byte-0 bool / UTF-8 string. None on wrong size (host rejects, like the C++ UI)."""
    if value_type == ValueType.STRING:
        return data.decode("utf-8", errors="replace")
    if len(data) != 4:
        return None
    if value_type == ValueType.FLOAT:
        return float(_F32.unpack(data)[0])
    if value_type == ValueType.INT32:
        return int(_I32.unpack(data)[0])
    if value_type == ValueType.UINT32:
        return int(_U32.unpack(data)[0])
    if value_type == ValueType.BOOL:
        return data[0] != 0
    return None


def pack_live_value(value_type: int, value: int | float | bool) -> bytes:
    """4-byte union, zero-filled for bool (the CRC covers all four bytes)."""
    if value_type == ValueType.FLOAT:
        return _F32.pack(float(value))
    if value_type == ValueType.INT32:
        return _I32.pack(int(value))
    if value_type == ValueType.UINT32:
        return _U32.pack(int(value))
    if value_type == ValueType.BOOL:
        return bytes([1 if value else 0, 0, 0, 0])
    raise ValueError(f"not a live-var type: {value_type}")


def unpack_live_value(value_type: int, data: bytes) -> int | float | bool | None:
    if value_type == ValueType.BOOL:
        return data[0] != 0
    return decode_value(value_type, data)  # type: ignore[return-value]


def parse_live_data(value: bytes) -> tuple[tuple[int, int, int | float | bool], ...] | None:
    """Response_LiveData value -> ((id, value_type, value), ...). None if not a multiple of 8 or bad type."""
    if len(value) % LIVE_DATA_STRUCT.size:
        return None
    out: list[tuple[int, int, int | float | bool]] = []
    for off in range(0, len(value), LIVE_DATA_STRUCT.size):
        var_id, vtype, raw4 = LIVE_DATA_STRUCT.unpack_from(value, off)
        decoded = unpack_live_value(vtype, raw4)
        if decoded is None:
            return None
        out.append((var_id, vtype, decoded))
    return tuple(out)


def encode_device_raw(packet_type: int, content_type: int, key: bytes, value: bytes) -> bytes | None:
    """header+key+value+tail, then COBS + delimiter. None when raw > 99 bytes (firmware refuses to send)."""
    raw_size = HEADER_SIZE + len(key) + len(value) + TAIL_SIZE
    if raw_size > MAX_DEVICE_FRAME_RAW:
        return None
    raw = build_header(packet_type, content_type, len(key), len(value)) + key + value
    raw += TAIL_STRUCT.pack(crc32(value, crc32(key)))
    return cobs.encode(raw)


def encode_telemetry(key: str, value_type: int, value: int | float | bool | str) -> bytes | None:
    kb = key.encode("ascii")
    vb = value.encode("utf-8") if value_type == ValueType.STRING else pack_live_value(value_type, value)  # type: ignore[arg-type]
    return encode_device_raw(PacketType.TELEMETRY, value_type, kb, vb)


def encode_alert(message: str) -> bytes | None:
    return encode_device_raw(PacketType.ALERT, ValueType.STRING, b"", message.encode("utf-8"))


def encode_response_live_data(items: tuple[tuple[int, int, int | float | bool], ...]) -> bytes | None:
    value = b"".join(
        LIVE_DATA_STRUCT.pack(var_id, vtype, pack_live_value(vtype, val)) for var_id, vtype, val in items
    )
    return encode_device_raw(PacketType.RESPONSE_LIVE_DATA, ValueType.UINT32, b"", value)


def encode_request_live_data() -> bytes:
    """16-byte raw host frame; empty payload tail is crc32(b'') == 0."""
    return build_header(PacketType.REQUEST_LIVE_DATA, 0, 0, 0) + TAIL_STRUCT.pack(0)


def encode_modify(var_id: int, value_type: int, value: int | float | bool) -> bytes:
    """24-byte raw host frame: one LiveDataPacket as the key (keySize=8, valueSize=0)."""
    packet = LIVE_DATA_STRUCT.pack(var_id, value_type, pack_live_value(value_type, value))
    header = build_header(PacketType.MODIFY, value_type, len(packet), 0)
    return header + packet + TAIL_STRUCT.pack(crc32(packet))
