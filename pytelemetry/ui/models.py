"""Qt item models that read the store without copying whole arrays. Owner: ui-engineer."""

from __future__ import annotations

import time

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

from pytelemetry.core.store import TelemetryStore
from pytelemetry.core.types import ValueType

__all__ = ["TelemetryTableModel"]

_HEADERS = ["Channel", "Value", "Type", "Age (s)"]
_STALE_AFTER = 2.0


class TelemetryTableModel(QAbstractTableModel):
    """One row per channel, refreshed on the UI timer via refresh() (no per-event signals)."""

    def __init__(self, store: TelemetryStore) -> None:
        super().__init__()
        self._store = store
        self._keys: list[str] = []
        self._mono = QFont("monospace")
        self._mono.setStyleHint(QFont.StyleHint.Monospace)

    def refresh(self) -> None:
        keys = self._store.keys()
        if keys != self._keys:
            self.beginResetModel()
            self._keys = keys
            self.endResetModel()
        elif keys:
            self.dataChanged.emit(
                self.index(0, 1), self.index(len(keys) - 1, len(_HEADERS) - 1)
            )

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._keys)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return _HEADERS[section]
        return None

    def channel_at(self, row: int) -> str | None:
        return self._keys[row] if 0 <= row < len(self._keys) else None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        key = self._keys[index.row()]
        item = self._store.latest(key)
        if item is None:
            return None
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return key
            if col == 1:
                return _format_value(item.type, item.value)
            if col == 2:
                return ValueType(item.type).name.lower()
            if col == 3:
                return f"{max(0.0, time.monotonic() - item.t):.1f}"
        elif role == Qt.ItemDataRole.FontRole and col in (1, 3):
            return self._mono
        elif role == Qt.ItemDataRole.ForegroundRole:
            if time.monotonic() - item.t > _STALE_AFTER:
                return QColor("#6b7079")
        return None


def _format_value(value_type: int, value: object) -> str:
    if value_type == ValueType.FLOAT:
        return f"{float(value):.4f}"  # type: ignore[arg-type]
    if value_type == ValueType.BOOL:
        return "true" if value else "false"
    return str(value)
