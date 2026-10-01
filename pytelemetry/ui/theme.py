"""Dark Fusion palette + shared channel colours. Owner: ui-engineer."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

__all__ = ["apply_dark_theme", "CHANNEL_COLORS", "color_for_index", "ACCENT"]

ACCENT = "#4aa3ff"

# 8 distinguishable, colour-blind-friendly channel colours (Okabe-Ito).
CHANNEL_COLORS = [
    "#56b4e9",
    "#e69f00",
    "#009e73",
    "#f0e442",
    "#0072b2",
    "#d55e00",
    "#cc79a7",
    "#bbbbbb",
]


def color_for_index(i: int) -> str:
    return CHANNEL_COLORS[i % len(CHANNEL_COLORS)]


def apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    base = QColor("#0e0f12")
    panel = QColor("#16181d")
    text = QColor("#d6d9df")
    pal.setColor(QPalette.ColorRole.Window, panel)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, base)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1b1e24"))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, panel)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.ToolTipBase, panel)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#06121f"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#7a7f8a"))
    disabled = QColor("#5a5e67")
    for grp in (QPalette.ColorGroup.Disabled,):
        pal.setColor(grp, QPalette.ColorRole.Text, disabled)
        pal.setColor(grp, QPalette.ColorRole.WindowText, disabled)
        pal.setColor(grp, QPalette.ColorRole.ButtonText, disabled)
    app.setPalette(pal)
    app.setStyleSheet(
        "QToolTip { color: #d6d9df; background: #16181d; border: 1px solid #3a3f49; }"
        "QDockWidget::title { background: #16181d; padding: 4px; }"
        "QTableView { gridline-color: #262a31; selection-background-color: #24405e; }"
        "QHeaderView::section { background: #1b1e24; border: 0; padding: 3px 6px; }"
    )
