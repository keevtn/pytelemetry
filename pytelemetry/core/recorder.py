"""CSV recorder. Owner: core-engineer.

Wide format, host-timestamped, one row per telemetry sample (PROTOCOL.md / kickoff default 3). New channels
seen mid-recording add a column; earlier rows keep empty cells for it. Flushed per row so a crash keeps data.
"""

from __future__ import annotations

import csv
import threading
from pathlib import Path
from typing import Any, TextIO

from pytelemetry.core.types import Telemetry

__all__ = ["CsvRecorder"]


class CsvRecorder:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._fh: TextIO | None = None
        self._writer: Any = None  # csv.writer is a function, not a type; Any keeps mypy --strict happy
        self._columns: list[str] = ["t"]
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._fh = self._path.open("w", newline="", encoding="utf-8")
            self._writer = csv.writer(self._fh)
            self._writer.writerow(self._columns)
            self._fh.flush()

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
            self._fh.flush()

    def stop(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
                self._writer = None

    def __enter__(self) -> CsvRecorder:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
