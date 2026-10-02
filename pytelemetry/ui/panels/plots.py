"""Live plot panel (pyqtgraph). Owner: ui-engineer.

One shared-time plot with a multi-select channel list, follow/pause, and a time window. Curves are fed
ring-buffer array views from the store (no per-point appends). Colours are shared with the telemetry table
by channel index.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.store import TelemetryStore
from pytelemetry.ui.theme import color_for_index

__all__ = ["PlotsPanel"]

_WINDOWS = {"1 s": 1.0, "10 s": 10.0, "30 s": 30.0, "1 min": 60.0, "10 min": 600.0}


class PlotsPanel(QWidget):
    def __init__(self, store: TelemetryStore) -> None:
        super().__init__()
        self._store = store
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._color_idx: dict[str, int] = {}
        self._follow = True

        pg.setConfigOptions(antialias=False)
        self._plot = pg.PlotWidget(background="#0e0f12")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setClipToView(True)
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.addLegend()
        self._pw = self._plot.getPlotItem()

        self._channels = QListWidget()
        self._channels.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._channels.setMaximumWidth(160)
        self._channels.itemSelectionChanged.connect(self._sync_curves)

        self._window = QComboBox()
        self._window.addItems(list(_WINDOWS))
        self._window.setCurrentText("30 s")

        self._pause = QPushButton("Pause")
        self._pause.setCheckable(True)
        self._pause.toggled.connect(self._on_pause)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Window"))
        controls.addWidget(self._window)
        controls.addWidget(self._pause)
        controls.addStretch(1)

        right = QVBoxLayout()
        right.addLayout(controls)
        right.addWidget(self._plot, 1)

        root = QHBoxLayout(self)
        root.addWidget(self._channels)
        root.addLayout(right, 1)

    def _on_pause(self, paused: bool) -> None:
        self._follow = not paused
        self._pause.setText("Resume" if paused else "Pause")
        self._plot.setMouseEnabled(x=paused, y=paused)

    def add_channel(self, key: str) -> None:
        """Select a channel for plotting (called from the table's 'plot this').

        Adds the list entry if it isn't there yet, so plotting works even before the first refresh populates
        the channel list. Selecting it triggers _sync_curves, which creates the curve.
        """
        for i in range(self._channels.count()):
            if self._channels.item(i).text() == key:
                self._channels.item(i).setSelected(True)
                return
        item = QListWidgetItem(key)
        self._channels.addItem(item)
        item.setSelected(True)

    def _refresh_channel_list(self) -> None:
        existing = {self._channels.item(i).text() for i in range(self._channels.count())}
        for key in self._store.keys():  # noqa: SIM118 -- TelemetryStore.keys() is a method, not a dict
            if key in existing:
                continue
            # only plottable (numeric) channels have history
            t, _v = self._store.history(key)
            if len(t) == 0 and self._store.latest(key) and isinstance(self._store.latest(key).value, str):
                continue
            self._channels.addItem(QListWidgetItem(key))

    def _selected(self) -> list[str]:
        return [i.text() for i in self._channels.selectedItems()]

    def _sync_curves(self) -> None:
        selected = set(self._selected())
        for key in list(self._curves):
            if key not in selected:
                self._pw.removeItem(self._curves.pop(key))
        for key in selected:
            if key not in self._curves:
                idx = self._color_idx.setdefault(key, len(self._color_idx))
                pen = pg.mkPen(color_for_index(idx), width=1)
                self._curves[key] = self._plot.plot([], [], name=key, pen=pen)

    def refresh(self) -> None:
        self._refresh_channel_list()
        if not self._follow:
            return
        window = _WINDOWS[self._window.currentText()]
        latest_t = 0.0
        for key, curve in self._curves.items():
            t, v = self._store.history(key)
            if len(t):
                curve.setData(t, v)
                latest_t = max(latest_t, float(t[-1]))
        if self._curves and latest_t > 0:
            self._plot.setXRange(latest_t - window, latest_t, padding=0)
