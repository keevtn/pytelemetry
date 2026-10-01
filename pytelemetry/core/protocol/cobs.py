"""COBS framing (docs/PROTOCOL.md section 2). Owner: protocol-engineer.

encode() appends the 0x00 delimiter, mirroring firmware/COBS.c (byte-identical for all
inputs < 254 bytes; wire frames are <= 99 so the 254-group boundary never occurs on the wire).
decode() takes one chunk WITHOUT its delimiter; returns None on malformed input (callers count, not raise).
"""

from __future__ import annotations

__all__ = ["encode", "decode"]


def encode(data: bytes) -> bytes:
    out = bytearray()
    block = bytearray()

    def flush() -> None:
        out.append(len(block) + 1)
        out.extend(block)
        block.clear()

    for b in data:
        if b == 0:
            flush()
        else:
            block.append(b)
            if len(block) == 254:
                flush()
    flush()
    out.append(0)
    return bytes(out)


def decode(chunk: bytes) -> bytes | None:
    if not chunk:
        return None
    out = bytearray()
    idx = 0
    n = len(chunk)
    while idx < n:
        code = chunk[idx]
        if code == 0:
            return None
        idx += 1
        end = idx + code - 1
        if end > n:
            return None
        out += chunk[idx:end]
        idx = end
        if code != 0xFF and idx < n:
            out.append(0)
    return bytes(out)
