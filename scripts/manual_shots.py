"""Capture screenshots of several pages / states for review.

    YTPDL_DATA_DIR=$(mktemp -d) python scripts/manual_shots.py
"""

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
s.app.options_expanded = True
translator.set_locale("en")
apply_theme(app, "dark", s.app.accent)
w = MainWindow(s)
w.resize(1180, 860)
w.show()

titles = [
    "Building a Rust web server from scratch — part 1",
    "The physics of skipping stones (slow motion)",
    "I visited the world's quietest room",
    "How compilers actually work",
    "A history of the synthesizer in 12 sounds",
    "Why bridges don't fall down (usually)",
]
fake = ResolvedSource(
    kind=SourceKind.PLAYLIST,
    title="Deep dives — engineering & science",
    url="https://youtube.com/playlist?list=x",
    author="Longform Channel",
    thumbnail="",
    videos=[
        VideoInfo(f"vid{i:08d}", titles[i % len(titles)], "u", "Longform Channel", 600 + i * 47)
        for i in range(23)
    ],
)

seq = iter(["home", "resolved", "light", "queue", "settings", "about", "rtl", "done"])
state = {"cur": next(seq)}


def step():
    cur = state["cur"]
    if cur == "home":
        w.grab().save("scripts/_home.png")
    elif cur == "resolved":
        w._home._on_resolved(fake, w._home._resolve_token)
        w.grab().save("scripts/_home_resolved.png")
    elif cur == "light":
        apply_theme(app, "light", s.app.accent)
        w._home._on_resolved(fake, w._home._resolve_token)
        w.grab().save("scripts/_light.png")
    elif cur == "queue":
        apply_theme(app, "dark", s.app.accent)
        w._on_queue_requested([fake])
        w.grab().save("scripts/_queue.png")
    elif cur == "settings":
        w._select(3)
        w.grab().save("scripts/_settings.png")
    elif cur == "about":
        w._select(4)
        w.grab().save("scripts/_about.png")
    elif cur == "rtl":
        translator.set_locale("ar")
        app.setLayoutDirection(Qt.RightToLeft)
        w._select(0)
        w.grab().save("scripts/_rtl_arabic.png")
    else:
        app.quit()
        return
    state["cur"] = next(seq)
    QTimer.singleShot(250, step)


QTimer.singleShot(500, step)
sys.exit(app.exec())
