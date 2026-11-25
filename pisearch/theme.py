"""Colours, fonts and the Qt stylesheet (dark navy + amber, as in the video)."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap

BG = QColor("#0a0a12")
PANEL = QColor("#0c0e1b")
DIM = QColor("#2a3a70")          # un-highlighted digits / letters
GOLD = QColor("#f4c267")         # highlighted match
AMBER = QColor("#f0b429")        # buttons / active tab
TEXT = QColor("#e6ebfa")
MUTED = QColor("#8794c0")
BORDER = QColor("#222a4a")
RED = QColor("#e8805e")
CARD_EDGE = QColor("#b9d3e6")

# digit -> colour for the COLORS tab (black, navy, blue, sky, green, yellow, amber, orange, red, magenta)
DIGIT_COLORS = [
    QColor("#000000"),
    QColor("#0a1a9a"),
    QColor("#3d6fd9"),
    QColor("#3b9be0"),
    QColor("#27c944"),
    QColor("#f5e41c"),
    QColor("#f9b90f"),
    QColor("#ef8a0c"),
    QColor("#f2230c"),
    QColor("#e61cf0"),
]
BW_BLACK = QColor("#05060a")
BW_WHITE = QColor("#f2f4f8")

MONO_CANDIDATES = [
    "JetBrains Mono",
    "Cascadia Mono",
    "Cascadia Code",
    "Consolas",
    "SF Mono",
    "Menlo",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Noto Sans Mono",
    "Courier New",
]


def mono_family() -> str:
    available = set(QFontDatabase.families())
    for fam in MONO_CANDIDATES:
        if fam in available:
            return fam
    return "monospace"


def mono_font(px: float = 11, bold: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont(mono_family())
    f.setStyleHint(QFont.Monospace)
    f.setPixelSize(max(1, int(round(px))))
    f.setBold(bold)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def chevron_path(color: str = "#8794c0") -> str:
    """Draw a small down-chevron PNG (used for combo boxes) and return its path."""
    path = os.path.join(tempfile.gettempdir(), f"pisearch_chevron_{color.strip('#')}.png")
    if not os.path.exists(path):
        pm = QPixmap(20, 20)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor(color), 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawLine(QPointF(5, 8), QPointF(10, 13))
        p.drawLine(QPointF(10, 13), QPointF(15, 8))
        p.end()
        pm.save(path, "PNG")
    return path.replace("\\", "/")


def stylesheet() -> str:
    fam = mono_family()
    chev = chevron_path()
    return f"""
    * {{ font-family: "{fam}", monospace; }}
    QMainWindow, QStackedWidget, QWidget#startPage {{ background: #08080f; }}
    QToolTip {{ background: #11142a; color: #e6ebfa; border: 1px solid #222a4a; }}

    /* ---------- start screen ---------- */
    QComboBox#digitsCombo {{
        background: #0d0f1f; color: #b9c4ee; border: 1px solid #1f2547;
        border-radius: 3px; padding: 6px 28px 6px 10px; min-width: 150px; font-size: 11px;
    }}
    QComboBox#digitsCombo::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: url({chev}); width: 14px; height: 14px; }}
    QComboBox#digitsCombo QAbstractItemView {{
        background: #0d0f1f; color: #b9c4ee; border: 1px solid #1f2547;
        selection-background-color: #1c2250; outline: none;
    }}
    QPushButton#computeBtn, QPushButton#searchBtn {{
        background: {AMBER.name()}; color: #14110a; border: none; border-radius: 3px;
        padding: 7px 16px; font-weight: bold; font-size: 11px;
    }}
    QPushButton#computeBtn:hover, QPushButton#searchBtn:hover {{ background: #ffc83d; }}
    QPushButton#computeBtn:disabled {{ background: #5a4a1c; color: #2a2412; }}

    /* ---------- explorer ---------- */
    QFrame#toolbar {{
        background: rgba(12, 14, 28, 247); border: 1px solid #1c2240; border-radius: 8px;
    }}
    QComboBox#modeCombo {{
        background: transparent; color: #8794c0; border: none; padding: 4px 22px 4px 8px;
        min-width: 112px; font-size: 11px;
    }}
    QComboBox#modeCombo::drop-down {{ border: none; width: 18px; }}
    QComboBox#modeCombo QAbstractItemView {{
        background: #0d0f1f; color: #b9c4ee; border: 1px solid #1f2547;
        selection-background-color: #1c2250; outline: none; min-width: 130px;
    }}
    QLineEdit#queryEdit {{
        background: transparent; border: none; color: #ffffff; font-size: 13px;
        selection-background-color: #3b4a90; padding: 4px 6px;
    }}
    QPushButton.ghost {{
        background: #11142a; color: #aab6e4; border: 1px solid #262e55; border-radius: 4px;
        padding: 7px 14px; font-size: 11px;
    }}
    QPushButton.ghost:hover {{ border-color: #3f4b86; color: #ffffff; }}
    QPushButton.ghost:checked {{ border-color: {AMBER.name()}; color: {AMBER.name()}; }}
    QPushButton.ghost[recording="true"] {{ border-color: #e0452f; color: #ff7a64; }}

    QPushButton.tab {{
        background: rgba(10, 12, 24, 220); color: #c3cdf0; border: 1px solid #2a3256;
        border-radius: 4px; padding: 6px 12px; font-size: 10px;
    }}
    QPushButton.tab:hover {{ border-color: #46538f; }}
    QPushButton.tab:checked {{ background: {AMBER.name()}; color: #14110a; border-color: {AMBER.name()}; font-weight: bold; }}
    QPushButton.tab[dimmed="true"]:!checked {{ color: #6b76a3; }}

    /* ---------- info card ---------- */
    QFrame#card {{ background: rgba(9, 11, 22, 248); border: none; border-left: 2px solid {CARD_EDGE.name()}; }}
    QFrame#card[kind="notfound"] {{ border-left: 2px solid {RED.name()}; }}
    QLabel#cardTitle {{ color: #f2f5ff; font-weight: bold; }}
    QFrame#card[kind="notfound"] QLabel#cardTitle {{ color: {RED.name()}; }}
    QLabel#cardBody {{ color: #8f9bc8; }}

    /* ---------- shape dialog ---------- */
    QDialog {{ background: #0b0d1a; }}
    QLabel {{ color: #aab6e4; }}
    QComboBox {{ background: #0d0f1f; color: #b9c4ee; border: 1px solid #1f2547; border-radius: 3px; padding: 4px 8px; }}
    QComboBox QAbstractItemView {{ background: #0d0f1f; color: #b9c4ee; selection-background-color: #1c2250; }}
    """
