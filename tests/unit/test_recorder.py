"""CSV recorder. Owner: core-engineer."""

from __future__ import annotations

from pathlib import Path

from pytelemetry.core.recorder import CsvRecorder
from pytelemetry.core.types import Telemetry, ValueType


def test_records_rows_and_adds_columns(tmp_path: Path) -> None:
    out = tmp_path / "log.csv"
    with CsvRecorder(out) as rec:
        rec.on_telemetry(Telemetry("Voltage", ValueType.FLOAT, 12.5, 1.0))
        rec.on_telemetry(Telemetry("RPM", ValueType.INT32, 3000, 1.1))
        rec.on_telemetry(Telemetry("Voltage", ValueType.FLOAT, 12.6, 1.2))
    lines = out.read_text().splitlines()
    assert lines[0] == "t"
    assert any(line.startswith("# columns:") for line in lines)
    data_rows = [ln for ln in lines if not ln.startswith(("t", "# columns:"))]
    assert len(data_rows) == 3
    assert data_rows[0].startswith("1.000000")
    assert "12.5" in data_rows[0]


def test_stop_closes_file(tmp_path: Path) -> None:
    out = tmp_path / "log.csv"
    rec = CsvRecorder(out)
    rec.start()
    rec.on_telemetry(Telemetry("X", ValueType.UINT32, 7, 0.5))
    rec.stop()
    rec.on_telemetry(Telemetry("X", ValueType.UINT32, 8, 0.6))  # after stop: ignored, no crash
    assert out.exists()
    assert "7" in out.read_text()
