"""Settings: appearance, language, downloads, updates."""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
    concurrency_changed = Signal(int)
    subscriptions_changed = Signal()

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

        self.save_dir = QLineEdit()
        self.save_dir.setReadOnly(True)
        browse = QPushButton(tr("Browse"))
        browse.clicked.connect(self._pick_folder)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.save_dir, 1)
        dir_row.addWidget(browse)

        downloads = QFormLayout()
        downloads.setSpacing(10)
        downloads.addRow(QLabel(tr("SaveDirectory")), dir_row)
        downloads.addRow(QLabel(tr("ConcurrentDownloads")), self.concurrency)
        downloads.addRow(QLabel(tr("RateLimit")), self.rate_limit)
        downloads.addRow(QLabel(tr("CookiesFromBrowser")), self.cookies)
        col.addWidget(_section(tr("Downloads"), downloads))

        # -- subscriptions --------------------------------------------
        self.check_subs = QCheckBox(tr("AutomaticllyDownloadSubscriptions"))
        self.sub_interval = QSpinBox()
        self.sub_interval.setRange(5, 1440)
        self.sub_interval.setSuffix(f" {tr('Minutes')}")
        subs = QFormLayout()
        subs.setSpacing(10)
        subs.addRow(self.check_subs)
        subs.addRow(QLabel(tr("SubscriptionsUpdateDelay")), self.sub_interval)
        col.addWidget(_section(tr("Subscriptions"), subs))

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
        self.save_dir.setText(a.save_directory)
        self.check_subs.setChecked(a.check_subscriptions)
        self.sub_interval.setValue(a.subscription_interval_minutes)

    def _wire(self) -> None:
        self.theme.currentIndexChanged.connect(self._apply_theme)
        self.accent.currentIndexChanged.connect(self._apply_theme)
        self.language.currentIndexChanged.connect(self._apply_language)
        self.concurrency.valueChanged.connect(self._set_concurrency)
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
        self.check_subs.toggled.connect(self._set_check_subs)
        self.sub_interval.valueChanged.connect(self._set_sub_interval)
        self.update_btn.clicked.connect(self.run_update_check)
        self.restore_btn.clicked.connect(self._restore)

    # ------------------------------------------------------------------ slots
    def _set_concurrency(self, value: int) -> None:
        self._settings.app.concurrent_downloads = value
        self.concurrency_changed.emit(value)

    def _set_check_subs(self, on: bool) -> None:
        self._settings.app.check_subscriptions = on
        self.subscriptions_changed.emit()

    def _set_sub_interval(self, value: int) -> None:
        self._settings.app.subscription_interval_minutes = value
        self.subscriptions_changed.emit()

    def _pick_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, tr("SaveDirectory"), self._settings.app.save_directory
        )
        if chosen:
            self._settings.app.save_directory = chosen
            self._settings.download.save_path = chosen
            self.save_dir.setText(chosen)
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
    box = QFrame()
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
