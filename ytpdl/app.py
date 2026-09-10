"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, config
from .core.settings import SettingsStore


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


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ytpdl",
        description=f"{config.APP_NAME} — download YouTube playlists, channels and videos.",
    )
    parser.add_argument("--version", action="version", version=f"ytpdl {__version__}")
    parser.add_argument(
        "url", nargs="?",
        help="optional link to pre-fill on the Home screen at startup",
    )
    # let Qt keep its own flags (-style, -platform, …)
    return parser.parse_known_args(argv)[0]


def main() -> int:
    args = _parse_args(sys.argv[1:])
    _setup_logging()
    config.clean_temp_dir()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from .i18n import translator
    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

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
    if args.url:
        window._home._search.setText(args.url.strip())
    window.show()

    exit_code = app.exec()
    settings.save()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
