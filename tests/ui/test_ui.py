"""Offscreen pytest-qt tests for the dashboard. Owner: ui-engineer (run/extended by test-engineer).

Run headless with QT_QPA_PLATFORM=offscreen (pyproject sets qt_api=pyside6). These push events straight into
the store (the UI's read view) for determinism, then tick the refresh and assert the widgets reflect it.
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PySide6")

from pytelemetry.core.types import Alert, LiveVar, Telemetry, ValueType  # noqa: E402
from pytelemetry.ui.app import MainWindow  # noqa: E402
from pytelemetry.ui.panels.livevars import LiveVarsPanel  # noqa: E402


def _push_telemetry(store, n: int) -> None:
    now = time.monotonic()
    for i in range(n):
        store.on_telemetry(Telemetry("Voltage", ValueType.FLOAT, 12.0 + (i % 50) * 0.01, now + i * 0.001))
        store.on_telemetry(Telemetry("RPM", ValueType.INT32, 3000 + i, now + i * 0.001))


def test_window_builds(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    assert win.windowTitle() == "PyTelemetry"
    for panel in (win.connect_panel, win.telemetry_panel, win.plots_panel, win.alerts_panel,
                  win.livevars_panel, win.recording_panel):
        assert panel is not None


def test_telemetry_table_populates(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    _push_telemetry(win._store, 1000)
    win._refresh()
    model = win.telemetry_panel.table.model()
    assert model.rowCount() == 2  # Voltage, RPM


def test_plot_curve_fills_from_ring_buffer(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    _push_telemetry(win._store, 500)
    win.plots_panel.add_channel("Voltage")
    win._refresh()
    curves = win.plots_panel._curves
    assert "Voltage" in curves
    # .xData is the raw set data; getData() returns the downsampled/clipped view (peak mode halves/thins it).
    assert curves["Voltage"].xData is not None and len(curves["Voltage"].xData) == 500
    shown_x, _ = curves["Voltage"].getData()
    assert shown_x is not None and len(shown_x) > 0


def test_alerts_debug_toggle(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    now = time.monotonic()
    win._store.on_alert(Alert("real problem", now, debug=False))
    win._store.on_alert(Alert("Processing packet", now, debug=True))
    win._refresh()
    assert win.alerts_panel.list.count() == 1  # debug hidden by default
    win.alerts_panel._show_debug.setChecked(True)
    assert win.alerts_panel.list.count() == 2


def test_livevars_apply_emits_modify(qtbot) -> None:
    from pytelemetry.core.store import TelemetryStore

    class StubController:
        def __init__(self) -> None:
            self.modifies: list[tuple[int, int, object]] = []

        def modify_live_var(self, var_id: int, value_type: int, value: object) -> None:
            self.modifies.append((var_id, value_type, value))

        def request_live_data(self) -> None:
            pass

    store = TelemetryStore()
    stub = StubController()
    panel = LiveVarsPanel(store, stub)
    qtbot.addWidget(panel)
    store.on_live_data((LiveVar(1, ValueType.FLOAT, 3.0, "Pitch", "deg", -45.0, 45.0),))
    panel.refresh()
    panel.table.item(0, 4).setText("3.25")
    panel._apply()
    assert stub.modifies == [(1, int(ValueType.FLOAT), 3.25)]


def test_livevars_apply_clamps_to_limits(qtbot) -> None:
    from pytelemetry.core.store import TelemetryStore

    class StubController:
        def __init__(self) -> None:
            self.modifies: list[tuple[int, int, object]] = []

        def modify_live_var(self, var_id: int, value_type: int, value: object) -> None:
            self.modifies.append((var_id, value_type, value))

        def request_live_data(self) -> None:
            pass

    store = TelemetryStore()
    stub = StubController()
    panel = LiveVarsPanel(store, stub)
    qtbot.addWidget(panel)
    store.on_live_data((LiveVar(1, ValueType.FLOAT, 3.0, "Pitch", "deg", -45.0, 45.0),))
    panel.refresh()
    panel.table.item(0, 4).setText("999")
    panel._apply()
    assert stub.modifies == [(1, int(ValueType.FLOAT), 45.0)]  # clamped to max


def test_demo_runs_end_to_end(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    win.start_demo()
    try:
        deadline = time.time() + 3.0
        while time.time() < deadline and not win._store.keys():
            qtbot.wait(50)
        win._refresh()
        assert win.telemetry_panel.table.model().rowCount() > 0
        assert win._store.live_vars()
    finally:
        win._teardown()


def test_closed_dock_can_be_reopened(qtbot) -> None:
    # isHidden() reflects explicit hide/show regardless of whether the (unshown) window is visible.
    win = MainWindow()
    qtbot.addWidget(win)
    dock = win._docks["Telemetry"]
    dock.close()
    assert dock.isHidden()
    dock.toggleViewAction().trigger()  # the View-menu entry
    assert not dock.isHidden()


def test_reset_layout_restores_all_panels(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    for name in ("Telemetry", "Alerts", "Connect"):
        win._docks[name].close()
    win._reset_layout()
    for dock in win._docks.values():
        assert not dock.isHidden()


def test_refresh_is_fast_under_load(qtbot) -> None:
    win = MainWindow()
    qtbot.addWidget(win)
    _push_telemetry(win._store, 5000)
    win.plots_panel.add_channel("Voltage")
    win.plots_panel.add_channel("RPM")
    # warm up, then measure p95 of the refresh callback
    samples = []
    for _ in range(40):
        _push_telemetry(win._store, 50)
        t0 = time.perf_counter()
        win._refresh()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    p95 = samples[int(len(samples) * 0.95)]
    assert p95 < 16.0, f"refresh p95 {p95:.1f} ms exceeds 16 ms budget"
