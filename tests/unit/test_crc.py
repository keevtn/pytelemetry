"""CRC check values and identities (PROTOCOL.md section 5). Owner: protocol-engineer."""

from __future__ import annotations

import zlib

from hypothesis import given
from hypothesis import strategies as st

from pytelemetry.core.protocol.crc import crc16, crc16_bitwise, crc32, crc32_bitwise

CHECK = b"123456789"


def test_check_values() -> None:
    assert crc16(CHECK) == 0xBB3D
    assert crc16_bitwise(CHECK) == 0xBB3D
    assert crc32(CHECK) == 0x2DFD2D88
    assert crc32_bitwise(CHECK) == 0x2DFD2D88
    assert crc32(b"") == 0
    assert crc16(b"") == 0


@given(st.binary(max_size=300))
def test_fast_paths_match_bitwise_reference(data: bytes) -> None:
    assert crc16(data) == crc16_bitwise(data)
    assert crc32(data) == crc32_bitwise(data)


@given(st.binary(max_size=300), st.integers(min_value=0, max_value=0xFFFFFFFF))
def test_zlib_identity(data: bytes, seed: int) -> None:
    assert crc32(data, seed) == (zlib.crc32(data, seed ^ 0xFFFFFFFF) ^ 0xFFFFFFFF)


@given(st.binary(max_size=200), st.binary(max_size=200))
def test_chaining_is_concatenation(a: bytes, b: bytes) -> None:
    assert crc32(b, crc32(a)) == crc32(a + b)
    assert crc16(b, crc16(a)) == crc16(a + b)
