"""Home: paste a link, review what was found, tweak options, send to the queue.

A secondary tab accepts a newline-separated list of links for bulk queuing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.models import ResolvedSource, SourceKind
from ...core.settings import SettingsStore
from ...i18n import tr
from ..widgets.common import Thumbnail, card, dim, heading, pill
from ..widgets.download_options import DownloadOptions
from ..workers import BulkResolveWorker, ResolveWorker


class HomePage(QWidget):
    queue_requested = Signal(list)      # list[ResolvedSource]
    toast = Signal(str)

    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self._settings = settings
        self._pool = QThreadPool.globalInstance()
        self._source: ResolvedSource | None = None
        self._resolve_token = 0

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self._start_resolve)

        self._build()
        self._options.load(settings.download)
        self._options.changed.connect(self._persist_options)

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        self._page_title = heading(tr("StartADownload"))
        root.addWidget(self._page_title)
        self._page_hint = dim(tr("PasteLinkHint"))
        root.addWidget(self._page_hint)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._single_tab(), tr("Home"))
        self._tabs.addTab(self._bulk_tab(), tr("Bulk"))
        root.addWidget(self._tabs, 1)

    def _single_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(16)

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setObjectName("Search")
        self._search.setPlaceholderText(tr("InsertYoutubePlaylistLinkHere"))
        self._search.textChanged.connect(lambda _t: self._debounce.start())
        self._search.returnPressed.connect(self._start_resolve)
        paste_btn = QPushButton(tr("Paste"))
        paste_btn.clicked.connect(self._paste)
        search_row.addWidget(self._search, 1)
        search_row.addWidget(paste_btn)
        lay.addLayout(search_row)

        # --- result card ------------------------------------------------
        self._result_card = QFrame()
        self._result_card.setObjectName("Card")
        rc = QHBoxLayout(self._result_card)
        rc.setContentsMargins(16, 16, 16, 16)
        rc.setSpacing(16)
        self._thumb = Thumbnail(200, 112)
        rc.addWidget(self._thumb, 0, Qt.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(6)
        self._res_title = QLabel("")
        self._res_title.setObjectName("H2")
        self._res_title.setWordWrap(True)
        self._res_author = QLabel("")
        self._res_author.setObjectName("Dim")
        self._res_meta = QHBoxLayout()
        self._res_meta.setSpacing(6)
        self._res_meta.addStretch(1)
        info.addWidget(self._res_title)
        info.addWidget(self._res_author)
        meta_holder = QWidget()
        meta_holder.setLayout(self._res_meta)
        info.addWidget(meta_holder, 0, Qt.AlignLeft)
        info.addStretch(1)
        rc.addLayout(info, 1)
        self._result_card.hide()
        lay.addWidget(self._result_card)

        self._status = dim("")
        lay.addWidget(self._status)

        # --- options drawer ------------------------------------------
        self._options = DownloadOptions()
        opt_toggle = QPushButton("⚙  " + tr("Options"))
        opt_toggle.setObjectName("Ghost")
        opt_toggle.setCheckable(True)
        opt_toggle.setChecked(self._settings.app.options_expanded)
        opt_scroll = QScrollArea()
        opt_scroll.setWidgetResizable(True)
        opt_scroll.setWidget(self._options)
        opt_scroll.setVisible(self._settings.app.options_expanded)
        opt_scroll.setMaximumHeight(340)

        def _toggle(checked: bool) -> None:
            opt_scroll.setVisible(checked)
            self._settings.app.options_expanded = checked

        opt_toggle.toggled.connect(_toggle)
        lay.addWidget(opt_toggle)
        lay.addWidget(opt_scroll)
        lay.addStretch(1)

        # --- action bar ------------------------------------------------
        actions = QHBoxLayout()
        self._path_label = QLabel(self._settings.download.save_path)
        self._path_label.setObjectName("Dim")
        browse = QPushButton(tr("Browse"))
        browse.clicked.connect(self._browse)
        actions.addWidget(QLabel(tr("SaveDirectory")))
        actions.addWidget(self._path_label, 1)
        actions.addWidget(browse)
        lay.addLayout(actions)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_queue = QPushButton(tr("AddToQueue"))
        self._btn_queue.clicked.connect(self._enqueue_single)
        self._btn_download = QPushButton(tr("DownloadNow"))
        self._btn_download.setObjectName("Primary")
        self._btn_download.clicked.connect(self._enqueue_single)
        self._btn_queue.setEnabled(False)
        self._btn_download.setEnabled(False)
        btn_row.addWidget(self._btn_queue)
        btn_row.addWidget(self._btn_download)
        lay.addLayout(btn_row)
        return page

    def _bulk_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(dim("One link per line — videos, playlists or channels."))
        self._bulk_text = QPlainTextEdit()
        self._bulk_text.setPlaceholderText("https://www.youtube.com/watch?v=…\nhttps://www.youtube.com/playlist?list=…")
        lay.addWidget(self._bulk_text, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        clear = QPushButton(tr("Clear"))
        clear.clicked.connect(self._bulk_text.clear)
        self._bulk_btn = QPushButton(tr("AddToQueue"))
        self._bulk_btn.setObjectName("Primary")
        self._bulk_btn.clicked.connect(self._enqueue_bulk)
        row.addWidget(clear)
        row.addWidget(self._bulk_btn)
        lay.addLayout(row)
        return page

    # ------------------------------------------------------------- behaviour
    def _paste(self) -> None:
        from PySide6.QtWidgets import QApplication

        self._search.setText(QApplication.clipboard().text().strip())

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, tr("SaveDirectory"), self._settings.download.save_path
        )
        if chosen:
            self._settings.download.save_path = chosen
            self._settings.app.save_directory = chosen
            self._path_label.setText(chosen)

    def _persist_options(self) -> None:
        self._options.apply(self._settings.download)

    def _start_resolve(self) -> None:
        text = self._search.text().strip()
        self._debounce.stop()
        self._source = None
        self._btn_queue.setEnabled(False)
        self._btn_download.setEnabled(False)
        if not text:
            self._result_card.hide()
            self._status.setText("")
            return

        self._resolve_token += 1
        token = self._resolve_token
        self._status.setText(tr("Analyzing"))
        worker = ResolveWorker(text, self._settings.app.cookies_from_browser)
        worker.signals.ok.connect(lambda src, t=token: self._on_resolved(src, t))
        worker.signals.err.connect(lambda msg, t=token: self._on_resolve_error(msg, t))
        self._pool.start(worker)

    def _on_resolved(self, source: ResolvedSource, token: int) -> None:
        if token != self._resolve_token:
            return
        self._source = source
        self._status.setText("")
        self._result_card.show()
        self._thumb.load(source.thumbnail)
        self._res_title.setText(source.title)
        self._res_author.setText(tr("PlaylistBy", author=source.author) if source.author else "")

        while self._res_meta.count() > 1:
            item = self._res_meta.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        kind_label = {
            SourceKind.VIDEO: tr("Video"),
            SourceKind.PLAYLIST: tr("Playlist"),
            SourceKind.CHANNEL: tr("Channel"),
        }[source.kind]
        self._res_meta.insertWidget(0, pill(kind_label))
        if source.is_collection:
            self._res_meta.insertWidget(1, pill(tr("ItemsSelected", count=source.count)))

        self._btn_queue.setEnabled(True)
        self._btn_download.setEnabled(True)

    def _on_resolve_error(self, message: str, token: int) -> None:
        if token != self._resolve_token:
            return
        self._result_card.hide()
        self._status.setText(f"{tr('Error')}: {message or tr('InvalidLink')}")

    def _enqueue_single(self) -> None:
        if not self._source:
            return
        self._options.apply(self._settings.download)
        if not self._settings.download.save_path:
            self.toast.emit(tr("DownloadPathMissing"))
            return
        self.queue_requested.emit([self._source])
        self.toast.emit(tr("Queued"))
        self._search.clear()
        self._result_card.hide()
        self._source = None

    def _enqueue_bulk(self) -> None:
        lines = [ln for ln in self._bulk_text.toPlainText().splitlines() if ln.strip()]
        if not lines:
            return
        self._options.apply(self._settings.download)
        self._bulk_btn.setEnabled(False)
        self._bulk_btn.setText(tr("Analyzing"))
        worker = BulkResolveWorker(lines, self._settings.app.cookies_from_browser)
        worker.signals.ok.connect(self._on_bulk_resolved)
        self._pool.start(worker)

    def _on_bulk_resolved(self, payload: tuple) -> None:
        resolved, errors = payload
        self._bulk_btn.setEnabled(True)
        self._bulk_btn.setText(tr("AddToQueue"))
        if resolved:
            self.queue_requested.emit(resolved)
            self._bulk_text.clear()
        msg = tr("ItemsSelected", count=len(resolved))
        if errors:
            msg += f"  ·  {len(errors)} {tr('Failed').lower()}"
        self.toast.emit(msg)

    # ------------------------------------------------------------- retitling
    def retranslate(self) -> None:
        self._page_title.setText(tr("StartADownload"))
        self._page_hint.setText(tr("PasteLinkHint"))
        self._search.setPlaceholderText(tr("InsertYoutubePlaylistLinkHere"))
        self._tabs.setTabText(0, tr("Home"))
        self._tabs.setTabText(1, tr("Bulk"))
        self._btn_queue.setText(tr("AddToQueue"))
        self._btn_download.setText(tr("DownloadNow"))
