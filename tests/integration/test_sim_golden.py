"""The simulator reproduces the firmware's reply chatter byte-for-byte. Owner: test-engineer.

This is the oracle for PROTOCOL.md section 7: for each golden "exchange", feed the device the host frame the
entry describes and assert the emitted frames equal the recorded wire bytes exactly, in order.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytelemetry.core.protocol import codec
from pytelemetry.core.types import ValueType
from pytelemetry.sim.fake_device import FakeDevice

VECTORS = json.loads((Path(__file__).parent.parent / "golden" / "vectors.json").read_text())
EXCHANGES = {
    it["name"]: [bytes.fromhex(h) for h in it["wire"]]
    for it in VECTORS["vectors"]
    if it["section"] == "exchange"
}


def _device() -> FakeDevice:
    d = FakeDevice()
    d.register_live(1, ValueType.FLOAT, 1.5)
    d.register_live(2, ValueType.INT32, 10)
    d.register_live(3, ValueType.BOOL, True)
    d.register_live(4, ValueType.UINT32, 4000)
    return d


def _request() -> bytes:
    return codec.encode_request_live_data()


def _corrupt_tail(frame: bytes) -> bytes:
    b = bytearray(frame)
    b[-1] ^= 0xFF
    return bytes(b)


def _corrupt_header(frame: bytes) -> bytes:
    b = bytearray(frame)
    b[2] ^= 0x01  # flip key_size -> header CRC fails
    return bytes(b)


STIMULI = {
    "request_live_data_4_vars": _request(),
    "modify_float_id1_ok": codec.encode_modify(1, ValueType.FLOAT, 3.25),
    "modify_bool_id3_false": codec.encode_modify(3, ValueType.BOOL, False),
    "modify_type_mismatch": codec.encode_modify(2, ValueType.FLOAT, 1.0),
    "modify_unknown_id": codec.encode_modify(9, ValueType.INT32, 5),
    "request_bad_payload_crc": _corrupt_tail(_request()),
    "request_bad_header_crc_silent": _corrupt_header(_request()),
}


@pytest.mark.parametrize("name", list(EXCHANGES))
def test_exchange_replies_byte_exact(name: str) -> None:
    device = _device()
    assert device.feed(STIMULI[name]) == EXCHANGES[name]


def test_final_live_state_matches_golden() -> None:
    device = _device()
    device.feed(codec.encode_modify(1, ValueType.FLOAT, 3.25))
    device.feed(codec.encode_modify(3, ValueType.BOOL, False))
    device.feed(codec.encode_modify(2, ValueType.FLOAT, 1.0))  # type mismatch, gain unchanged
    device.feed(codec.encode_modify(9, ValueType.INT32, 5))  # unknown id, ignored
    assert device.live_snapshot() == {1: 3.25, 2: 10, 3: False, 4: 4000}
    assert VECTORS["final_state"] == {"pitch": 3.25, "gain": 10, "enable": False, "limit": 4000}


def test_byte_split_feed_is_equivalent() -> None:
    whole = _device().feed(STIMULI["request_live_data_4_vars"])
    dev = _device()
    out: list[bytes] = []
    for byte in STIMULI["request_live_data_4_vars"]:
        out += dev.feed(bytes([byte]))
    assert out == whole
