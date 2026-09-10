"""Home: paste a link, review what was found, pick items, tweak options, queue.

A secondary tab accepts a newline-separated list of links for bulk queuing.
"""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.ffmpeg import has_ffmpeg
from ...core.models import ResolvedSource, SourceKind
from ...core.settings import SettingsStore
from ...i18n import tr
from ..widgets.common import Thumbnail, dim, heading
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
        self.setAcceptDrops(True)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self._start_resolve)

        self._build()
        self._options.load(settings.download)
        self._options.changed.connect(self._on_options_changed)
        self._refresh_ffmpeg_banner()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self._page_title = heading(tr("StartADownload"))
        root.addWidget(self._page_title)
        self._page_hint = dim(tr("PasteLinkHint"))
        root.addWidget(self._page_hint)

        self._banner = self._build_banner()
        root.addWidget(self._banner)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._single_tab(), tr("Home"))
        self._tabs.addTab(self._bulk_tab(), tr("Bulk"))
        root.addWidget(self._tabs, 1)

    def _build_banner(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Banner")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 10)
        self._banner_label = QLabel(tr("FFmpegMissing"))
        self._banner_label.setWordWrap(True)
        lay.addWidget(self._banner_label, 1)
        frame.hide()
        return frame

    def _single_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 12, 0, 0)
        outer.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 8, 0)
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
        card_lay = QVBoxLayout(self._result_card)
        card_lay.setContentsMargins(16, 16, 16, 16)
        card_lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(16)
        self._thumb = Thumbnail(180, 101)
        top.addWidget(self._thumb, 0, Qt.AlignTop)
        info = QVBoxLayout()
        info.setSpacing(6)
        self._res_title = QLabel("")
        self._res_title.setObjectName("H2")
        self._res_title.setWordWrap(True)
        self._res_author = QLabel("")
        self._res_author.setObjectName("Dim")
        self._res_meta_label = QLabel("")
        self._res_meta_label.setObjectName("MetaLine")
        info.addWidget(self._res_title)
        info.addWidget(self._res_author)
        info.addWidget(self._res_meta_label)
        info.addStretch(0)
        top.addLayout(info, 1)
        top.setAlignment(Qt.AlignTop)
        card_lay.addLayout(top)

        # per-item selection list (collections only)
        self._select_bar = QHBoxLayout()
        self._select_bar.setSpacing(8)
        self._select_count = QLabel("")
        self._select_count.setObjectName("Dim")
        self._list_filter = QLineEdit()
        self._list_filter.setPlaceholderText(tr("Search"))
        self._list_filter.setClearButtonEnabled(True)
        self._list_filter.setMaximumWidth(220)
        self._list_filter.textChanged.connect(self._apply_list_filter)
        btn_all = QPushButton(tr("SelectAll"))
        btn_all.setObjectName("Ghost")
        btn_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_none = QPushButton(tr("SelectNone"))
        btn_none.setObjectName("Ghost")
        btn_none.clicked.connect(lambda: self._set_all_checked(False))
        self._select_bar.addWidget(self._select_count, 1)
        self._select_bar.addWidget(self._list_filter)
        self._select_bar.addWidget(btn_all)
        self._select_bar.addWidget(btn_none)
        self._select_bar_holder = QWidget()
        self._select_bar_holder.setLayout(self._select_bar)
        card_lay.addWidget(self._select_bar_holder)

        self._video_list = QListWidget()
        self._video_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._video_list.setUniformItemSizes(True)
        self._video_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._video_list.itemChanged.connect(self._on_item_checked)
        card_lay.addWidget(self._video_list)

        self._result_card.hide()
        lay.addWidget(self._result_card)

        self._status = dim("")
        self._status.setVisible(False)
        lay.addWidget(self._status)

        # --- options drawer ------------------------------------------
        self._options = DownloadOptions()
        self._opt_toggle = QPushButton("⚙  " + tr("Options"))
        self._opt_toggle.setObjectName("Ghost")
        self._opt_toggle.setCheckable(True)
        self._opt_toggle.setChecked(self._settings.app.options_expanded)
        self._options.setVisible(self._settings.app.options_expanded)
        self._opt_toggle.toggled.connect(self._toggle_options)
        lay.addWidget(self._opt_toggle)
        lay.addWidget(self._options)
        lay.addStretch(1)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # --- action bar (fixed at bottom) --------------------------------
        actions = QHBoxLayout()
        actions.addWidget(QLabel(tr("SaveDirectory")))
        self._path_label = QLabel(self._settings.download.save_path)
        self._path_label.setObjectName("Dim")
        browse = QPushButton(tr("Browse"))
        browse.clicked.connect(self._browse)
        actions.addWidget(self._path_label, 1)
        actions.addWidget(browse)
        outer.addLayout(actions)

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
        outer.addLayout(btn_row)
        return page

    def _bulk_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(dim(tr("BulkHint")))
        self._bulk_text = QPlainTextEdit()
        self._bulk_text.setPlaceholderText(
            "https://www.youtube.com/watch?v=…\nhttps://www.youtube.com/playlist?list=…"
        )
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

    # ------------------------------------------------------------- drag & drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        text = md.text().strip()
        if md.hasUrls() and md.urls():
            text = md.urls()[0].toString()
        if text:
            self._tabs.setCurrentIndex(0)
            self._search.setText(text)
            event.acceptProposedAction()

    # ------------------------------------------------------------- behaviour
    def _toggle_options(self, checked: bool) -> None:
        self._options.setVisible(checked)
        self._settings.app.options_expanded = checked

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

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def _on_options_changed(self) -> None:
        self._options.apply(self._settings.download)
        self._refresh_ffmpeg_banner()

    def _refresh_ffmpeg_banner(self) -> None:
        needs = not self._options.audio_only or self._settings.download.convert
        self._banner.setVisible(needs and not has_ffmpeg())

    # ------------------------------------------------------------- resolving
    def _start_resolve(self) -> None:
        text = self._search.text().strip()
        self._debounce.stop()
        self._source = None
        self._btn_queue.setEnabled(False)
        self._btn_download.setEnabled(False)
        if not text:
            self._result_card.hide()
            self._set_status("")
            return

        self._resolve_token += 1
        token = self._resolve_token
        self._set_status(tr("Analyzing"))
        worker = ResolveWorker(text, self._settings.app.cookies_from_browser)
        worker.signals.ok.connect(lambda src, t=token: self._on_resolved(src, t))
        worker.signals.err.connect(lambda msg, t=token: self._on_resolve_error(msg, t))
        self._pool.start(worker)

    def _on_resolved(self, source: ResolvedSource, token: int) -> None:
        if token != self._resolve_token:
            return
        self._source = source
        self._set_status("")
        self._result_card.show()
        self._thumb.load(source.thumbnail)
        self._res_title.setText(source.title)
        self._res_author.setText(tr("PlaylistBy", author=source.author) if source.author else "")

        kind_label = {
            SourceKind.VIDEO: tr("Video"),
            SourceKind.PLAYLIST: tr("Playlist"),
            SourceKind.CHANNEL: tr("Channel"),
        }[source.kind]
        parts = [kind_label]
        if source.is_collection:
            parts.append(tr("ItemsSelected", count=source.count))
        self._res_meta_label.setText("   ·   ".join(parts))

        self._populate_video_list(source)
        self._btn_queue.setEnabled(True)
        self._btn_download.setEnabled(True)

    def _on_resolve_error(self, message: str, token: int) -> None:
        if token != self._resolve_token:
            return
        self._result_card.hide()
        self._set_status(f"{tr('Error')}: {message or tr('InvalidLink')}")

    # ------------------------------------------------------------- selection
    def _populate_video_list(self, source: ResolvedSource) -> None:
        collection = source.is_collection and source.count > 1
        self._select_bar_holder.setVisible(collection)
        self._video_list.setVisible(collection)
        self._list_filter.blockSignals(True)
        self._list_filter.clear()
        self._list_filter.blockSignals(False)
        self._list_filter.setVisible(collection and source.count > 12)
        self._video_list.blockSignals(True)
        self._video_list.clear()
        if collection:
            for i, video in enumerate(source.videos, start=1):
                dur = f"  ·  {video.duration_text}" if video.duration else ""
                item = QListWidgetItem(f"{i}.  {video.title}{dur}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setData(Qt.UserRole, video.id)
                self._video_list.addItem(item)
        self._video_list.blockSignals(False)
        if collection and self._video_list.count():
            row_h = self._video_list.sizeHintForRow(0) or 22
            self._video_list.setFixedHeight(min(self._video_list.count(), 7) * row_h + 8)
        self._update_select_count()

    def _apply_list_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._video_list.count()):
            item = self._video_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _set_all_checked(self, checked: bool) -> None:
        """Toggle the rows currently visible (respects the filter box)."""
        state = Qt.Checked if checked else Qt.Unchecked
        self._video_list.blockSignals(True)
        for i in range(self._video_list.count()):
            item = self._video_list.item(i)
            if not item.isHidden():
                item.setCheckState(state)
        self._video_list.blockSignals(False)
        self._update_select_count()

    def _on_item_checked(self, _item: QListWidgetItem) -> None:
        self._update_select_count()

    def _update_select_count(self) -> None:
        total = self._video_list.count()
        chosen = sum(
            1 for i in range(total)
            if self._video_list.item(i).checkState() == Qt.Checked
        )
        self._select_count.setText(tr("SelectedOfTotal", count=chosen, total=total))
        if total:
            self._btn_queue.setEnabled(chosen > 0)
            self._btn_download.setEnabled(chosen > 0)

    def _selected_source(self) -> ResolvedSource | None:
        if self._source is None:
            return None
        if not self._video_list.isVisible() or self._video_list.count() == 0:
            return self._source
        keep = {
            self._video_list.item(i).data(Qt.UserRole)
            for i in range(self._video_list.count())
            if self._video_list.item(i).checkState() == Qt.Checked
        }
        videos = [v for v in self._source.videos if v.id in keep]
        if len(videos) == len(self._source.videos):
            return self._source
        return dataclasses.replace(self._source, videos=videos)

    # ------------------------------------------------------------- enqueue
    def _enqueue_single(self) -> None:
        source = self._selected_source()
        if source is None:
            return
        self._options.apply(self._settings.download)
        if not self._settings.download.save_path:
            self.toast.emit(tr("DownloadPathMissing"))
            return
        self.queue_requested.emit([source])
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
        self._banner_label.setText(tr("FFmpegMissing"))
        self._search.setPlaceholderText(tr("InsertYoutubePlaylistLinkHere"))
        self._tabs.setTabText(0, tr("Home"))
        self._tabs.setTabText(1, tr("Bulk"))
        self._opt_toggle.setText("⚙  " + tr("Options"))
        self._btn_queue.setText(tr("AddToQueue"))
        self._btn_download.setText(tr("DownloadNow"))
