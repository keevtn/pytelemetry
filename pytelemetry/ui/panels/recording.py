"""CSV recording panel. Owner: ui-engineer.

Wraps core.recorder.CsvRecorder and registers it as a sink on the active session so rows are written off the
reader thread. Default path ~/PyTelemetryLogs/pytelemetry_<timestamp>.csv.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.recorder import CsvRecorder

__all__ = ["RecordingPanel"]


def _default_path() -> str:
    folder = Path.home() / "PyTelemetryLogs"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(folder / f"pytelemetry_{stamp}.csv")


class RecordingPanel(QWidget):
    recordingChanged = Signal(bool)  # MainWindow adds/removes the recorder as a session sink

    def __init__(self) -> None:
        super().__init__()
        self._recorder: CsvRecorder | None = None
        self._start_t = 0.0

        self.path = QLineEdit(_default_path())
        browse = QPushButton("…")
        browse.setFixedWidth(28)
        browse.clicked.connect(self._browse)
        self.button = QPushButton("Start recording")
        self.button.setCheckable(True)
        self.button.toggled.connect(self._toggle)
        self.info = QLabel("idle")

        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)

        root = QVBoxLayout(self)
        root.addLayout(path_row)
        root.addWidget(self.button)
        root.addWidget(self.info)
        root.addStretch(1)

    @property
    def recorder(self) -> CsvRecorder | None:
        return self._recorder

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getSaveFileName(self, "Record to CSV", self.path.text(), "CSV (*.csv)")
        if chosen:
            self.path.setText(chosen)

    def _toggle(self, on: bool) -> None:
        if on:
            path = Path(self.path.text())
            path.parent.mkdir(parents=True, exist_ok=True)
            self._recorder = CsvRecorder(path)
            self._recorder.start()
            self._start_t = time.monotonic()
            self.button.setText("Stop recording")
            self.recordingChanged.emit(True)
        else:
            self.recordingChanged.emit(False)
            if self._recorder is not None:
                self._recorder.stop()
                self._recorder = None
            self.button.setText("Start recording")
            self.info.setText("idle")

    def refresh(self) -> None:
        if self._recorder is not None:
            self.info.setText(f"recording • {time.monotonic() - self._start_t:0.0f}s")
