"""Settings: appearance, language, downloads, updates."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ... import __version__, config
from ...core.settings import SettingsStore
from ...i18n import available_locales, tr
from ..widgets.common import heading
from ..workers import UpdateWorker


class SettingsPage(QWidget):
    theme_changed = Signal()
    language_changed = Signal(str)

    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self._settings = settings
        self._pool = QThreadPool.globalInstance()
        self._build()
        self._load()
        self._wire()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)
        outer.addWidget(heading(tr("Settings")))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 8, 0)
        col.setSpacing(16)

        # -- appearance -------------------------------------------------
        self.theme = QComboBox()
        self.theme.addItem(tr("FollowSystem"), "system")
        self.theme.addItem(tr("Light"), "light")
        self.theme.addItem(tr("Dark"), "dark")
        self.accent = QComboBox()
        for name in config.ACCENTS:
            self.accent.addItem(name, name)
        self.language = QComboBox()
        for loc in available_locales():
            self.language.addItem(loc.label, loc.code)

        appearance = QFormLayout()
        appearance.setSpacing(10)
        appearance.addRow(QLabel(tr("DarkTheme")), self.theme)
        appearance.addRow(QLabel(tr("AccentColor")), self.accent)
        appearance.addRow(QLabel(tr("Language")), self.language)
        col.addWidget(_section(tr("Appearance"), appearance))

        # -- downloads ------------------------------------------------
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 8)
        self.rate_limit = QSpinBox()
        self.rate_limit.setRange(0, 1_000_000)
        self.rate_limit.setSingleStep(128)
        self.cookies = QComboBox()
        self.cookies.addItem(tr("None"), "")
        for b in ("chrome", "firefox", "edge", "brave", "chromium", "opera", "vivaldi", "safari"):
            self.cookies.addItem(b.capitalize(), b)

        downloads = QFormLayout()
        downloads.setSpacing(10)
        downloads.addRow(QLabel(tr("ConcurrentDownloads")), self.concurrency)
        downloads.addRow(QLabel(tr("RateLimit")), self.rate_limit)
        downloads.addRow(QLabel(tr("CookiesFromBrowser")), self.cookies)
        col.addWidget(_section(tr("Downloads"), downloads))

        # -- general -------------------------------------------------
        self.save_options = QCheckBox(tr("SaveDownloadOptions"))
        self.confirm_exit = QCheckBox(tr("ConfirmExit"))
        self.check_updates = QCheckBox(tr("CheckForUpdates"))
        general = QVBoxLayout()
        general.setSpacing(8)
        for w in (self.save_options, self.confirm_exit, self.check_updates):
            general.addWidget(w)

        upd_row = QHBoxLayout()
        self.update_btn = QPushButton(tr("CheckForUpdatesNow"))
        self.update_btn.setObjectName("Ghost")
        self.update_status = QLabel(f"v{__version__}")
        self.update_status.setObjectName("Dim")
        upd_row.addWidget(self.update_btn)
        upd_row.addWidget(self.update_status, 1)
        general.addLayout(upd_row)
        col.addWidget(_section(tr("General"), general))

        # -- danger zone --------------------------------------------
        self.restore_btn = QPushButton(tr("RestoreDefaults"))
        self.restore_btn.setObjectName("Danger")
        col.addWidget(self.restore_btn)
        col.addStretch(1)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    def _load(self) -> None:
        a = self._settings.app
        self.theme.setCurrentIndex(max(0, self.theme.findData(a.theme)))
        self.accent.setCurrentIndex(max(0, self.accent.findData(a.accent)))
        self.language.setCurrentIndex(max(0, self.language.findData(a.language)))
        self.concurrency.setValue(a.concurrent_downloads)
        self.rate_limit.setValue(a.rate_limit_kib)
        self.cookies.setCurrentIndex(max(0, self.cookies.findData(a.cookies_from_browser)))
        self.save_options.setChecked(a.save_download_options)
        self.confirm_exit.setChecked(a.confirm_on_exit)
        self.check_updates.setChecked(a.check_for_updates)

    def _wire(self) -> None:
        self.theme.currentIndexChanged.connect(self._apply_theme)
        self.accent.currentIndexChanged.connect(self._apply_theme)
        self.language.currentIndexChanged.connect(self._apply_language)
        self.concurrency.valueChanged.connect(
            lambda v: setattr(self._settings.app, "concurrent_downloads", v))
        self.rate_limit.valueChanged.connect(
            lambda v: setattr(self._settings.app, "rate_limit_kib", v))
        self.cookies.currentIndexChanged.connect(
            lambda _i: setattr(self._settings.app, "cookies_from_browser", self.cookies.currentData()))
        self.save_options.toggled.connect(
            lambda v: setattr(self._settings.app, "save_download_options", v))
        self.confirm_exit.toggled.connect(
            lambda v: setattr(self._settings.app, "confirm_on_exit", v))
        self.check_updates.toggled.connect(
            lambda v: setattr(self._settings.app, "check_for_updates", v))
        self.update_btn.clicked.connect(self.run_update_check)
        self.restore_btn.clicked.connect(self._restore)

    # ------------------------------------------------------------------ slots
    def _apply_theme(self) -> None:
        self._settings.app.theme = self.theme.currentData()
        self._settings.app.accent = self.accent.currentData()
        self.theme_changed.emit()

    def _apply_language(self) -> None:
        code = self.language.currentData()
        self._settings.app.language = code
        self.language_changed.emit(code)

    def run_update_check(self) -> None:
        self.update_status.setText(tr("Analyzing"))
        worker = UpdateWorker()
        worker.signals.ok.connect(self._on_update_info)
        self._pool.start(worker)

    def _on_update_info(self, info) -> None:
        if info is None:
            self.update_status.setText(tr("ErrorWhileUpdating"))
            return
        if info.update_available:
            self.update_status.setText(f"{tr('NewVersionAvailable')}: {info.latest} → {info.url}")
        else:
            self.update_status.setText(tr("UpToDate"))

    def _restore(self) -> None:
        self._settings.restore_defaults()
        self._load()
        self.theme_changed.emit()
        self.language_changed.emit(self._settings.app.language)


def _section(title: str, inner) -> QWidget:
    box = QWidget()
    box.setObjectName("Card")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(12)
    lay.addWidget(heading(title, level=2))
    if isinstance(inner, (QFormLayout, QVBoxLayout, QHBoxLayout)):
        lay.addLayout(inner)
    else:
        lay.addWidget(inner)
    return box
