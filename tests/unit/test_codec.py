"""Golden-vector compatibility (PROTOCOL.md section 6): byte-exact against the compiled C library.

Every device->host frame must decode to the stated fields and re-encode to identical bytes;
every host->device frame must encode to identical bytes. Owner: protocol-engineer.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from pytelemetry.core.protocol import codec
from pytelemetry.core.protocol.crc import crc16, crc32
from pytelemetry.core.protocol.framer import StreamFramer
from pytelemetry.core.types import PacketType, ValueType

VECTORS = json.loads((Path(__file__).parent.parent / "golden" / "vectors.json").read_text())
BY_NAME = {item["name"]: item for item in VECTORS["vectors"]}


def wires(name: str) -> list[bytes]:
    return [bytes.fromhex(h) for h in BY_NAME[name]["wire"]]


def decode_one(wire: bytes):
    frames = StreamFramer().feed(wire)
    assert len(frames) == 1, f"expected exactly one frame from {wire.hex()}"
    return frames[0]


def test_check_values_section() -> None:
    cv = VECTORS["check_values"]
    assert crc16(b"123456789") == int(cv["crc16_arc_123456789"], 16)
    assert crc32(b"123456789") == int(cv["crc32_payload_123456789"], 16)
    assert crc32(b"") == int(cv["crc32_payload_empty"], 16)
    assert codec.HEADER_STRUCT.size == cv["sizeof_header"]
    assert codec.LIVE_DATA_STRUCT.size == cv["sizeof_livedata"]
    assert codec.TAIL_STRUCT.size == cv["sizeof_tail"]


@pytest.mark.parametrize(
    "name",
    [
        item["name"]
        for item in VECTORS["vectors"]
        if item["wire"] and item["section"] in ("device_to_host", "exchange")
    ],
)
def test_every_device_frame_reencodes_byte_exact(name: str) -> None:
    for wire in wires(name):
        frame = decode_one(wire)
        rebuilt = codec.encode_device_raw(
            frame.header.packet_type, frame.header.content_type, frame.key, frame.value
        )
        assert rebuilt == wire


SEMANTIC_DEVICE = [
    ("telemetry_float", "Voltage", ValueType.FLOAT, 12.5),
    ("telemetry_int32_negative", "RPM", ValueType.INT32, -42),
    ("telemetry_uint32_with_zero_bytes", "Ticks", ValueType.UINT32, 0x01000200),
    ("telemetry_uint32_zero", "Z", ValueType.UINT32, 0),
    ("telemetry_string", "Mode", ValueType.STRING, "RUN"),
    ("telemetry_string_empty_value", "E", ValueType.STRING, ""),
    ("telemetry_string_max_size", "k", ValueType.STRING, "x" * 82),
]


@pytest.mark.parametrize("name,key,vtype,value", SEMANTIC_DEVICE)
def test_semantic_telemetry_encodes(name: str, key: str, vtype: ValueType, value) -> None:
    assert codec.encode_telemetry(key, vtype, value) == wires(name)[0]


def test_alert_encodes() -> None:
    assert codec.encode_alert("Hello") == wires("alert")[0]


def test_nan_telemetry_decodes_as_nan() -> None:
    # The firmware's NAN bit pattern (0xffc00000) differs from Python's (0x7fc00000); both are NaN.
    frame = decode_one(wires("telemetry_float_nan")[0])
    value = codec.decode_value(frame.header.content_type, frame.value)
    assert isinstance(value, float) and math.isnan(value)


def test_too_large_frame_is_refused() -> None:
    assert codec.encode_telemetry("k", ValueType.STRING, "x" * 83) is None
    assert BY_NAME["telemetry_string_too_large_not_sent"]["wire"] == []


def test_host_frames_byte_exact() -> None:
    assert codec.encode_request_live_data() == wires("request_live_data")[0]
    assert codec.encode_modify(7, ValueType.FLOAT, 3.25) == wires("modify_float_id7")[0]


def test_decoded_fields_of_first_vector() -> None:
    frame = decode_one(wires("telemetry_float")[0])
    assert frame.header.packet_type == PacketType.TELEMETRY
    assert frame.header.content_type == ValueType.FLOAT
    assert frame.key == b"Voltage"
    assert codec.decode_value(frame.header.content_type, frame.value) == 12.5
    assert frame.tail == 0x723391C5


def test_response_live_data_parses() -> None:
    for wire in wires("request_live_data_4_vars"):
        if wire[-1] != 0:
            continue
        frame = decode_one(wire)
        if frame.header.packet_type == PacketType.RESPONSE_LIVE_DATA:
            parsed = codec.parse_live_data(frame.value)
            assert parsed == ((1, 2, 1.5), (2, 1, 10), (3, 3, True), (4, 0, 4000))
            return
    pytest.fail("no Response_LiveData frame in exchange")


def test_numeric_telemetry_rejects_wrong_size() -> None:
    assert codec.decode_value(ValueType.FLOAT, b"\x00" * 3) is None
    assert codec.decode_value(ValueType.UINT32, b"\x00" * 5) is None


def test_bool_live_value_zero_fills_union() -> None:
    assert codec.pack_live_value(ValueType.BOOL, True) == b"\x01\x00\x00\x00"
    assert codec.pack_live_value(ValueType.BOOL, False) == b"\x00\x00\x00\x00"
