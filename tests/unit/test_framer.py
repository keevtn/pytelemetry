"""Stream framer: chunking invariance, resync, counters, throughput. Owner: protocol-engineer."""

from __future__ import annotations

import time

from hypothesis import given
from hypothesis import strategies as st

from pytelemetry.core.protocol import cobs, codec
from pytelemetry.core.protocol.framer import StreamFramer
from pytelemetry.core.types import ValueType

FRAMES = [
    codec.encode_telemetry("Voltage", ValueType.FLOAT, 12.5),
    codec.encode_alert("Hello"),
    codec.encode_telemetry("RPM", ValueType.INT32, -42),
    codec.encode_telemetry("Mode", ValueType.STRING, "RUN"),
]
STREAM = b"".join(f for f in FRAMES if f is not None)


def contents(frames) -> list[tuple]:
    return [(f.header, f.key, f.value) for f in frames]


REFERENCE = contents(StreamFramer().feed(STREAM))


@given(st.lists(st.integers(min_value=1, max_value=23), min_size=1, max_size=80))
def test_chunking_never_changes_output(sizes: list[int]) -> None:
    framer = StreamFramer()
    got = []
    idx = 0
    for size in sizes * 50:
        if idx >= len(STREAM):
            break
        got += framer.feed(STREAM[idx : idx + size])
        idx += size
    got += framer.feed(STREAM[idx:])
    assert contents(got) == REFERENCE
    assert framer.stats.frames_dropped == 0


def test_garbage_then_resync() -> None:
    framer = StreamFramer()
    framer.feed(bytes(range(1, 200)) + b"\x00")  # junk chunk, then delimiter
    frames = framer.feed(STREAM)
    assert contents(frames) == REFERENCE
    stats = framer.stats
    assert stats.frames_ok == len(REFERENCE)
    assert stats.frames_dropped >= 1


def test_empty_chunks_are_skipped_not_counted() -> None:
    framer = StreamFramer()
    framer.feed(b"\x00\x00\x00")
    assert framer.stats.frames_dropped == 0


def test_payload_corruption_is_counted() -> None:
    wire = FRAMES[0]
    assert wire is not None
    raw = cobs.decode(wire[:-1])
    assert raw is not None
    bad = bytearray(raw)
    bad[-1] ^= 0xFF  # flip tail byte -> payload CRC mismatch
    framer = StreamFramer()
    assert framer.feed(cobs.encode(bytes(bad))) == []
    assert framer.stats.payload_crc_errors == 1


def test_header_corruption_is_counted() -> None:
    wire = FRAMES[0]
    assert wire is not None
    raw = cobs.decode(wire[:-1])
    assert raw is not None
    bad = bytearray(raw)
    bad[2] ^= 0x01  # key_size bit flip -> header CRC mismatch
    framer = StreamFramer()
    assert framer.feed(cobs.encode(bytes(bad))) == []
    assert framer.stats.header_crc_errors == 1


def test_unbounded_garbage_without_delimiter_resyncs() -> None:
    framer = StreamFramer()
    framer.feed(bytes([1]) * 5000)
    assert framer.stats.resyncs == 1
    assert contents(framer.feed(STREAM)) == REFERENCE


def test_throughput_at_least_20k_frames_per_second() -> None:
    blob = STREAM * 5000  # 20,000 frames
    framer = StreamFramer()
    start = time.perf_counter()
    count = 0
    for idx in range(0, len(blob), 4096):
        count += len(framer.feed(blob[idx : idx + 4096]))
    elapsed = time.perf_counter() - start
    assert count == 20_000
    assert count / elapsed > 20_000, f"only {count / elapsed:,.0f} frames/s"
