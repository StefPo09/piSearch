"""REC: record the canvas to an animated GIF."""
from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

try:
    from PIL import Image

    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False


class Recorder(QObject):
    saved = Signal(str)      # path of the GIF (or "" on failure)
    limitReached = Signal()

    def __init__(self, widget: QWidget, out_dir: Path, fps: int = 12, max_seconds: int = 30, max_width: int = 720):
        super().__init__()
        self.widget, self.out_dir = widget, Path(out_dir)
        self.fps, self.max_frames, self.max_width = fps, fps * max_seconds, max_width
        self._frames: List[bytes] = []
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / fps))
        self._timer.timeout.connect(self._grab)
        self.recording = False

    def start(self) -> bool:
        if not HAVE_PIL:
            return False
        self._frames = []
        self.recording = True
        self._timer.start()
        return True

    def _grab(self) -> None:
        img: QImage = self.widget.grab().toImage()
        if img.width() > self.max_width:
            img = img.scaledToWidth(self.max_width, Qt.SmoothTransformation)
        img = img.convertToFormat(QImage.Format_RGBA8888)
        pil = Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()), "raw", "RGBA", 0, 1)
        buf = io.BytesIO()
        pil.convert("RGB").save(buf, "JPEG", quality=88)
        self._frames.append(buf.getvalue())
        if len(self._frames) >= self.max_frames:
            self.limitReached.emit()

    def stop(self) -> None:
        if not self.recording:
            return
        self.recording = False
        self._timer.stop()
        frames, self._frames = self._frames, []
        threading.Thread(target=self._write, args=(frames,), daemon=True).start()

    def _write(self, frames: List[bytes]) -> None:
        try:
            if len(frames) < 2:
                self.saved.emit("")
                return
            self.out_dir.mkdir(parents=True, exist_ok=True)
            path = self.out_dir / time.strftime("pi_%Y%m%d_%H%M%S.gif")
            imgs = [Image.open(io.BytesIO(b)).convert("P", palette=Image.ADAPTIVE, colors=128) for b in frames]
            imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=int(1000 / self.fps), loop=0, optimize=False)
            self.saved.emit(str(path))
        except Exception:
            self.saved.emit("")
