"""PySide6 application + MainWindow. Owner: ui-engineer.

Thread rule (CLAUDE.md): the Session reads serial on its own thread and writes decoded events into the
thread-safe TelemetryStore; the UI never blocks on I/O. A single 30 Hz QTimer pulls snapshots from the store
and refreshes every panel in one batch. Widgets are touched only here, on the GUI thread.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMainWindow

from pytelemetry.core.config import load_config
from pytelemetry.core.session import Session
from pytelemetry.core.store import TelemetryStore
from pytelemetry.core.transport.serial_transport import SerialTransport
from pytelemetry.core.types import AppConfig
from pytelemetry.ui.panels.alerts import AlertsPanel
from pytelemetry.ui.panels.connect import ConnectPanel
from pytelemetry.ui.panels.livevars import LiveVarsPanel
from pytelemetry.ui.panels.plots import PlotsPanel
from pytelemetry.ui.panels.recording import RecordingPanel
from pytelemetry.ui.panels.telemetry import TelemetryPanel
from pytelemetry.ui.synthetic import SyntheticSource
from pytelemetry.ui.theme import apply_dark_theme

__all__ = ["MainWindow", "run_app"]

_REFRESH_MS = 33  # ~30 Hz


class MainWindow(QMainWindow):
    # Emitted from the background connect thread; Qt queues them onto the GUI thread (cross-thread
    # connections are queued by default), so the handlers run where it's safe to touch widgets.
    _connectSucceeded = Signal(object, str, int, int)
    _connectFailed = Signal(str, int)

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PyTelemetry")
        self.resize(1200, 760)
        self._config = config or AppConfig()
        self._live_cfg = {c.id: c for c in self._config.live_vars}
        self._controller: Session | SyntheticSource | None = None
        self._store = TelemetryStore(history_samples=self._config.history_samples)

        self.connect_panel = ConnectPanel()
        self.telemetry_panel = TelemetryPanel(self._store)
        self.plots_panel = PlotsPanel(self._store)
        self.alerts_panel = AlertsPanel(self._store)
        self.livevars_panel = LiveVarsPanel(self._store, controller=self)
        self.recording_panel = RecordingPanel()

        self._docks: dict[str, QDockWidget] = {}
        self.setCentralWidget(self._dockless(self.plots_panel))
        self._add_dock("Connect", self.connect_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._add_dock("Live Vars", self.livevars_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._add_dock("Telemetry", self.telemetry_panel, Qt.DockWidgetArea.RightDockWidgetArea)
        self._add_dock("Alerts", self.alerts_panel, Qt.DockWidgetArea.BottomDockWidgetArea)
        self._add_dock("Recording", self.recording_panel, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._default_state = self.saveState()  # captured before any user layout is restored
        self._build_menu()

        self._status = QLabel("Disconnected")
        self.statusBar().addWidget(self._status)
        self._frame_label = QLabel("")
        self.statusBar().addPermanentWidget(self._frame_label)

        self.connect_panel.connectRequested.connect(self._connect)
        self.connect_panel.disconnectRequested.connect(self._disconnect)
        self.telemetry_panel.plotChannel.connect(self.plots_panel.add_channel)
        self.recording_panel.recordingChanged.connect(self._on_recording)
        self._connectSucceeded.connect(self._on_connect_succeeded)
        self._connectFailed.connect(self._on_connect_failed)
        self._connecting = False
        self._connect_gen = 0  # bumped on every connect/disconnect; stale in-flight connects are abandoned

        self._last_frames = 0
        self._last_time = time.monotonic()
        self._rate = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

        self._restore_layout()

    def _build_menu(self) -> None:
        view = self.menuBar().addMenu("&View")
        for title, dock in self._docks.items():
            action = dock.toggleViewAction()  # checkable show/hide, so closed panels can be reopened
            action.setText(title)
            view.addAction(action)
        view.addSeparator()
        reset = view.addAction("Reset Layout")
        reset.triggered.connect(self._reset_layout)

    def _reset_layout(self) -> None:
        self.restoreState(self._default_state)
        for dock in self._docks.values():
            dock.setVisible(True)

    def _restore_layout(self) -> None:
        settings = QSettings("pytelemetry", "pytelemetry")
        geom = settings.value("geometry")
        state = settings.value("state")
        if geom is not None:
            self.restoreGeometry(geom)
        if state is not None:
            self.restoreState(state)

    def _save_layout(self) -> None:
        settings = QSettings("pytelemetry", "pytelemetry")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())

    # ---- controller API used by LiveVarsPanel (delegates to the active controller) ---------------

    def request_live_data(self) -> None:
        if self._controller is not None:
            self._controller.request_live_data()

    def modify_live_var(self, var_id: int, value_type: int, value: int | float | bool) -> None:
        if self._controller is not None:
            self._controller.modify_live_var(var_id, value_type, value)

    # ---- lifecycle ------------------------------------------------------------------------------

    def start_demo(self) -> None:
        self._teardown()
        source = SyntheticSource()
        source.add_sink(self._store)
        self._attach_recorder(source)
        source.start()
        source.request_live_data()
        self._controller = source
        self.connect_panel.set_connected(True, "(demo)")
        self._status.setText("Demo — synthetic source")

    def connect_to(self, url: str, baud: int = 115200) -> None:
        self._connect(url, baud)

    def _connect(self, url: str, baud: int) -> None:
        if self._connecting:
            return  # a connect is already in flight; ignore the repeat click
        self._teardown()
        self._connect_gen += 1
        gen = self._connect_gen
        self._connecting = True
        self._status.setText(f"Connecting to {url}…")
        # Opening the transport (serial_for_url / socket connect) can block for the connect timeout, so it
        # runs on a worker thread — never the GUI thread (CLAUDE.md: nothing on the GUI thread blocks on I/O).
        # The recorder is captured here, on the GUI thread, rather than read off the panel in the worker.
        rec = self.recording_panel.recorder

        def worker() -> None:
            try:
                session = Session(SerialTransport(url, baud), live_var_config=self._live_cfg)
                session.add_sink(self._store)
                if rec is not None:
                    session.add_sink(rec)
                session.start()  # opens the transport here, off the GUI thread
                session.request_live_data()
            except Exception as exc:  # surface connect failures in the UI, don't crash
                self._connectFailed.emit(str(exc), gen)
                return
            self._connectSucceeded.emit(session, url, baud, gen)

        threading.Thread(target=worker, name="pytelemetry-connect", daemon=True).start()

    def _on_connect_succeeded(self, session: Session, url: str, baud: int, gen: int) -> None:
        if gen != self._connect_gen:  # user disconnected or started another connect while this was opening
            session.stop()
            return
        self._connecting = False
        self._controller = session
        self.connect_panel.set_connected(True, url)
        self._status.setText(f"Connected — {url} @ {baud}")

    def _on_connect_failed(self, message: str, gen: int) -> None:
        if gen != self._connect_gen:  # superseded; don't clobber the newer state
            return
        self._connecting = False
        self.connect_panel.set_connected(False)
        self._status.setText(f"Connect failed: {message}")

    def _disconnect(self) -> None:
        self._teardown()
        self.connect_panel.set_connected(False)
        self._status.setText("Disconnected")

    def _teardown(self) -> None:
        self._connect_gen += 1  # abandon any connect still opening in the background
        self._connecting = False
        if self._controller is not None:
            self._controller.stop()
            self._controller = None

    def _attach_recorder(self, controller: Session | SyntheticSource) -> None:
        rec = self.recording_panel.recorder
        if rec is not None:
            controller.add_sink(rec)

    def _on_recording(self, active: bool) -> None:
        if active and self._controller is not None:
            rec = self.recording_panel.recorder
            if rec is not None:
                self._controller.add_sink(rec)

    # ---- refresh (30 Hz) ------------------------------------------------------------------------

    def _refresh(self) -> None:
        start = time.perf_counter()
        self.telemetry_panel.refresh()
        self.plots_panel.refresh()
        self.alerts_panel.refresh()
        self.livevars_panel.refresh()
        self.recording_panel.refresh()
        if self._controller is not None:
            stats = self._controller.stats
            now = time.monotonic()
            dt = now - self._last_time
            if dt >= 0.5:
                self._rate = (stats.frames_ok - self._last_frames) / dt
                self._last_frames = stats.frames_ok
                self._last_time = now
            self.connect_panel.update_stats(stats, self._rate)
        ui_ms = (time.perf_counter() - start) * 1000.0
        self._frame_label.setText(f"UI {ui_ms:4.1f} ms   •   {self._rate:,.0f} frames/s")

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._save_layout()
        self._teardown()
        super().closeEvent(event)

    # ---- dock helpers ---------------------------------------------------------------------------

    def _add_dock(self, title: str, widget, area: Qt.DockWidgetArea) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{title.replace(' ', '_').lower()}")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self._docks[title] = dock
        return dock

    @staticmethod
    def _dockless(widget):
        return widget


def run_app(connect: str | None = None, demo: bool = False, sim: bool = False) -> int:
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    config = load_config()
    window = MainWindow(config)
    window.show()
    server = None
    if demo:
        window.start_demo()
    elif sim:
        from pytelemetry.sim.server import SimServer

        server = SimServer(port=0, rate_hz=100.0)
        server.start()
        window.connect_to(f"socket://127.0.0.1:{server.port}", config.baud or 115200)
    elif connect:
        window.connect_to(connect, config.baud or 115200)
    try:
        return app.exec()
    finally:
        if server is not None:
            server.stop()
