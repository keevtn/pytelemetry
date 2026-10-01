"""Alerts log panel. Owner: ui-engineer.

Timestamped lines; device debug chatter (PROTOCOL.md section 7) is grey and hidden behind a toggle. Autoscroll
pauses when the user scrolls up. Rendered from the store each tick, capped to the store's alert ring.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.store import TelemetryStore

__all__ = ["AlertsPanel"]

_DEBUG_COLOR = QColor("#6b7079")
_ALERT_COLOR = QColor("#e8b84b")


class AlertsPanel(QWidget):
    def __init__(self, store: TelemetryStore) -> None:
        super().__init__()
        self._store = store
        self._seen = 0

        self._show_debug = QCheckBox("Show device debug")
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("filter…")
        self._filter.textChanged.connect(self._rebuild)
        self._show_debug.toggled.connect(self._rebuild)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear)

        controls = QHBoxLayout()
        controls.addWidget(self._show_debug)
        controls.addWidget(self._filter, 1)
        controls.addWidget(clear)

        self.list = QListWidget()
        root = QVBoxLayout(self)
        root.addLayout(controls)
        root.addWidget(self.list)

    def _clear(self) -> None:
        self.list.clear()

    def _at_bottom(self) -> bool:
        bar = self.list.verticalScrollBar()
        return bar.value() >= bar.maximum() - 2

    def _passes(self, message: str, debug: bool) -> bool:
        if debug and not self._show_debug.isChecked():
            return False
        needle = self._filter.text().strip().lower()
        return needle in message.lower() if needle else True

    def refresh(self) -> None:
        alerts = self._store.alerts(limit=5000)
        if len(alerts) == self._seen:
            return
        new = alerts[self._seen :]
        self._seen = len(alerts)
        stick = self._at_bottom()
        for a in new:
            if not self._passes(a.message, a.debug):
                continue
            item = QListWidgetItem(f"[{a.t:9.2f}] {a.message}")
            item.setForeground(_DEBUG_COLOR if a.debug else _ALERT_COLOR)
            self.list.addItem(item)
        if stick:
            self.list.scrollToBottom()

    def _rebuild(self) -> None:
        self.list.clear()
        self._seen = 0
        self.refresh()
