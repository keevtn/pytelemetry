"""COBS encode/decode (PROTOCOL.md section 2). Owner: protocol-engineer."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from pytelemetry.core.protocol.cobs import decode, encode


def test_known_encodings_match_firmware() -> None:
    # Traced from firmware/COBS.c; cross-checked against the compiled library.
    assert encode(b"A") == bytes.fromhex("024100")
    assert encode(b"\x00") == bytes.fromhex("010100")
    assert encode(b"A\x00") == bytes.fromhex("02410100")
    assert encode(b"\x00\x00") == bytes.fromhex("01010100")
    assert encode(b"\x11\x22\x00\x33") == bytes.fromhex("0311220233 00".replace(" ", ""))


def test_encoded_form() -> None:
    data = bytes(range(1, 60))
    enc = encode(data)
    assert enc[-1] == 0
    assert 0 not in enc[:-1]


@given(st.binary(min_size=0, max_size=600))
def test_round_trip(data: bytes) -> None:
    enc = encode(data)
    assert enc[-1] == 0 and 0 not in enc[:-1]
    assert decode(enc[:-1]) == data


def test_decode_rejects_malformed() -> None:
    assert decode(b"") is None
    assert decode(bytes.fromhex("0041")) is None  # zero code byte
    assert decode(bytes.fromhex("05414141")) is None  # code promises more than present
