"""SHAPE: paint a small pixel pattern with digit colours and look for it in pi."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

GRID = 5

PRESETS = {
    "PLUS": [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)],
    "SQUARE": [(0, 0), (0, 1), (1, 0), (1, 1)],
    "FRAME": [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)],
    "CROSS (X)": [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)],
    "LINE": [(0, 0), (0, 1), (0, 2), (0, 3)],
    "STAIRS": [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)],
    "L-SHAPE": [(0, 0), (1, 0), (2, 0), (2, 1)],
    "TRIANGLE": [(0, 1), (1, 0), (1, 1), (1, 2)],
}


class _Cell(QWidget):
    def __init__(self, dialog: "ShapeDialog", r: int, c: int):
        super().__init__()
        self.d, self.r, self.c = dialog, r, c
        self.setFixedSize(40, 40)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.d.state[self.r][self.c] = None
        else:
            cur = self.d.state[self.r][self.c]
            self.d.state[self.r][self.c] = None if cur == self.d.selected else self.d.selected
        self.d.refresh()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        v = self.d.state[self.r][self.c]
        p.setPen(QPen(theme.BORDER, 1))
        p.setBrush(theme.DIGIT_COLORS[v] if v is not None else QColor("#0e1124"))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
        if v is not None:
            p.setPen(QColor(255, 255, 255, 200) if v in (0, 1, 2, 3, 8) else QColor(0, 0, 0, 200))
            p.setFont(theme.mono_font(13, bold=True))
            p.drawText(self.rect(), Qt.AlignCenter, str(v))


class _Swatch(QWidget):
    def __init__(self, dialog: "ShapeDialog", digit: int):
        super().__init__()
        self.d, self.digit = dialog, digit
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, _e):
        self.d.selected = self.digit
        self.d.refresh()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        sel = self.d.selected == self.digit
        p.setPen(QPen(theme.AMBER if sel else theme.BORDER, 2 if sel else 1))
        p.setBrush(theme.DIGIT_COLORS[self.digit])
        p.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 4, 4)
        p.setPen(QColor(255, 255, 255, 200) if self.digit in (0, 1, 2, 3, 8) else QColor(0, 0, 0, 200))
        p.setFont(theme.mono_font(11, bold=True))
        p.drawText(self.rect(), Qt.AlignCenter, str(self.digit))


class ShapeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SHAPE")
        self.state: List[List[Optional[int]]] = [[None] * GRID for _ in range(GRID)]
        self.selected = 4

        title = QLabel("SHAPE  ·  find a picture in pi")
        title.setFont(theme.mono_font(12, bold=True, spacing=1.5))
        title.setStyleSheet("color:#e6ebfa;")
        hint = QLabel(
            "Pick a digit colour, then click cells to paint (click again or right-click to erase).\n"
            "pi is searched in the COLORS grid: every painted cell must show that digit."
        )
        hint.setFont(theme.mono_font(10))
        hint.setWordWrap(True)

        sw = QHBoxLayout()
        sw.setSpacing(4)
        for d in range(10):
            sw.addWidget(_Swatch(self, d))
        sw.addStretch(1)

        grid = QGridLayout()
        grid.setSpacing(4)
        for r in range(GRID):
            for c in range(GRID):
                grid.addWidget(_Cell(self, r, c), r, c)
        gwrap = QHBoxLayout()
        gwrap.addLayout(grid)
        gwrap.addStretch(1)

        self.presets = QComboBox()
        self.presets.addItem("PRESET…")
        self.presets.addItems(PRESETS.keys())
        self.presets.currentTextChanged.connect(self._apply_preset)

        self.info = QLabel()
        self.info.setFont(theme.mono_font(10))

        clear = QPushButton("CLEAR")
        clear.setProperty("class", "ghost")
        clear.clicked.connect(self._clear)
        cancel = QPushButton("CANCEL")
        cancel.setProperty("class", "ghost")
        cancel.clicked.connect(self.reject)
        go = QPushButton("SEARCH")
        go.setObjectName("searchBtn")
        go.clicked.connect(self.accept)
        for b in (clear, cancel, go):
            b.setCursor(Qt.PointingHandCursor)
        btns = QHBoxLayout()
        btns.addWidget(self.presets)
        btns.addStretch(1)
        btns.addWidget(clear)
        btns.addWidget(cancel)
        btns.addWidget(go)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(hint)
        lay.addLayout(sw)
        lay.addLayout(gwrap)
        lay.addWidget(self.info)
        lay.addLayout(btns)
        self.refresh()

    # ------------------------------------------------------------ helpers
    def _clear(self):
        self.state = [[None] * GRID for _ in range(GRID)]
        self.refresh()

    def _apply_preset(self, name: str):
        if name in PRESETS:
            self.state = [[None] * GRID for _ in range(GRID)]
            for r, c in PRESETS[name]:
                self.state[r][c] = self.selected
            self.refresh()
        self.presets.blockSignals(True)
        self.presets.setCurrentIndex(0)
        self.presets.blockSignals(False)

    def refresh(self):
        for w in self.findChildren(QWidget):
            if isinstance(w, (_Cell, _Swatch)):
                w.update()
        n = len(self.cells())
        if n == 0:
            self.info.setText("Nothing painted yet.")
        else:
            self.info.setText(f"{n} cell{'s' if n != 1 else ''} painted · odds ≈ 1 in {10 ** n:,} per spot")

    def cells(self):
        """Painted cells as (row, col, digit), shifted so the top-left is (0, 0)."""
        raw = [(r, c, v) for r in range(GRID) for c in range(GRID) if (v := self.state[r][c]) is not None]
        if not raw:
            return []
        r0 = min(r for r, _c, _v in raw)
        c0 = min(c for _r, c, _v in raw)
        return [(r - r0, c - c0, v) for r, c, v in raw]
