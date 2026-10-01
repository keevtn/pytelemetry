"""Telemetry table panel. Owner: ui-engineer."""

from __future__ import annotations

from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.store import TelemetryStore
from pytelemetry.ui.models import TelemetryTableModel

__all__ = ["TelemetryPanel"]


class TelemetryPanel(QWidget):
    plotChannel = Signal(str)

    def __init__(self, store: TelemetryStore) -> None:
        super().__init__()
        self._model = TelemetryTableModel(store)
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("filter channels…")
        self._filter.textChanged.connect(self._proxy.setFilterFixedString)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._emit_plot)

        root = QVBoxLayout(self)
        root.addWidget(self._filter)
        root.addWidget(self.table)

    def refresh(self) -> None:
        self._model.refresh()

    def _channel_for_row(self, proxy_row_index) -> str | None:
        src = self._proxy.mapToSource(proxy_row_index)
        return self._model.channel_at(src.row())

    def _emit_plot(self, index) -> None:
        key = self._channel_for_row(index)
        if key:
            self.plotChannel.emit(key)

    def _menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        key = self._channel_for_row(index)
        if not key:
            return
        menu = QMenu(self)
        plot = menu.addAction("Plot this channel")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == plot:
            self.plotChannel.emit(key)
