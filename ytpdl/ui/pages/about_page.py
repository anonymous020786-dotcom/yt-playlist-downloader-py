"""About: credits, version, environment status, links, shortcuts."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import __version__, config
from ...core.ffmpeg import ffmpeg_path, ffmpeg_version
from ...i18n import tr
from ..widgets.common import dim, heading


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        root.addWidget(heading(tr("About")))
        root.addWidget(self._about_card())
        root.addWidget(self._environment_card())
        root.addWidget(self._shortcuts_card())
        root.addStretch(1)

    def _about_card(self) -> QFrame:
        box = QFrame()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        lay.addWidget(heading(config.APP_NAME, level=2))
        lay.addWidget(dim(f"Version {__version__} · PySide6 rewrite of the WPF original"))
        blurb = QLabel(
            "A free, open-source downloader for YouTube playlists, channels and "
            "single videos, built on yt-dlp and FFmpeg.\n\n"
            "This program does not host or redistribute any content. You are "
            "responsible for complying with YouTube's Terms of Service and with "
            "the copyright law in your jurisdiction."
        )
        blurb.setWordWrap(True)
        blurb.setObjectName("Dim")
        lay.addWidget(blurb)

        links = QHBoxLayout()
        for label, url in (
            ("Original project", f"https://github.com/{config.GITHUB_REPO}"),
            ("yt-dlp", "https://github.com/yt-dlp/yt-dlp"),
            ("FFmpeg", "https://ffmpeg.org"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("Ghost")
            btn.clicked.connect(lambda _c=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            links.addWidget(btn)
        links.addStretch(1)
        lay.addLayout(links)
        return box

    def _environment_card(self) -> QFrame:
        box = QFrame()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        lay.addWidget(heading("Environment", level=2))

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        try:
            import yt_dlp

            ytdlp_ver = yt_dlp.version.__version__
        except Exception:  # noqa: BLE001
            ytdlp_ver = "—"

        ff = ffmpeg_path()
        ff_text = f"{ffmpeg_version() or 'found'}  ·  {ff}" if ff else "not found"

        rows = [
            ("yt-dlp", ytdlp_ver),
            ("FFmpeg", ff_text),
            ("Settings folder", str(config.APP_DATA_DIR)),
        ]
        for i, (key, value) in enumerate(rows):
            k = QLabel(key)
            v = QLabel(value)
            v.setObjectName("Dim")
            v.setWordWrap(True)
            v.setTextInteractionFlags(v.textInteractionFlags().TextSelectableByMouse)
            grid.addWidget(k, i, 0)
            grid.addWidget(v, i, 1)
        lay.addLayout(grid)
        return box

    def _shortcuts_card(self) -> QFrame:
        box = QFrame()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(8)
        lay.addWidget(heading("Keyboard shortcuts", level=2))
        for keys, what in (
            ("Ctrl+1 … Ctrl+5", "Switch between pages"),
            ("Ctrl+L", "Focus the link box"),
            ("Enter", "Analyze the link / start"),
        ):
            row = QHBoxLayout()
            k = QLabel(keys)
            k.setObjectName("Pill")
            w = QLabel(what)
            w.setObjectName("Dim")
            row.addWidget(k)
            row.addWidget(w, 1)
            lay.addLayout(row)
        return box
