"""Small custom widgets: start screen, tabs, toolbar, info card, explorer page."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .canvas import Mode, PiCanvas

DIGIT_CHOICES = [
    100_000, 500_000, 1_000_000, 2_000_000, 5_000_000,
    10_000_000, 25_000_000, 50_000_000, 100_000_000,
    250_000_000, 500_000_000, 1_000_000_000,
]


def _ghost(text: str, checkable: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setProperty("class", "ghost")
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    b.setFont(theme.mono_font(11, spacing=1.4))
    return b


# --------------------------------------------------------------------------- #
# Start screen
# --------------------------------------------------------------------------- #
class _ThinProgress(QWidget):
    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedSize(290, 3)

    def set_value(self, v: float) -> None:
        self.value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1a1f35"))
        p.fillRect(QRectF(0, 0, self.width() * self.value, self.height()), theme.AMBER)


class StartPage(QWidget):
    computeRequested = Signal(int)
    cancelRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("startPage")

        pi = QLabel("π")
        pi.setFont(theme.mono_font(26, bold=True))
        pi.setStyleSheet(f"color:{theme.GOLD.name()};")
        title = QLabel("SEARCH")
        title.setFont(theme.mono_font(24, bold=True, spacing=9))
        title.setStyleSheet("color:#f2f5ff;")
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addStretch(1)
        row.addWidget(pi)
        row.addWidget(title)
        row.addStretch(1)

        sub = QLabel("CHUDNOVSKY  ·  BINARY SPLITTING  ·  NOTHING PRE-STORED")
        sub.setFont(theme.mono_font(9, spacing=2.2))
        sub.setStyleSheet("color:#4f5a8c;")
        sub.setAlignment(Qt.AlignCenter)

        self.msg = QLabel("")
        self.msg.setFont(theme.mono_font(10, spacing=1.6))
        self.msg.setStyleSheet(f"color:{theme.AMBER.name()};")
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        self.msg.setFixedHeight(90)

        self.bar = _ThinProgress()

        self.combo = QComboBox()
        self.combo.setObjectName("digitsCombo")
        self.combo.setCursor(Qt.PointingHandCursor)
        self.combo.setToolTip(
            "Large selections can require many gigabytes of RAM and a very long compute time."
        )
        for n in DIGIT_CHOICES:
            self.combo.addItem(f"{n:,} digits", n)
        self.combo.setCurrentIndex(2)
        self.btn = QPushButton("COMPUTE  →")
        self.btn.setObjectName("computeBtn")
        self.btn.setFont(theme.mono_font(10, bold=True, spacing=1.8))
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.clicked.connect(lambda: self.computeRequested.emit(self.combo.currentData()))
        self.cancel_btn = _ghost("CANCEL")
        self.cancel_btn.setObjectName("cancelComputeBtn")
        self.cancel_btn.clicked.connect(self.cancelRequested)
        self.cancel_btn.hide()
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        ctl.addStretch(1)
        ctl.addWidget(self.combo)
        ctl.addWidget(self.btn)
        ctl.addWidget(self.cancel_btn)
        ctl.addStretch(1)

        resource_note = QLabel("LARGE COUNTS NEED SUBSTANTIAL MEMORY AND COMPUTE TIME")
        resource_note.setFont(theme.mono_font(8, spacing=1.2))
        resource_note.setStyleSheet("color:#4f5a8c;")
        resource_note.setAlignment(Qt.AlignCenter)

        col = QVBoxLayout(self)
        col.setAlignment(Qt.AlignCenter)
        col.setSpacing(8)
        col.addStretch(3)
        col.addLayout(row)
        col.addWidget(sub)
        col.addWidget(self.msg)
        col.addWidget(self.bar, 0, Qt.AlignHCenter)
        col.addSpacing(18)
        col.addLayout(ctl)
        col.addWidget(resource_note)
        col.addStretch(4)

    def set_busy(self, busy: bool) -> None:
        self.btn.setEnabled(not busy)
        self.combo.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        self.cancel_btn.setVisible(busy)
        if not busy:
            self.bar.set_value(0)

    def set_progress(self, frac: float, text: str) -> None:
        self.bar.set_value(frac)
        self.msg.setText(f"{text.upper()}  ·  {frac * 100:3.0f}%")

    def set_message(self, text: str, error: bool = False) -> None:
        self.msg.setStyleSheet(f"color:{theme.RED.name() if error else theme.AMBER.name()};")
        self.msg.setText(text)


# --------------------------------------------------------------------------- #
# Explorer overlays
# --------------------------------------------------------------------------- #
class TabBar(QWidget):
    modeChanged = Signal(int)
    LABELS = ["01 NUMBERS", "02 LETTERS", "03 COLORS", "04 BLACK && WHITE"]

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for i, text in enumerate(self.LABELS):
            b = QPushButton(text)
            b.setProperty("class", "tab")
            b.setProperty("dimmed", i == 3)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFont(theme.mono_font(10, spacing=1.3))
            self.group.addButton(b, i)
            lay.addWidget(b)
            self.buttons.append(b)
        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.modeChanged)

    def set_mode(self, mode: int) -> None:
        self.buttons[int(mode)].setChecked(True)


class Toolbar(QFrame):
    searchRequested = Signal(str, str)   # (mode label, text)
    shapeClicked = Signal()
    recToggled = Signal(bool)
    hudToggled = Signal(bool)

    DIGIT_MODES = ["ANY NUMBER", "DATE"]
    LETTER_MODES = ["WORD"]

    def __init__(self):
        super().__init__()
        self.setObjectName("toolbar")
        self.combo = QComboBox()
        self.combo.setObjectName("modeCombo")
        self.combo.setCursor(Qt.PointingHandCursor)
        self.combo.setFont(theme.mono_font(11, spacing=1.6))
        self.edit = QLineEdit()
        self.edit.setObjectName("queryEdit")
        self.edit.setPlaceholderText("Type, then Enter")
        self.search = QPushButton("SEARCH")
        self.search.setObjectName("searchBtn")
        self.search.setCursor(Qt.PointingHandCursor)
        self.search.setFont(theme.mono_font(11, bold=True, spacing=1.6))
        self.shape = _ghost("SHAPE")
        self.rec = _ghost("REC")
        self.hud = _ghost("+HUD", checkable=True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 7, 8, 7)
        lay.setSpacing(8)
        lay.addWidget(self.combo)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.search)
        lay.addWidget(self.shape)
        lay.addWidget(self.rec)
        lay.addWidget(self.hud)

        self.edit.returnPressed.connect(self._emit)
        self.search.clicked.connect(self._emit)
        self.shape.clicked.connect(self.shapeClicked)
        self.rec.clicked.connect(self._rec_clicked)
        self.hud.toggled.connect(self.hudToggled)
        self.combo.currentTextChanged.connect(self._update_placeholder)
        self.set_letters(False)

    def _emit(self):
        self.searchRequested.emit(self.combo.currentText(), self.edit.text())

    def _update_placeholder(self, text: str):
        self.edit.setPlaceholderText("DD/MM/YYYY, then Enter" if text == "DATE" else "Type, then Enter")

    def set_letters(self, letters: bool) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(self.LETTER_MODES if letters else self.DIGIT_MODES)
        self.combo.blockSignals(False)
        self._update_placeholder(self.combo.currentText())

    def _rec_clicked(self):
        recording = self.rec.property("recording") == "true"
        self.set_recording(not recording)
        self.recToggled.emit(not recording)

    def set_recording(self, on: bool) -> None:
        self.rec.setProperty("recording", "true" if on else "false")
        self.rec.setText("● REC" if on else "REC")
        self.rec.style().unpolish(self.rec)
        self.rec.style().polish(self.rec)


class InfoCard(QFrame):
    """The FOUND / NOT FOUND card shown above the toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setProperty("kind", "found")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.body = QLabel()
        self.body.setObjectName("cardBody")
        self.body.setAlignment(Qt.AlignCenter)
        self.body.setTextFormat(Qt.RichText)
        self.body.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 9, 22, 10)
        lay.setSpacing(5)
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        self.hide()

    @staticmethod
    def _gold(t: str) -> str:
        return f'<b style="color:{theme.GOLD.name()};">{t}</b>'

    def show_card(self, kind: str, title: str, body_html: str) -> None:
        self.setProperty("kind", kind)
        big = kind != "found"
        self.title.setFont(theme.mono_font(15 if big else 12, bold=True, spacing=2.0))
        self.body.setFont(theme.mono_font(12 if big else 10, spacing=0.4))
        self.title.setText(title)
        self.body.setText(body_html)
        self.style().unpolish(self)
        self.style().polish(self)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)
        self.show()
        self.raise_()
        if self.parent() is not None:
            self.parent().layout_overlays()

    def fit(self, max_width: int) -> None:
        """Size the card to its text (wrapping only when it would be too wide)."""
        self.body.setWordWrap(False)
        lay = self.layout()
        lay.activate()
        natural = max(self.title.sizeHint().width(), self.body.sizeHint().width()) + 46
        if natural > max_width:
            self.body.setWordWrap(True)
            width = max_width
            self.setFixedWidth(width)
            lay.activate()
            self.setFixedHeight(lay.heightForWidth(width))
        else:
            self.setFixedWidth(natural)
            lay.activate()
            self.setFixedHeight(lay.sizeHint().height())


class ExplorerPage(QWidget):
    backRequested = Signal()

    def __init__(self):
        super().__init__()
        self.canvas = PiCanvas(self)
        self.tabs = TabBar()
        self.tabs.setParent(self)
        self.back = _ghost("← NEW SEARCH")
        self.back.setObjectName("backToStartBtn")
        self.back.setParent(self)
        self.back.clicked.connect(self.backRequested)
        self.toolbar = Toolbar()
        self.toolbar.setParent(self)
        self.card = InfoCard(self)
        self.canvas.lower()

    def layout_overlays(self) -> None:
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.tabs.adjustSize()
        self.tabs.move(16, 14)
        self.back.adjustSize()
        self.back.move(w - self.back.width() - 16, 14)
        tb_h = 50
        self.toolbar.setGeometry(16, h - tb_h - 16, w - 32, tb_h)
        self.card.fit(min(780, w - 60))
        self.card.move((w - self.card.width()) // 2, h - tb_h - 16 - self.card.height() - 14)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.layout_overlays()
