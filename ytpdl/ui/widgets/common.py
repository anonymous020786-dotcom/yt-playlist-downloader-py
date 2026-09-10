"""Small shared UI helpers: section cards, headings, an async thumbnail label,
and a transient toast overlay.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

log = logging.getLogger(__name__)
_pool = QThreadPool.globalInstance()


def card(*children: QWidget, spacing: int = 14, margins: tuple[int, int, int, int] = (18, 18, 18, 18)) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    for c in children:
        lay.addWidget(c)
    return frame


def heading(text: str, level: int = 1) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("H1" if level == 1 else "H2")
    return lbl


def dim(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Dim")
    lbl.setWordWrap(True)
    return lbl


def pill(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Pill")
    lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    return lbl


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: palette(mid);")
    line.setFixedHeight(1)
    return line


def row(*widgets: QWidget, spacing: int = 8, stretch_last: bool = False) -> QWidget:
    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    for i, w in enumerate(widgets):
        lay.addWidget(w, 1 if (stretch_last and i == len(widgets) - 1) else 0)
    return holder


# --------------------------------------------------------------------------- #
#  Async thumbnail
# --------------------------------------------------------------------------- #
class _FetchSignals(QObject):
    done = Signal(bytes)


class _FetchTask(QRunnable):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = _FetchSignals()

    def run(self) -> None:
        try:
            import requests

            resp = requests.get(self.url, timeout=10)
            resp.raise_for_status()
            self.signals.done.emit(resp.content)
        except Exception as exc:  # noqa: BLE001
            log.debug("thumbnail fetch failed: %s", exc)
            self.signals.done.emit(b"")


class Thumbnail(QLabel):
    """A rounded thumbnail that loads its image off the UI thread."""

    def __init__(self, width: int = 160, height: int = 90) -> None:
        super().__init__()
        self._w, self._h = width, height
        self.setFixedSize(width, height)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setStyleSheet("background: palette(mid); border-radius: 8px;")
        self.setText("—")

    def load(self, url: str) -> None:
        if not url:
            return
        task = _FetchTask(url)
        task.signals.done.connect(self._apply)
        _pool.start(task)

    def _apply(self, data: bytes) -> None:
        if not data:
            return
        pix = QPixmap()
        if not pix.loadFromData(data):
            return
        scaled = pix.scaled(
            self._w, self._h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        self.setPixmap(scaled)


# --------------------------------------------------------------------------- #
#  Toast
# --------------------------------------------------------------------------- #
class Toast(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, msec: int = 2600) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 32
            self.move(max(12, x), max(12, y))
        self._effect.setOpacity(0.96)
        self.show()
        self.raise_()
        self._timer.start(msec)
