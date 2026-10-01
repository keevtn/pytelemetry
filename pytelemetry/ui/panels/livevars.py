"""Live-var editor panel. Owner: ui-engineer.

One row per live var reported by the device. Edit a value, Apply -> controller.modify_live_var(...). Pending
edits are highlighted; Refresh re-requests from the device. Names/units come from config, not the wire.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.store import TelemetryStore
from pytelemetry.core.types import LiveVar, ValueType

__all__ = ["LiveVarsPanel"]

_COLS = ["Name", "ID", "Type", "Current", "New value"]


class LiveVarsPanel(QWidget):
    def __init__(self, store: TelemetryStore, controller: object) -> None:
        super().__init__()
        self._store = store
        self._controller = controller
        self._ids: list[int] = []

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_request)

        buttons = QHBoxLayout()
        buttons.addWidget(apply_btn)
        buttons.addWidget(refresh)
        buttons.addStretch(1)

        root = QVBoxLayout(self)
        root.addWidget(self.table)
        root.addLayout(buttons)

    def _refresh_request(self) -> None:
        req = getattr(self._controller, "request_live_data", None)
        if callable(req):
            req()

    def refresh(self) -> None:
        live = self._store.live_vars()
        ids = [v.id for v in live]
        if ids != self._ids:
            self._rebuild(live)
        else:
            for row, v in enumerate(live):
                self.table.item(row, 3).setText(_fmt(v))

    def _rebuild(self, live: tuple[LiveVar, ...]) -> None:
        self._ids = [v.id for v in live]
        self.table.setRowCount(len(live))
        for row, v in enumerate(live):
            name = v.name or f"var{v.id}"
            for col, text in enumerate((name, str(v.id), ValueType(v.type).name.lower(), _fmt(v))):
                item = QTableWidgetItem(text)
                if col != 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)
            editor = QTableWidgetItem("")
            self.table.setItem(row, 4, editor)

    def _apply(self) -> None:
        live = {v.id: v for v in self._store.live_vars()}
        modify = getattr(self._controller, "modify_live_var", None)
        if not callable(modify):
            return
        for row, var_id in enumerate(self._ids):
            cell = self.table.item(row, 4)
            if cell is None or not cell.text().strip():
                continue
            var = live.get(var_id)
            if var is None:
                continue
            value = _parse(var.type, cell.text().strip())
            if value is None:
                continue
            value = _clamp(var, value)
            modify(var_id, int(var.type), value)
            cell.setText("")


def _fmt(v: LiveVar) -> str:
    if v.type == ValueType.FLOAT:
        return f"{float(v.value):.4f}"  # type: ignore[arg-type]
    if v.type == ValueType.BOOL:
        return "true" if v.value else "false"
    return str(v.value)


def _parse(value_type: int, text: str) -> int | float | bool | None:
    try:
        if value_type == ValueType.FLOAT:
            return float(text)
        if value_type == ValueType.BOOL:
            return text.lower() in ("1", "true", "on", "yes")
        if value_type in (ValueType.INT32, ValueType.UINT32):
            return int(text, 0)
    except ValueError:
        return None
    return None


def _clamp(var: LiveVar, value: int | float | bool) -> int | float | bool:
    if isinstance(value, bool) or var.type == ValueType.BOOL:
        return value
    if var.minimum is not None and value < var.minimum:
        return type(value)(var.minimum)
    if var.maximum is not None and value > var.maximum:
        return type(value)(var.maximum)
    return value
