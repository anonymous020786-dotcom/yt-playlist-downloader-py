"""Application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import config
from .core.settings import SettingsStore
from .i18n import translator
from .ui.main_window import MainWindow
from .ui.theme import apply_theme


def _setup_logging() -> None:
    config.ensure_dirs()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config.ERROR_LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> int:
    _setup_logging()
    config.clean_temp_dir()

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setOrganizationName("YTPDL")
    for icon_path in (config.ICON_ICO_FILE, config.ICON_FILE):
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            break

    settings = SettingsStore()
    translator.set_locale(settings.app.language)
    app.setLayoutDirection(Qt.RightToLeft if translator.is_rtl else Qt.LeftToRight)
    apply_theme(app, settings.app.theme, settings.app.accent)

    window = MainWindow(settings)
    window.show()

    exit_code = app.exec()
    settings.save()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
