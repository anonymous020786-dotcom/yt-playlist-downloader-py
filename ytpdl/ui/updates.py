"""Update flow for the desktop app: check, ask, download, install.

The update mode setting picks the behaviour:

* ``off``  — never checks on its own; the Settings button still works.
* ``ask``  — checks at startup (and every few hours); a new release opens a
  dialog offering Update now / Update when I exit / Skip this version / Later.
* ``auto`` — checks the same way, downloads silently in the background and
  installs when the app exits. Where the platform can't self-install (macOS,
  source installs) it falls back to asking.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from ..core import updater
from ..core.settings import SettingsStore
from ..core.updater import ReleaseAsset, UpdateInfo
from ..i18n import tr
from .workers import UpdateWorker

log = logging.getLogger(__name__)

_RECHECK_MS = 6 * 60 * 60 * 1000  # re-check every 6 h for long-running sessions


class _DownloadSignals(QObject):
    progress = Signal(int, int)
    ok = Signal(object)
    err = Signal(str)
    cancelled = Signal()


class _DownloadWorker(QRunnable):
    def __init__(self, asset: ReleaseAsset) -> None:
        super().__init__()
        self.asset = asset
        self.cancel = threading.Event()
        self.signals = _DownloadSignals()

    def run(self) -> None:
        try:
            path = updater.download_asset(
                self.asset, progress=lambda d, t: self.signals.progress.emit(d, t),
                cancel=self.cancel,
            )
            self.signals.ok.emit(path)
        except updater.UpdateCancelled:
            self.signals.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            log.warning("update download failed: %s", exc)
            self.signals.err.emit(str(exc))


class UpdateController(QObject):
    """Owns every update decision so the window and settings page stay thin."""

    status_changed = Signal(str)

    def __init__(self, settings: SettingsStore, window: QWidget,
                 toast: Callable[[str], None], request_quit: Callable[[], None]) -> None:
        super().__init__(window)
        self._settings = settings
        self._window = window
        self._toast = toast
        self._request_quit = request_quit
        self._pool = QThreadPool.globalInstance()
        self._kind = updater.install_kind()
        self._checking = False
        self._check_worker: UpdateWorker | None = None
        self._downloading: _DownloadWorker | None = None
        self._pending: tuple[Path, UpdateInfo] | None = None  # installed on exit
        self._prompted: str = ""  # version already asked about this session

        self._timer = QTimer(self)
        self._timer.setInterval(_RECHECK_MS)
        self._timer.timeout.connect(lambda: self.check(manual=False))

    # ------------------------------------------------------------ public
    @property
    def mode(self) -> str:
        return self._settings.app.update_mode

    def start(self) -> None:
        """Call once the window is up: startup check plus the periodic timer."""
        updater.clear_downloads()
        self.sync_mode()
        if self.mode != "off":
            QTimer.singleShot(1500, lambda: self.check(manual=False))

    def sync_mode(self) -> None:
        if self.mode == "off":
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start()

    def check(self, *, manual: bool) -> None:
        if self._checking:
            return
        if self._pending and manual:
            self._offer_restart(self._pending[1])
            return
        self._checking = True
        if manual:
            self.status_changed.emit(tr("Analyzing"))
        worker = UpdateWorker()
        worker.setAutoDelete(False)
        # Hold the worker until its result arrives: otherwise Python can collect
        # it (and its signals object) before the queued signal is delivered.
        self._check_worker = worker
        worker.signals.ok.connect(lambda info: self._on_info(info, manual))
        self._pool.start(worker)

    def install_pending_on_exit(self) -> None:
        """Called from the window's close handler after state is saved."""
        if not self._pending:
            return
        path, info = self._pending
        self._pending = None
        try:
            updater.apply_update(path, self._kind, relaunch=False)
            log.info("installing update %s on exit", info.latest)
        except Exception as exc:  # noqa: BLE001
            log.warning("install on exit failed: %s", exc)

    # ----------------------------------------------------------- results
    def _on_info(self, info: UpdateInfo | None, manual: bool) -> None:
        self._checking = False
        self._check_worker = None
        if info is None:
            if manual:
                self.status_changed.emit(tr("UpdateFailed"))
                self._toast(tr("UpdateFailed"))
            return
        if not info.update_available:
            if manual:
                self.status_changed.emit(tr("UpToDate"))
                self._toast(tr("UpToDate"))
            return

        self.status_changed.emit(f"{tr('NewVersionAvailable')}: {info.latest}")
        if not manual:
            if info.latest == self._settings.app.skipped_version:
                return
            if info.latest == self._prompted or self._downloading or self._pending:
                return

        asset = updater.pick_asset(info.assets, self._kind)
        if not manual and self.mode == "auto" and asset and updater.can_self_install(self._kind):
            self._download(info, asset, then="exit", interactive=False)
            return
        self._prompted = info.latest
        self._prompt(info, asset)

    def _prompt(self, info: UpdateInfo, asset: ReleaseAsset | None) -> None:
        box = QMessageBox(self._window)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr("NewVersionAvailable"))
        box.setText(tr("UpdateAvailableVersion", latest=info.latest, current=info.current))
        box.setInformativeText(tr("DoYouWantToUpdate"))
        if info.notes:
            box.setDetailedText(info.notes)

        self_install = asset is not None and updater.can_self_install(self._kind)
        now = later_exit = None
        if self_install:
            now = box.addButton(tr("UpdateNow"), QMessageBox.AcceptRole)
            later_exit = box.addButton(tr("UpdateWhenIExit"), QMessageBox.AcceptRole)
        elif asset is not None:  # macOS: fetch the .dmg and open it
            now = box.addButton(tr("UpdateNow"), QMessageBox.AcceptRole)
        page = box.addButton(tr("OpenDownloadPage"), QMessageBox.ActionRole)
        skip = box.addButton(tr("SkipThisVersion"), QMessageBox.DestructiveRole)
        box.addButton(tr("RemindMeLater"), QMessageBox.RejectRole)
        box.setDefaultButton(now or page)
        box.exec()

        clicked = box.clickedButton()
        if clicked is None:
            return
        if clicked is now:
            self._download(info, asset, then="now", interactive=True)
        elif clicked is later_exit:
            self._download(info, asset, then="exit", interactive=False)
        elif clicked is page:
            QDesktopServices.openUrl(QUrl(info.url))
        elif clicked is skip:
            self._settings.app.skipped_version = info.latest
            self._settings.save()

    # ---------------------------------------------------------- download
    def _download(self, info: UpdateInfo, asset: ReleaseAsset, *, then: str,
                  interactive: bool) -> None:
        if self._downloading:
            return
        worker = _DownloadWorker(asset)
        worker.setAutoDelete(False)
        self._downloading = worker
        self.status_changed.emit(tr("UpdateDownloading", version=info.latest))

        dialog: QProgressDialog | None = None
        if interactive:
            dialog = QProgressDialog(tr("UpdateDownloading", version=info.latest),
                                     tr("Cancel"), 0, 100, self._window)
            dialog.setWindowTitle(tr("UpdateNow"))
            dialog.setWindowModality(Qt.WindowModal)
            dialog.setMinimumDuration(0)
            dialog.setAutoClose(False)
            dialog.setAutoReset(False)
            dialog.canceled.connect(worker.cancel.set)
            dialog.show()

            def _progress(done: int, total: int) -> None:
                if total:
                    dialog.setValue(int(done * 100 / total))
                    dialog.setLabelText(
                        f"{tr('UpdateDownloading', version=info.latest)}\n"
                        f"{done / 1_048_576:.1f} / {total / 1_048_576:.1f} MB")

            worker.signals.progress.connect(_progress)

        def _finish() -> None:
            self._downloading = None
            if dialog is not None:
                dialog.close()

        def _ok(path: Path) -> None:
            _finish()
            self._downloaded(path, info, then)

        def _err(message: str) -> None:
            _finish()
            self.status_changed.emit(tr("UpdateFailed"))
            if interactive:
                QMessageBox.warning(self._window, tr("UpdateFailed"),
                                    f"{tr('UpdateFailed')}\n\n{message}")

        def _cancelled() -> None:
            _finish()
            self.status_changed.emit(tr("UpdateCancelled"))

        worker.signals.ok.connect(_ok)
        worker.signals.err.connect(_err)
        worker.signals.cancelled.connect(_cancelled)
        self._pool.start(worker)

    def _downloaded(self, path: Path, info: UpdateInfo, then: str) -> None:
        if not updater.can_self_install(self._kind):
            # macOS: hand the .dmg to Finder and let the user drag the app over.
            try:
                updater.apply_update(path, self._kind, relaunch=False)
                self.status_changed.emit(tr("UpdateOpenedDmg"))
                self._toast(tr("UpdateOpenedDmg"))
            except Exception as exc:  # noqa: BLE001
                self.status_changed.emit(f"{tr('UpdateFailed')}: {exc}")
            return

        if then == "now":
            try:
                if updater.apply_update(path, self._kind, relaunch=True):
                    self._request_quit()
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self._window, tr("UpdateFailed"), str(exc))
            return

        self._pending = (path, info)
        msg = tr("UpdateReadyOnExit", version=info.latest)
        self.status_changed.emit(msg)
        self._toast(msg)

    def _offer_restart(self, info: UpdateInfo) -> None:
        reply = QMessageBox.question(
            self._window, tr("NewVersionAvailable"),
            tr("UpdateReadyOnExit", version=info.latest) + "\n\n" + tr("RestartToUpdateNow"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes or not self._pending:
            return
        path, _info = self._pending
        self._pending = None
        try:
            if updater.apply_update(path, self._kind, relaunch=True):
                self._request_quit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self._window, tr("UpdateFailed"), str(exc))
