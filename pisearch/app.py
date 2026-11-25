"""Main window and entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from . import search as S
from . import theme
from .canvas import Mode
from .pi_compute import HAVE_GMPY2, Cancelled, compute_pi_digits, has_expected_digit_count
from .recorder import HAVE_PIL, Recorder
from .resources import available_physical_memory, resource_warning
from .shape_dialog import ShapeDialog
from .widgets import ExplorerPage, InfoCard, StartPage

RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"


class PiWorker(QThread):
    progress = Signal(float, str)
    done = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, n_digits: int):
        super().__init__()
        self.n = n_digits
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        def cb(frac: float, msg: str) -> None:
            if self._cancel:
                raise Cancelled()
            self.progress.emit(frac, msg)

        try:
            self.done.emit(
                compute_pi_digits(self.n, cb, cancel_check=lambda: self._cancel)
            )
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("π Explorer")
        self.resize(1180, 760)
        self.setMinimumSize(900, 560)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start = StartPage()
        self.explorer = ExplorerPage()
        self.stack.addWidget(self.start)
        self.stack.addWidget(self.explorer)

        self.canvas = self.explorer.canvas
        self.toolbar = self.explorer.toolbar
        self.card = self.explorer.card
        self.worker: Optional[PiWorker] = None
        self._cancel_requested = False
        self.recorder = Recorder(self.canvas, RECORDINGS_DIR)
        self.recorder.saved.connect(self._on_recording_saved)
        self.recorder.limitReached.connect(self._stop_recording_from_limit)

        self.start.computeRequested.connect(self.compute)
        self.start.cancelRequested.connect(self.cancel_compute)
        self.explorer.tabs.modeChanged.connect(self.on_tab)
        self.toolbar.searchRequested.connect(self.on_search)
        self.toolbar.shapeClicked.connect(self.on_shape)
        self.toolbar.recToggled.connect(self.on_rec)
        self.toolbar.hudToggled.connect(self.on_hud)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.back_to_start)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: self.toolbar.edit.setFocus())

    # ----------------------------------------------------------- computing
    def compute(self, n_digits: int) -> None:
        if self.worker is not None:
            return
        warning = resource_warning(n_digits, available_physical_memory())
        if warning:
            self.start.set_message(warning, error=True)
            return
        self.start.set_busy(True)
        self.start.set_message("")
        self._cancel_requested = False
        self.worker = PiWorker(n_digits)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_computed)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.start()

    def _on_progress(self, fraction: float, text: str) -> None:
        if not self._cancel_requested:
            self.start.set_progress(fraction, text)

    def cancel_compute(self) -> None:
        if self.worker is None or self._cancel_requested:
            return
        self._cancel_requested = True
        self.start.cancel_btn.setEnabled(False)
        self.start.set_message("CANCELLING…")
        self.worker.cancel()

    def _on_computed(self, digits: str) -> None:
        requested = self.worker.n if self.worker is not None else None
        if self._cancel_requested:
            self._finish_cancelled()
            return
        self._join_worker()
        self.start.set_busy(False)
        if requested is None or not has_expected_digit_count(digits, requested):
            actual = len(digits)
            expected = f"{requested:,}" if requested is not None else "the requested"
            self.start.set_message(
                f"ERROR · expected {expected} digits but computed {actual:,}; "
                "the result was not loaded.",
                error=True,
            )
            return
        self.canvas.set_data(digits)
        self.canvas.mode = Mode.NUMBERS
        self.explorer.tabs.set_mode(Mode.NUMBERS)
        self.toolbar.set_letters(False)
        self.card.hide()
        self.stack.setCurrentIndex(1)
        self.explorer.layout_overlays()
        QTimer.singleShot(60, self.canvas.intro)
        self.toolbar.edit.setFocus()

    def _on_failed(self, msg: str) -> None:
        self._join_worker()
        self.start.set_busy(False)
        if self._cancel_requested:
            self._cancel_requested = False
            self.start.set_message("CANCELLED")
            return
        self.start.set_message(f"ERROR · {msg}", error=True)

    def _on_cancelled(self) -> None:
        self._finish_cancelled()

    def _finish_cancelled(self) -> None:
        self._join_worker()
        self.start.set_busy(False)
        self._cancel_requested = False
        self.start.set_message("CANCELLED")

    def _join_worker(self) -> None:
        if self.worker is not None:
            self.worker.wait()
            self.worker = None

    def back_to_start(self) -> None:
        if self.recorder.recording:
            self.toolbar.set_recording(False)
            self.recorder.stop()
        self.start.set_message("")
        self.stack.setCurrentIndex(0)

    # --------------------------------------------------------------- tabs
    def on_tab(self, i: int) -> None:
        mode = Mode(i)
        self.toolbar.set_letters(mode == Mode.LETTERS)
        self.canvas.set_mode(mode)
        self.canvas.update()

    def _switch_tab(self, mode: Mode, frame: Optional[str] = None) -> None:
        if self.canvas.mode != mode or (frame and frame != self.canvas.frame):
            self.explorer.tabs.set_mode(mode)
            self.toolbar.set_letters(mode == Mode.LETTERS)
            self.canvas.set_mode(mode, frame)

    # ------------------------------------------------------------- search
    def on_search(self, mode_label: str, text: str) -> None:
        if not self.canvas.has_data():
            return
        if mode_label == "WORD":
            match = S.search_word(self.canvas.frames, text)
        else:
            q = S.normalize_date(text) if mode_label == "DATE" else S.normalize_number(text)
            match = S.search_digits(self.canvas.digits, q)
        self.show_result(match)

    def on_shape(self) -> None:
        if not self.canvas.has_data():
            return
        dlg = ShapeDialog(self)
        if dlg.exec() != ShapeDialog.Accepted:
            return
        cells = dlg.cells()
        if not cells:
            return
        if self.canvas.mode == Mode.LETTERS or self.canvas.mode == Mode.NUMBERS:
            self._switch_tab(Mode.COLORS)
        w = self.canvas.grid_w(Mode.COLORS)
        self.show_result(S.search_shape(self.canvas.darr, w, cells))

    def show_result(self, m: S.Match) -> None:
        g = InfoCard._gold
        if m.error:
            self.canvas.set_highlight(None)
            self.card.show_card("notfound", "CHECK YOUR INPUT", m.error)
            return
        if m.found:
            if m.kind == "letters":
                self._switch_tab(Mode.LETTERS, m.frame)
            elif self.canvas.mode == Mode.LETTERS:
                self._switch_tab(Mode.NUMBERS)
            self.canvas.set_highlight(m)
            self.canvas.fly_to_highlight()
            n = f"<b style='color:#e6ebfa;'>{m.count:,}</b>"
            if m.kind == "digits":
                body = (f"{g(m.query)} ({len(m.query)} digits) · {n} occurrence(s) in {m.searched:,} digits")
                title = f"FOUND — POSITION {m.position:,}"
            elif m.kind == "letters":
                body = (f"‘{g(m.query)}’ · Frame {m.frame} · digit {m.digit_pos:,} of π · {n} occurrence(s)")
                title = f"FOUND — LETTER {m.position:,}"
            else:
                body = f"{g('SHAPE')} ({m.cells} cells) · {n} occurrence(s) in {m.searched:,} digits"
                title = f"FOUND — POSITION {m.position:,}"
            self.card.show_card("found", title, body)
            return

        self.canvas.set_highlight(None)
        exp = f"<b style='color:{theme.GOLD.name()};'>{m.expected:,}</b>"
        tail = f"Expected around {exp} digits deep. Beyond this page, but a desktop program could find it."
        if m.kind == "letters":
            head = f"“{g(m.query)}” ({len(m.query)} letters) isn’t in the first {m.searched:,} letters of either frame."
        elif m.kind == "digits":
            head = f"“{g(m.query)}” ({len(m.query)} digits) isn’t in the first {m.searched:,} digits."
        else:
            head = f"This {g('SHAPE')} ({m.cells} cells) isn’t in the first {m.searched:,} digits."
        self.card.show_card("notfound", "NOT FOUND", f"{head}<br>{tail}")

    # ----------------------------------------------------------- HUD / REC
    def on_hud(self, on: bool) -> None:
        self.canvas.show_hud = on
        self.canvas.update()

    def on_rec(self, on: bool) -> None:
        if on:
            if not self.recorder.start():
                self.toolbar.set_recording(False)
                self.card.show_card("notfound", "REC NEEDS PILLOW", "Install it with: pip install pillow")
        else:
            self.recorder.stop()
            self.card.show_card("found", "SAVING GIF…", "Encoding your recording, one moment.")

    def _stop_recording_from_limit(self) -> None:
        self.toolbar.set_recording(False)
        self.recorder.stop()
        self.card.show_card("found", "SAVING GIF…", "30 second limit reached.")

    def _on_recording_saved(self, path: str) -> None:
        if path:
            self.card.show_card("found", "RECORDING SAVED", path)
        else:
            self.card.show_card("notfound", "RECORDING FAILED", "Nothing was saved (recording too short?).")

    def closeEvent(self, e):
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait()
        if self.recorder.recording:
            self.recorder.stop()
        super().closeEvent(e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pisearch", description="π Explorer - search numbers, dates and words in pi")
    ap.add_argument("--digits", type=int, help="compute this many digits right away (skip the start screen)")
    args = ap.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("π Explorer")
    app.setStyleSheet(theme.stylesheet())
    win = MainWindow()
    win.show()
    if not HAVE_GMPY2:
        win.start.set_message("TIP · pip install gmpy2  for much faster computing")
    if args.digits:
        win.compute(args.digits)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
