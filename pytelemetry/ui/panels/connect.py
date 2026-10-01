"""Connect panel: port, baud, connect/disconnect, link stats. Owner: ui-engineer."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pytelemetry.core.transport.ports import list_ports
from pytelemetry.core.types import LinkStats

__all__ = ["ConnectPanel"]

_BAUDS = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]


class ConnectPanel(QWidget):
    connectRequested = Signal(str, int)
    disconnectRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._connected = False

        self.port = QComboBox()
        self.port.setEditable(True)  # so socket://host:port can be typed
        self._refresh_ports()
        refresh = QPushButton("↻")
        refresh.setFixedWidth(28)
        refresh.setToolTip("Refresh ports")
        refresh.clicked.connect(self._refresh_ports)

        self.baud = QComboBox()
        self.baud.addItems(_BAUDS)
        self.baud.setCurrentText("115200")

        self.button = QPushButton("Connect")
        self.button.clicked.connect(self._toggle)

        self.status = QLabel("Disconnected")
        self.rate = QLabel("— frames/s")
        self.drops = QLabel("0 drops")

        port_row = QHBoxLayout()
        port_row.addWidget(self.port, 1)
        port_row.addWidget(refresh)

        form = QFormLayout()
        form.addRow("Port", _wrap(port_row))
        form.addRow("Baud", self.baud)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self.button)
        root.addWidget(self.status)
        root.addWidget(self.rate)
        root.addWidget(self.drops)
        root.addStretch(1)

    def _refresh_ports(self) -> None:
        current = self.port.currentText()
        self.port.clear()
        self.port.addItems([p.device for p in list_ports()])
        if current:
            self.port.setCurrentText(current)

    def _toggle(self) -> None:
        if self._connected:
            self.disconnectRequested.emit()
        else:
            url = self.port.currentText().strip()
            if not url:
                return
            try:
                baud = int(self.baud.currentText())
            except ValueError:
                baud = 115200
            self.connectRequested.emit(url, baud)

    def set_connected(self, connected: bool, detail: str = "") -> None:
        self._connected = connected
        self.button.setText("Disconnect" if connected else "Connect")
        self.status.setText(("Connected " + detail).strip() if connected else "Disconnected")

    def update_stats(self, stats: LinkStats, rate: float) -> None:
        self.rate.setText(f"{rate:,.0f} frames/s")
        total_drops = stats.frames_dropped
        self.drops.setText(f"{total_drops} drops")
        self.drops.setToolTip(
            f"header CRC: {stats.header_crc_errors}\npayload CRC: {stats.payload_crc_errors}\n"
            f"length: {stats.length_errors}\nCOBS: {stats.cobs_errors}\nresyncs: {stats.resyncs}"
        )


def _wrap(layout) -> QWidget:
    w = QWidget()
    w.setLayout(layout)
    return w
