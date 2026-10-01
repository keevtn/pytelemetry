"""PyTelemetry checksums (docs/PROTOCOL.md section 5). Owner: protocol-engineer.

crc16: CRC-16/ARC, poly 0xA001 (reflected 0x8005), init 0, no final XOR.
crc32: payload CRC-32, reflected poly 0xEDB88320, init 0, no final XOR.
Bitwise versions are the reference; crc32 ships a zlib-backed fast path tested against it.
"""

from __future__ import annotations

import zlib

__all__ = ["crc16", "crc32", "crc16_bitwise", "crc32_bitwise"]


def crc16_bitwise(data: bytes, crc: int = 0) -> int:
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def crc32_bitwise(data: bytes, crc: int = 0) -> int:
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc & 0xFFFFFFFF


_CRC16_TABLE: list[int] = []
for _n in range(256):
    _c = _n
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _CRC16_TABLE.append(_c)


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        crc = (crc >> 8) ^ _CRC16_TABLE[(crc ^ byte) & 0xFF]
    return crc & 0xFFFF


def crc32(data: bytes, crc: int = 0) -> int:
    # Identity verified in tests: payload crc32 == zlib with pre/post-inverted running value.
    return (zlib.crc32(data, crc ^ 0xFFFFFFFF) ^ 0xFFFFFFFF) & 0xFFFFFFFF
