"""The big zoomable canvas that shows the digits of pi.

Four views (the tabs of the app):

    NUMBERS        the decimals as a grid of digits
    LETTERS        digit pairs turned into letters (frame A / frame B)
    COLORS         one coloured square per digit
    BLACK & WHITE  one black or white square per digit

Rendering uses level-of-detail: real text when zoomed in, a pre-built texture
when zoomed out, so 2 million digits stay smooth.
"""
from __future__ import annotations

import math
import time
from enum import IntEnum
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from . import search as S
from . import theme


class Mode(IntEnum):
    NUMBERS = 0
    LETTERS = 1
    COLORS = 2
    BW = 3


NUM_W = 200            # columns of the digits grid
LET_W = 100            # columns of the letters grid
ADV = 0.72             # glyph advance (em) - the text is a bit airy, like the video
PITCH = {Mode.NUMBERS: 2.9, Mode.LETTERS: 2.4, Mode.COLORS: 1.0, Mode.BW: 1.0}
FAR_Z = 3.4            # below this the text modes switch to the texture
Z_MAX = 240.0

# rough "ink" weight of every glyph, used for the zoomed-out texture
_INK = {c: 0.72 for c in range(256)}
_INK.update({ord(c): w for c, w in zip("0123456789", (0.80, 0.55, 0.70, 0.72, 0.75, 0.72, 0.78, 0.62, 0.86, 0.78))})
_INK.update({ord("I"): 0.50, ord("J"): 0.56, ord("L"): 0.55, ord("M"): 0.92, ord("W"): 0.92,
             ord("B"): 0.82, ord("E"): 0.80, ord("O"): 0.80, ord("Q"): 0.86, ord("G"): 0.80,
             ord("T"): 0.58, ord("Y"): 0.58, ord("V"): 0.66, ord("X"): 0.70, ord("A"): 0.74})
_INK[0] = 0.0
INK_LUT = np.array([_INK[i] for i in range(256)], dtype=np.float32)


def _pack(c: QColor) -> int:
    return (0xFF << 24) | (c.red() << 16) | (c.green() << 8) | c.blue()


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def _van_wijk(p0, w0, p1, w1, rho=1.4):
    """Smooth zoom+pan path (van Wijk & Nuij).  Returns (f(t) -> (x, y, w), S)."""
    ux, uy = p1[0] - p0[0], p1[1] - p0[1]
    u1 = math.hypot(ux, uy)
    if u1 < 1e-6 or w0 <= 0 or w1 <= 0:
        s_len = abs(math.log(max(w1, 1e-9) / max(w0, 1e-9))) / rho

        def f_zoom(t):
            return p0[0] + ux * t, p0[1] + uy * t, w0 * math.exp(math.log(w1 / w0) * t)

        return f_zoom, s_len
    r2, r4 = rho * rho, rho ** 4
    b0 = (w1 * w1 - w0 * w0 + r4 * u1 * u1) / (2 * w0 * r2 * u1)
    b1 = (w1 * w1 - w0 * w0 - r4 * u1 * u1) / (2 * w1 * r2 * u1)
    r0 = math.log(-b0 + math.sqrt(b0 * b0 + 1))
    r1 = math.log(-b1 + math.sqrt(b1 * b1 + 1))
    s_len = (r1 - r0) / rho

    def f(t):
        s = t * s_len
        u = (w0 / r2) * math.cosh(r0) * math.tanh(rho * s + r0) - (w0 / r2) * math.sinh(r0)
        w = w0 * math.cosh(r0) / math.cosh(rho * s + r0)
        k = u / u1
        return p0[0] + ux * k, p0[1] + uy * k, w

    return f, abs(s_len)


class PiCanvas(QWidget):
    viewChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self.digits: str = ""
        self.darr: Optional[np.ndarray] = None
        self.frames: dict = {"A": "", "B": ""}
        self.color_w = 1000

        self.mode = Mode.NUMBERS
        self.frame = "A"
        self.highlight: Optional[S.Match] = None
        self.show_hud = False

        self.cx = 0.0   # camera centre, in columns
        self.cy = 0.0   # camera centre, in rows
        self.z = 14.0   # pixels per column

        self._tex = {}
        self._adv_cache = {}
        self._drag = None
        self._anim = None
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._tick)
        self._frame_times = []
        self._fps = 0.0

    # ------------------------------------------------------------------ data
    def set_data(self, digits: str) -> None:
        self.digits = digits
        self.darr = S.digits_to_array(digits)
        self.frames = S.build_letter_frames(digits)
        self.color_w = int(min(1000, max(100, math.sqrt(len(digits) * 1.8))))
        self._tex.clear()
        self.highlight = None
        self._anim = None
        self.update()

    def clear_data(self) -> None:
        """Release computed digits and all canvas data derived from them."""
        self._timer.stop()
        self.digits = ""
        self.darr = None
        self.frames = {"A": "", "B": ""}
        self.color_w = 1000
        self.mode = Mode.NUMBERS
        self.frame = "A"
        self.highlight = None
        self.cx = 0.0
        self.cy = 0.0
        self.z = 14.0
        self._tex.clear()
        self._adv_cache.clear()
        self._drag = None
        self._anim = None
        self._frame_times.clear()
        self._fps = 0.0
        self.update()

    def has_data(self) -> bool:
        return self.darr is not None and len(self.digits) > 0

    # ---------------------------------------------------------- grid helpers
    def grid_w(self, mode: Optional[Mode] = None) -> int:
        m = self.mode if mode is None else mode
        return {Mode.NUMBERS: NUM_W, Mode.LETTERS: LET_W}.get(m, self.color_w)

    def seq_len(self, mode: Optional[Mode] = None) -> int:
        m = self.mode if mode is None else mode
        if m == Mode.LETTERS:
            return len(self.frames[self.frame])
        return len(self.digits)

    def rows(self, mode: Optional[Mode] = None) -> int:
        w = self.grid_w(mode)
        return max(1, -(-self.seq_len(mode) // w))

    def pitch(self) -> float:
        return PITCH[self.mode]

    def is_text(self) -> bool:
        return self.mode in (Mode.NUMBERS, Mode.LETTERS)

    def fit_zoom(self) -> float:
        w, h = max(1, self.width()), max(1, self.height())
        return min(w / (self.grid_w() * 1.04), h / (self.rows() * self.pitch() * 1.04))

    def z_min(self) -> float:
        return max(0.02, self.fit_zoom() * 0.6)

    # -------------------------------------------------------- mode / frame
    def focus_digit(self) -> int:
        """Index of the digit currently at the centre of the screen."""
        w = self.grid_w()
        idx = int(max(0, min(self.rows() - 1, self.cy))) * w + int(max(0, min(w - 1, self.cx)))
        if self.mode == Mode.LETTERS:
            idx = idx * 2 + (1 if self.frame == "B" else 0)
        return max(0, min(len(self.digits) - 1, idx))

    def _place_digit(self, digit_idx: int, mode: Mode, frame: str) -> None:
        if mode == Mode.LETTERS:
            idx = max(0, (digit_idx - (1 if frame == "B" else 0)) // 2)
        else:
            idx = digit_idx
        w = self.grid_w(mode)
        self.cx = (idx % w) + 0.5
        self.cy = (idx // w) + 0.5

    def set_mode(self, mode: Mode, frame: Optional[str] = None) -> None:
        mode = Mode(mode)
        if not self.has_data():
            self.mode = mode
            return
        digit_idx = self.focus_digit()
        self._anim = None
        self.mode = mode
        if frame:
            self.frame = frame
        self._place_digit(digit_idx, mode, self.frame)
        default = {Mode.NUMBERS: 14.0, Mode.LETTERS: 16.0, Mode.COLORS: 8.0, Mode.BW: 8.0}[mode]
        self.z = max(self.z_min(), min(default, Z_MAX))
        self._clamp()
        self.update()
        self.viewChanged.emit()

    def set_highlight(self, match: Optional[S.Match]) -> None:
        self.highlight = match if (match is not None and match.found) else None
        self.update()

    # -------------------------------------------------------------- camera
    def _clamp(self) -> None:
        w = self.grid_w()
        self.cx = max(-2.0, min(w + 2.0, self.cx))
        self.cy = max(-1.0, min(self.rows() + 1.0, self.cy))
        self.z = max(self.z_min(), min(Z_MAX, self.z))

    def home(self, animate: bool = True) -> None:
        if not self.has_data():
            return
        z = {Mode.NUMBERS: 16.0, Mode.LETTERS: 18.0, Mode.COLORS: 8.0, Mode.BW: 8.0}[self.mode]
        cx = (self.width() / 2 - 48) / z
        cy = (self.height() / 2 - 90) / (self.pitch() * z)
        self.fly_to(cx, cy, z, animate=animate)

    def intro(self) -> None:
        """Start zoomed out (the whole page of pi) and fly to the first digits."""
        if not self.has_data():
            return
        self._anim = None
        self.cx = self.grid_w() / 2
        self.cy = self.rows() / 2
        self.z = self.fit_zoom()
        self.update()
        QTimer.singleShot(250, self.home)

    def fly_to(self, cx: float, cy: float, z: float, animate: bool = True) -> None:
        z = max(self.z_min(), min(Z_MAX, z))
        if not animate:
            self.cx, self.cy, self.z = cx, cy, z
            self._anim = None
            self.update()
            self.viewChanged.emit()
            return
        p = self.pitch()
        vw = max(1, self.width())
        p0 = (self.cx, self.cy * p)
        p1 = (cx, cy * p)
        w0, w1 = vw / self.z, vw / z
        path, s_len = _van_wijk(p0, w0, p1, w1)
        dur = max(0.9, min(3.4, 0.55 + s_len * 0.75))
        self._anim = {"t0": time.monotonic(), "dur": dur, "path": path, "pitch": p}
        self._timer.start()

    def fly_to_highlight(self) -> None:
        cells = self._highlight_cells()
        if cells is None or len(cells) == 0:
            return
        w = self.grid_w()
        cols, rws = cells % w, cells // w
        cmin, cmax, rmin, rmax = cols.min(), cols.max(), rws.min(), rws.max()
        p = self.pitch()
        width_world = float(cmax - cmin + 1)
        height_world = (rmax - rmin + 1) * p
        z = min(0.62 * self.width() / width_world, 0.45 * self.height() / height_world)
        z = max(5.0, min(z, 140.0 if self.is_text() else 70.0))
        self.fly_to((cmin + cmax + 1) / 2, (rmin + rmax + 1) / 2, z)

    def _tick(self) -> None:
        a = self._anim
        if a is None:
            self._timer.stop()
            return
        t = (time.monotonic() - a["t0"]) / a["dur"]
        done = t >= 1.0
        t = _smooth(min(1.0, t))
        x, y, wv = a["path"](t)
        self.z = max(self.z_min() * 0.5, min(Z_MAX, self.width() / wv))
        self.cx, self.cy = x, y / a["pitch"]
        if done:
            self._anim = None
            self._timer.stop()
        self.update()
        self.viewChanged.emit()

    # --------------------------------------------------------------- input
    def wheelEvent(self, e):
        if not self.has_data():
            return
        self._anim = None
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.0018 ** delta
        pos = e.position()
        vw, vh, p = self.width(), self.height(), self.pitch()
        wx = self.cx + (pos.x() - vw / 2) / self.z
        wy = self.cy * p + (pos.y() - vh / 2) / self.z
        self.z = max(self.z_min(), min(Z_MAX, self.z * factor))
        self.cx = wx - (pos.x() - vw / 2) / self.z
        self.cy = (wy - (pos.y() - vh / 2) / self.z) / p
        self._clamp()
        self.update()
        self.viewChanged.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._anim = None
            self._drag = e.position()
            self.setCursor(Qt.ClosedHandCursor)
            self.setFocus()

    def mouseMoveEvent(self, e):
        if self._drag is not None and self.has_data():
            d = e.position() - self._drag
            self._drag = e.position()
            self.cx -= d.x() / self.z
            self.cy -= d.y() / (self.z * self.pitch())
            self._clamp()
            self.update()
            self.viewChanged.emit()

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, e):
        if not self.has_data():
            return
        pos = e.position()
        vw, vh, p = self.width(), self.height(), self.pitch()
        wx = self.cx + (pos.x() - vw / 2) / self.z
        wy = (self.cy * p + (pos.y() - vh / 2) / self.z) / p
        self.fly_to(wx, wy, self.z * 3.0)

    def keyPressEvent(self, e):
        step = 60 / self.z
        k = e.key()
        if k == Qt.Key_Left:
            self.cx -= step
        elif k == Qt.Key_Right:
            self.cx += step
        elif k == Qt.Key_Up:
            self.cy -= step / self.pitch()
        elif k == Qt.Key_Down:
            self.cy += step / self.pitch()
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.z *= 1.25
        elif k == Qt.Key_Minus:
            self.z /= 1.25
        elif k == Qt.Key_Home:
            self.home()
            return
        else:
            return super().keyPressEvent(e)
        self._anim = None
        self._clamp()
        self.update()
        self.viewChanged.emit()

    # ----------------------------------------------------------- highlight
    def _highlight_cells(self) -> Optional[np.ndarray]:
        h = self.highlight
        if h is None or not h.found:
            return None
        if h.kind == "letters":
            if self.mode == Mode.LETTERS and h.frame == self.frame:
                return h.indices
            return None
        if self.mode == Mode.LETTERS:
            return None
        return h.indices

    # ------------------------------------------------------------ textures
    def _codes(self) -> np.ndarray:
        if self.mode == Mode.LETTERS:
            return np.frombuffer(self.frames[self.frame].encode("ascii"), dtype=np.uint8)
        return (self.darr + 48).astype(np.uint8)

    def _texture(self) -> QImage:
        key = (self.mode, self.frame if self.mode == Mode.LETTERS else None)
        hit = self._tex.get(key)
        if hit is not None:
            return hit[0]
        w, rows = self.grid_w(), self.rows()
        bg = _pack(theme.BG)
        if self.is_text():
            codes = self._codes()
            padded = np.zeros(rows * w, dtype=np.uint8)
            padded[: len(codes)] = codes
            wgt = INK_LUT[padded].reshape(rows, w)
            d, b = theme.DIM, theme.BG
            gain = 1.18
            r = np.clip(b.red() + (d.red() - b.red()) * wgt * gain, 0, 255).astype(np.uint32)
            g = np.clip(b.green() + (d.green() - b.green()) * wgt * gain, 0, 255).astype(np.uint32)
            bl = np.clip(b.blue() + (d.blue() - b.blue()) * wgt * gain, 0, 255).astype(np.uint32)
            packed = (np.uint32(0xFF) << 24) | (r << 16) | (g << 8) | bl
            img = np.full((rows * 2, w), bg, dtype=np.uint32)
            img[0::2] = packed
        else:
            if self.mode == Mode.COLORS:
                pal = [_pack(c) for c in theme.DIGIT_COLORS]
            else:
                pal = [_pack(theme.BW_BLACK)] * 5 + [_pack(theme.BW_WHITE)] * 5
            lut = np.array(pal + [bg], dtype=np.uint32)
            padded = np.full(rows * w, 10, dtype=np.uint8)
            padded[: len(self.darr)] = self.darr
            img = lut[padded].reshape(rows, w)
        img = np.ascontiguousarray(img)
        qimg = QImage(img.data, img.shape[1], img.shape[0], img.shape[1] * 4, QImage.Format_RGB32)
        self._tex[key] = (qimg, img)  # keep the numpy buffer alive
        return qimg

    # ------------------------------------------------------------- painting
    def paintEvent(self, _e):
        t0 = time.monotonic()
        p = QPainter(self)
        p.fillRect(self.rect(), theme.BG)
        if self.has_data():
            if self.is_text() and self.z >= FAR_Z:
                self._paint_text(p)
            else:
                self._paint_image(p)
            self._paint_far_markers(p)
            self._paint_fades(p)
            if self.show_hud:
                self._paint_hud(p)
        p.end()
        now = time.monotonic()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t < 1.0]
        self._fps = len(self._frame_times)

    # -- helpers
    def _visible(self):
        vw, vh, z, p = self.width(), self.height(), self.z, self.pitch()
        w, rows = self.grid_w(), self.rows()
        c0 = max(0, int(math.floor(self.cx - vw / 2 / z)) - 1)
        c1 = min(w, int(math.ceil(self.cx + vw / 2 / z)) + 1)
        r0 = max(0, int(math.floor(self.cy - vh / 2 / (z * p))) - 1)
        r1 = min(rows, int(math.ceil(self.cy + vh / 2 / (z * p))) + 1)
        return c0, c1, r0, r1

    def _sx(self, col: float) -> float:
        return (col - self.cx) * self.z + self.width() / 2

    def _sy(self, row: float) -> float:
        return (row - self.cy) * self.z * self.pitch() + self.height() / 2

    def _font_for(self, z: float):
        px = max(1, int(round(z / ADV)))
        f = theme.mono_font(px)
        adv = self._adv_cache.get(px)
        if adv is None:
            adv = QFontMetricsF(f).horizontalAdvance("0")
            self._adv_cache[px] = adv
        f.setLetterSpacing(QFont.AbsoluteSpacing, z - adv)
        return f, px

    def _paint_glow(self, p: QPainter, rect: QRectF) -> None:
        p.setPen(Qt.NoPen)
        for grow, alpha in ((0.55, 14), (0.32, 22), (0.14, 34)):
            g = rect.height() * grow
            p.setBrush(QColor(244, 194, 103, alpha))
            p.drawRoundedRect(rect.adjusted(-g, -g, g, g), g, g)

    # -- text (zoomed in)
    def _paint_text(self, p: QPainter) -> None:
        z, pitch = self.z, self.pitch()
        c0, c1, r0, r1 = self._visible()
        w = self.grid_w()
        text = self.frames[self.frame] if self.mode == Mode.LETTERS else self.digits
        font, px = self._font_for(z)
        p.setFont(font)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setPen(theme.DIM)
        base_off = 0.365 * px
        x0 = self._sx(c0)
        for r in range(r0, r1):
            s = text[r * w + c0 : r * w + c1]
            if not s:
                continue
            yc = self._sy(r + 0.5)
            p.drawText(QPointF(x0, yc + base_off), s)

        cells = self._highlight_cells()
        if cells is not None and len(cells):
            vis = cells[(cells // w >= r0) & (cells // w < r1)]
            hl_font = QFont(font)
            hl_font.setBold(False)
            p.setFont(hl_font)
            # soft halo (text-shadow look): the glyph drawn on a ring, twice
            ring = ((1, 0), (-1, 0), (0, 1), (0, -1), (.7, .7), (-.7, .7), (.7, -.7), (-.7, -.7))
            for rad, alpha in ((min(0.24 * z, 7.0), 10), (min(0.14 * z, 4.0), 22), (min(0.07 * z, 1.8), 44)):
                p.setPen(QColor(244, 194, 103, alpha))
                for idx in vis:
                    r, c = divmod(int(idx), w)
                    x, y = self._sx(c), self._sy(r + 0.5) + base_off
                    ch = text[int(idx)]
                    for dx, dy in ring:
                        p.drawText(QPointF(x + dx * rad, y + dy * rad), ch)
            p.setPen(theme.GOLD)
            for idx in vis:
                r, c = divmod(int(idx), w)
                p.drawText(QPointF(self._sx(c), self._sy(r + 0.5) + base_off), text[int(idx)])

    # -- image (zoomed out text modes, and colour modes)
    def _paint_image(self, p: QPainter) -> None:
        img = self._texture()
        z, pitch = self.z, self.pitch()
        c0, c1, r0, r1 = self._visible()
        if c1 <= c0 or r1 <= r0:
            return
        smooth = z < 2.2
        p.setRenderHint(QPainter.SmoothPixmapTransform, smooth)
        if self.is_text():
            src = QRectF(c0, r0 * 2, c1 - c0, (r1 - r0) * 2)
            ph = z * pitch
            tgt = QRectF(self._sx(c0), self._sy(r0) + 0.25 * ph, (c1 - c0) * z, (r1 - r0) * ph)
        else:
            src = QRectF(c0, r0, c1 - c0, r1 - r0)
            tgt = QRectF(self._sx(c0), self._sy(r0), (c1 - c0) * z, (r1 - r0) * z)
        p.drawImage(tgt, img, src)

        if not self.is_text():
            w = self.grid_w()
            if z >= 30:   # labels inside the squares
                p.setRenderHint(QPainter.TextAntialiasing, True)
                font, px = self._font_for(z * 0.55)
                font.setLetterSpacing(QFont.AbsoluteSpacing, 0)
                p.setFont(font)
                fm = QFontMetricsF(font)
                for r in range(r0, r1):
                    for c in range(c0, c1):
                        i = r * w + c
                        if i >= len(self.darr):
                            break
                        d = int(self.darr[i])
                        light = (d in (5, 6, 7)) if self.mode == Mode.COLORS else (d >= 5)
                        p.setPen(QColor(10, 10, 20, 200) if light else QColor(255, 255, 255, 190))
                        ch = str(d)
                        p.drawText(
                            QPointF(self._sx(c) + (z - fm.horizontalAdvance(ch)) / 2, self._sy(r) + z / 2 + 0.36 * px),
                            ch,
                        )
            cells = self._highlight_cells()
            if cells is not None and len(cells) and z >= 3:
                vis = cells[(cells // w >= r0) & (cells // w < r1)]
                p.setRenderHint(QPainter.Antialiasing, True)
                for idx in vis:
                    r, c = divmod(int(idx), w)
                    rect = QRectF(self._sx(c), self._sy(r), z, z)
                    self._paint_glow(p, rect)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(theme.GOLD, max(1.5, z * 0.06)))
                for idx in vis:
                    r, c = divmod(int(idx), w)
                    p.drawRect(QRectF(self._sx(c), self._sy(r), z, z))

    # -- thin amber band + dot when the match is too small to see
    def _paint_far_markers(self, p: QPainter) -> None:
        cells = self._highlight_cells()
        if cells is None or not len(cells):
            return
        w, pitch, z = self.grid_w(), self.pitch(), self.z
        if self.is_text() and z >= FAR_Z:
            return
        if (not self.is_text()) and z >= 3:
            return
        cols, rws = cells % w, cells // w
        rmin, rmax, cmin, cmax = int(rws.min()), int(rws.max()), int(cols.min()), int(cols.max())
        y_top, y_bot = self._sy(rmin), self._sy(rmax + 1)
        thick = max(3.0, y_bot - y_top)
        yc = (y_top + y_bot) / 2
        band = QRectF(0, yc - thick / 2, self.width(), thick)
        grad = QLinearGradient(0, band.top(), 0, band.bottom())
        grad.setColorAt(0.0, QColor(244, 194, 103, 0))
        grad.setColorAt(0.5, QColor(244, 194, 103, 120))
        grad.setColorAt(1.0, QColor(244, 194, 103, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(band.adjusted(0, -thick, 0, thick))
        p.setPen(QPen(QColor(255, 244, 220, 230), 1))
        p.drawLine(QPointF(0, yc), QPointF(self.width(), yc))
        # marker dot
        xm = self._sx((cmin + cmax + 1) / 2)
        rg = QRadialGradient(QPointF(xm, yc), 14)
        rg.setColorAt(0.0, QColor(255, 236, 190, 255))
        rg.setColorAt(0.25, QColor(244, 194, 103, 200))
        rg.setColorAt(1.0, QColor(244, 194, 103, 0))
        p.setBrush(QBrush(rg))
        p.drawEllipse(QPointF(xm, yc), 14, 14)

    def _paint_fades(self, p: QPainter) -> None:
        h = self.height()
        g = QLinearGradient(0, h - 150, 0, h)
        g.setColorAt(0, QColor(10, 10, 18, 0))
        g.setColorAt(1, QColor(10, 10, 18, 215))
        p.fillRect(QRectF(0, h - 150, self.width(), 150), QBrush(g))
        g2 = QLinearGradient(0, 0, 0, 90)
        g2.setColorAt(0, QColor(10, 10, 18, 200))
        g2.setColorAt(1, QColor(10, 10, 18, 0))
        p.fillRect(QRectF(0, 0, self.width(), 90), QBrush(g2))

    def _paint_hud(self, p: QPainter) -> None:
        w = self.grid_w()
        names = {Mode.NUMBERS: "NUMBERS", Mode.LETTERS: f"LETTERS · FRAME {self.frame}",
                 Mode.COLORS: "COLORS", Mode.BW: "BLACK & WHITE"}
        idx = self.focus_digit() + 1
        lines = [
            f"VIEW      {names[self.mode]}",
            f"ZOOM      {self.z:,.2f} px/col",
            f"CENTRE    row {int(self.cy) + 1:,} · col {int(self.cx) + 1:,}",
            f"DIGIT     ~{idx:,} / {len(self.digits):,}",
            f"GRID      {w} cols × {self.rows():,} rows",
            f"FPS       {self._fps:.0f}",
        ]
        font = theme.mono_font(10, spacing=0.6)
        p.setFont(font)
        fm = QFontMetricsF(font)
        bw = max(fm.horizontalAdvance(s) for s in lines) + 26
        bh = len(lines) * 16 + 18
        rect = QRectF(self.width() - bw - 16, 54, bw, bh)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(theme.BORDER, 1))
        p.setBrush(QColor(9, 11, 22, 225))
        p.drawRoundedRect(rect, 6, 6)
        p.setPen(theme.MUTED)
        for i, s in enumerate(lines):
            p.drawText(QPointF(rect.left() + 13, rect.top() + 22 + i * 16), s)
