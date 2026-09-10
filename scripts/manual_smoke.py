"""Headless smoke test: build every page + the main window, then quit."""

from __future__ import annotations

import faulthandler
import sys

faulthandler.dump_traceback_later(25, exit=True)

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
print("qapp ok", flush=True)

from ytpdl.core.settings import SettingsStore
from ytpdl.i18n import translator
from ytpdl.ui.theme import apply_theme

settings = SettingsStore()
settings.app.check_for_updates = False  # don't hit the network in the test
settings.app.confirm_on_exit = False  # QMessageBox blocks under QT_QPA_PLATFORM=offscreen
translator.set_locale(settings.app.language)
apply_theme(app, settings.app.theme, settings.app.accent)
print("theme ok", flush=True)

from ytpdl.ui.main_window import MainWindow

win = MainWindow(settings)
win.show()
print("window ok", flush=True)

# exercise a resolve against a tiny public playlist if a network flag is passed
if "--net" in sys.argv:
    from ytpdl.core.resolver import resolve

    src = resolve("https://www.youtube.com/playlist?list=PLbpi6ZahtOH6Blw3RGYpWkSByi_T7Rygb")
    print(f"resolved: {src.kind} '{src.title}' ({src.count} videos)", flush=True)

QTimer.singleShot(500, app.quit)
code = app.exec()
print("exec returned", code, flush=True)
faulthandler.cancel_dump_traceback_later()
