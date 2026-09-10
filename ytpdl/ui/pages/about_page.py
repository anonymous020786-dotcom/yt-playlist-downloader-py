"""About: credits, version, links, changelog blurb."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ... import __version__, config
from ...i18n import tr
from ..widgets.common import dim, heading


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        root.addWidget(heading(tr("About")))

        box = QWidget()
        box.setObjectName("Card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        lay.addWidget(heading(f"{config.APP_NAME}", level=2))
        lay.addWidget(dim(f"Version {__version__} · PySide6 rewrite"))
        blurb = QLabel(
            "A free, open-source downloader for YouTube playlists, channels and "
            "single videos. Powered by yt-dlp and FFmpeg.\n\n"
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

        root.addWidget(box)
        root.addStretch(1)
