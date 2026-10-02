"""CSV recorder. Owner: core-engineer.

Wide format, host-timestamped, one row per telemetry sample (PROTOCOL.md / kickoff default 3). New channels
seen mid-recording add a column; earlier rows keep empty cells for it. Runs on the reader thread, so rows are
buffered and flushed at most every FLUSH_INTERVAL_S (and on stop) rather than per row: a per-row flush is a
syscall on every sample and throttles the reader near the 2k frames/s target. A crash loses at most the last
~FLUSH_INTERVAL_S of rows.
"""

from __future__ import annotations

import csv
import threading
import time
from pathlib import Path
from typing import Any, TextIO

from pytelemetry.core.types import Telemetry

__all__ = ["CsvRecorder"]

FLUSH_INTERVAL_S = 0.5


class CsvRecorder:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._fh: TextIO | None = None
        self._writer: Any = None  # csv.writer is a function, not a type; Any keeps mypy --strict happy
        self._columns: list[str] = ["t"]
        self._lock = threading.Lock()
        self._last_flush = 0.0

    def start(self) -> None:
        with self._lock:
            self._fh = self._path.open("w", newline="", encoding="utf-8")
            self._writer = csv.writer(self._fh)
            self._writer.writerow(self._columns)
            self._fh.flush()
            self._last_flush = time.monotonic()

    def on_telemetry(self, item: Telemetry) -> None:
        with self._lock:
            if self._writer is None or self._fh is None:
                return
            if item.key not in self._columns:
                self._columns.append(item.key)
                self._writer.writerow(["# columns:", *self._columns])
            row = [""] * len(self._columns)
            row[0] = f"{item.t:.6f}"
            row[self._columns.index(item.key)] = str(item.value)
            self._writer.writerow(row)
            now = time.monotonic()
            if now - self._last_flush >= FLUSH_INTERVAL_S:  # periodic, not per-row (reader-thread hot path)
                self._fh.flush()
                self._last_flush = now

    def stop(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.flush()  # final flush so the tail of the recording isn't lost
                self._fh.close()
                self._fh = None
                self._writer = None

    def __enter__(self) -> CsvRecorder:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
