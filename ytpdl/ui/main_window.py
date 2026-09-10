"""Main window: navigation rail + stacked pages, wiring the pages to the queue."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..core.queue import DownloadQueue
from ..core.settings import SettingsStore
from ..core.subscriptions import SubscriptionStore
from ..i18n import tr, translator
from .pages.about_page import AboutPage
from .pages.help_page import HelpPage
from .pages.home_page import HomePage
from .pages.queue_page import QueuePage
from .pages.settings_page import SettingsPage
from .pages.subscriptions_page import SubscriptionsPage
from .theme import apply_theme
from .widgets.common import Toast
from .workers import ResolveWorker, UpdateWorker

_NAV = [
    ("Home", "🏠"),
    ("Queue", "⬇"),
    ("Subscriptions", "🔔"),
    ("Settings", "⚙"),
    ("Help", "❔"),
    ("About", "ℹ"),
]


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self._settings = settings
        self._pool = QThreadPool.globalInstance()
        self._queue = DownloadQueue(settings)
        self._subs = SubscriptionStore()
        self._quitting = False

        self.setWindowTitle(config.APP_NAME)
        self._restore_geometry()

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._nav_buttons: list[QPushButton] = []
        layout.addWidget(self._build_nav())

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        self._home = HomePage(settings)
        self._queue_page = QueuePage(self._queue)
        self._subs_page = SubscriptionsPage(self._subs)
        self._settings_page = SettingsPage(settings)
        self._help_page = HelpPage()
        self._about_page = AboutPage()
        for page in (self._home, self._queue_page, self._subs_page,
                     self._settings_page, self._help_page, self._about_page):
            self._stack.addWidget(page)

        self._toast = Toast(self)
        self._sub_timer = QTimer(self)
        self._sub_timer.timeout.connect(self._subs_page.check_all)
        self._tray = self._build_tray()
        self._wire()
        self._install_shortcuts()
        self._select(0)
        self._sync_subscription_timer()

        QTimer.singleShot(200, self._offer_restore)
        if settings.app.check_for_updates:
            self._check_updates(silent=True)

    # ------------------------------------------------------------------ build
    def _build_nav(self) -> QWidget:
        rail = QFrame()
        rail.setObjectName("NavRail")
        rail.setFixedWidth(210)
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(14, 20, 14, 20)
        lay.setSpacing(6)

        wordmark = QLabel("YT  Downloader")
        wordmark.setObjectName("AppWordmark")
        lay.addWidget(wordmark)
        lay.addSpacing(16)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for idx, (key, icon) in enumerate(_NAV):
            btn = QPushButton(f"  {icon}   {tr(key)}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, i=idx: self._select(i))
            self._nav_group.addButton(btn, idx)
            self._nav_buttons.append(btn)
            lay.addWidget(btn)

        lay.addStretch(1)
        self._queue_badge = QLabel("")
        self._queue_badge.setObjectName("Dim")
        lay.addWidget(self._queue_badge)
        return rail

    def _build_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icon = QIcon(str(config.ICON_FILE)) if config.ICON_FILE.exists() else self.windowIcon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(config.APP_NAME)
        menu = QMenu()
        show_action = QAction(tr("Home"), self)
        show_action.triggered.connect(self._show_from_tray)
        quit_action = QAction(tr("Exit"), self)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    # ------------------------------------------------------------------- wire
    def _wire(self) -> None:
        self._home.queue_requested.connect(self._on_queue_requested)
        self._home.toast.connect(self._toast.show_message)
        self._subs_page.download_requested.connect(self._on_subscription_download)
        self._subs_page.toast.connect(self._toast.show_message)
        self._settings_page.theme_changed.connect(self._apply_theme)
        self._settings_page.language_changed.connect(self._on_language_changed)
        self._settings_page.concurrency_changed.connect(self._queue.set_concurrency)
        self._settings_page.subscriptions_changed.connect(self._sync_subscription_timer)

        self._queue.job_added.connect(lambda _j: self._refresh_badge())
        self._queue.job_removed.connect(lambda _j: self._refresh_badge())
        self._queue.job_state_changed.connect(lambda *_a: self._refresh_badge())
        self._queue.job_finished.connect(self._on_job_finished)
        self._queue.queue_idle.connect(self._on_queue_idle)

        translator.locale_changed.connect(self._retranslate)

    def _install_shortcuts(self) -> None:
        for i in range(len(_NAV)):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            sc.activated.connect(lambda idx=i: self._select(idx))
        focus = QShortcut(QKeySequence("Ctrl+L"), self)
        focus.activated.connect(self._focus_search)

    def _focus_search(self) -> None:
        self._select(0)
        self._home._search.setFocus()
        self._home._search.selectAll()

    # ------------------------------------------------------------------ slots
    def _select(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._nav_buttons[index].setChecked(True)

    def _on_queue_requested(self, sources: list) -> None:
        self._queue.enqueue_many(sources)
        self._select(1)
        self._refresh_badge()

    def _on_subscription_download(self, url: str) -> None:
        worker = ResolveWorker(url, self._settings.app.cookies_from_browser)
        worker.signals.ok.connect(lambda src: self._on_queue_requested([src]))
        worker.signals.err.connect(lambda msg: self._toast.show_message(f"{tr('Error')}: {msg}"))
        self._pool.start(worker)

    def _on_job_finished(self, job_id: str, error: str) -> None:
        job = self._queue.job(job_id)
        if job is None:
            return
        if error:
            self._toast.show_message(f"{tr('CouldntDownload')}: {job.source.title}")
        else:
            self._toast.show_message(f"{tr('AllDone')} — {job.source.title}")
            if job.settings.open_folder_when_done:
                self._queue_page._open_folder(job_id)
        self._refresh_badge()

    def _on_queue_idle(self) -> None:
        """Every download finished — notify if the window isn't focused."""
        if self._tray and not self.isActiveWindow():
            done = sum(1 for j in self._queue.jobs() if j.state.value == "completed")
            self._tray.showMessage(
                config.APP_NAME,
                f"{tr('AllDone')} ({done})",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _sync_subscription_timer(self) -> None:
        app = self._settings.app
        self._subs_page.set_auto_download(app.check_subscriptions)
        if app.check_subscriptions and self._subs.items:
            self._sub_timer.start(max(5, app.subscription_interval_minutes) * 60_000)
        else:
            self._sub_timer.stop()

    def _refresh_badge(self) -> None:
        active = self._queue.active_count()
        self._queue_badge.setText(f"{active} {tr('Downloading').lower()}" if active else "")
        self._nav_buttons[1].setText(
            f"  ⬇   {tr('Queue')}" + (f"  ({active})" if active else "")
        )
        if self._tray:
            self._tray.setToolTip(
                f"{config.APP_NAME} — {active} {tr('Downloading').lower()}"
                if active else config.APP_NAME
            )

    def _apply_theme(self) -> None:
        apply_theme(QApplication.instance(), self._settings.app.theme, self._settings.app.accent)

    def _on_language_changed(self, code: str) -> None:
        translator.set_locale(code)
        QApplication.instance().setLayoutDirection(
            Qt.RightToLeft if translator.is_rtl else Qt.LeftToRight
        )

    def _retranslate(self, _code: str) -> None:
        for idx, (key, icon) in enumerate(_NAV):
            self._nav_buttons[idx].setText(f"  {icon}   {tr(key)}")
        self._home.retranslate()
        self._help_page.retranslate()
        self._refresh_badge()

    def _check_updates(self, *, silent: bool) -> None:
        worker = UpdateWorker()

        def _done(info) -> None:
            if info is None:
                if not silent:
                    self._toast.show_message(tr("ErrorWhileUpdating"))
                return
            if info.update_available:
                QMessageBox.information(
                    self, tr("NewVersionAvailable"),
                    f"{tr('DoYouWantToUpdate')}\n\n{info.latest}\n{info.url}",
                )
            elif not silent:
                self._toast.show_message(tr("UpToDate"))

        worker.signals.ok.connect(_done)
        self._pool.start(worker)

    def _offer_restore(self) -> None:
        pending = self._queue.load_pending()
        if not pending:
            return
        reply = QMessageBox.question(
            self, config.APP_NAME,
            tr("RestoreQueuePrompt", count=len(pending)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._queue.restore(pending)
            self._select(1)
            self._refresh_badge()

    # ------------------------------------------------------------------ tray
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._quitting = True
        self.close()

    # -------------------------------------------------------------- geometry
    def _restore_geometry(self) -> None:
        self.setMinimumSize(900, 600)
        self.resize(1120, 780)
        geo = self._settings.app.window_geometry
        if geo:
            try:
                from PySide6.QtCore import QByteArray

                self.restoreGeometry(QByteArray.fromBase64(geo.encode("ascii")))
            except (ValueError, TypeError):
                pass

    def _save_geometry(self) -> None:
        self._settings.app.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")

    # ------------------------------------------------------------------ close
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._toast.isVisible():
            self._toast.hide()

    def closeEvent(self, event: QCloseEvent) -> None:
        # Minimise to tray instead of quitting while downloads run.
        if (not self._quitting and self._tray and self._tray.isVisible()
                and self._queue.active_count() > 0):
            event.ignore()
            self.hide()
            self._tray.showMessage(
                config.APP_NAME,
                tr("RunningInBackground", count=self._queue.active_count()),
                QSystemTrayIcon.MessageIcon.Information, 3000,
            )
            return

        if not self._quitting and self._settings.app.confirm_on_exit:
            key = "StillDownloadingSubscriptionsExit" if self._queue.active_count() else "AreYouSureExit"
            default = QMessageBox.No if self._queue.active_count() else QMessageBox.Yes
            reply = QMessageBox.question(
                self, tr("Exit"), tr(key),
                QMessageBox.Yes | QMessageBox.No, default,
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return

        self._save_geometry()
        self._queue.save_state()
        self._queue.wait_for_done(3000)
        self._settings.save()
        self._subs.save()
        if self._tray:
            self._tray.hide()
        config.clean_temp_dir()
        super().closeEvent(event)
