"""Capture screenshots of several pages / states for review."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from ytpdl.core.models import ResolvedSource, SourceKind, VideoInfo
from ytpdl.core.settings import SettingsStore
from ytpdl.i18n import translator
from ytpdl.ui.theme import apply_theme
from ytpdl.ui.main_window import MainWindow

s = SettingsStore()
s.app.check_for_updates = False
translator.set_locale("en")
apply_theme(app, "dark", s.app.accent)
w = MainWindow(s)
w.resize(1180, 800)
w.show()

fake = ResolvedSource(
    kind=SourceKind.PLAYLIST,
    title="Lo-fi beats to code to — 2024 mix",
    url="https://youtube.com/playlist?list=x",
    author="Chillhop Music",
    thumbnail="",
    videos=[VideoInfo(f"id{i:09d}", f"Track {i}", "u", "Artist", 200 + i) for i in range(42)],
)

shots = []


def step():
    if not shots:
        w._home._on_resolved(fake, w._home._resolve_token)
        w.grab().save("scripts/_home_resolved.png")
        shots.append(1)
        QTimer.singleShot(200, step)
    elif shots == [1]:
        w._on_queue_requested([fake, fake])
        w.grab().save("scripts/_queue.png")
        shots.append(2)
        QTimer.singleShot(200, step)
    elif shots == [1, 2]:
        w._select(3)
        w.grab().save("scripts/_settings.png")
        shots.append(3)
        QTimer.singleShot(200, step)
    else:
        translator.set_locale("ar")
        app.setLayoutDirection(Qt.RightToLeft)
        w._select(0)
        w.grab().save("scripts/_rtl_arabic.png")
        app.quit()


QTimer.singleShot(400, step)
sys.exit(app.exec())
