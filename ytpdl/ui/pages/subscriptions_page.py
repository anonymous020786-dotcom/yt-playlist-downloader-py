"""Subscriptions: track channels / playlists and pull new uploads on demand."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.subscriptions import Subscription, SubscriptionStore
from ...i18n import tr
from ..widgets.common import heading, pill


class _CheckSignals(QObject):
    done = Signal(str, int, str)  # url, new_count, error


class _CheckTask(QRunnable):
    def __init__(self, store: SubscriptionStore, sub: Subscription) -> None:
        super().__init__()
        self._store = store
        self._sub = sub
        self.signals = _CheckSignals()

    def run(self) -> None:
        _src, err = self._store.check(self._sub)
        self.signals.done.emit(self._sub.url, self._sub.new_count, err)


class SubscriptionsPage(QWidget):
    download_requested = Signal(str)  # url
    toast = Signal(str)

    def __init__(self, store: SubscriptionStore) -> None:
        super().__init__()
        self._store = store
        self._pool = QThreadPool.globalInstance()
        self._rows: dict[str, QFrame] = {}
        self._build()
        self._reload()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.addWidget(heading(tr("Subscriptions")))
        header.addStretch(1)
        self._check_all = QPushButton(tr("CheckNow"))
        self._check_all.setObjectName("Primary")
        self._check_all.clicked.connect(self._check_all_now)
        header.addWidget(self._check_all)
        root.addLayout(header)

        add_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("https://www.youtube.com/@channel")
        self._input.returnPressed.connect(self._add)
        add_btn = QPushButton(tr("AddSubscription"))
        add_btn.clicked.connect(self._add)
        add_row.addWidget(self._input, 1)
        add_row.addWidget(add_btn)
        root.addLayout(add_row)

        self._empty = QLabel(tr("NoSubscriptions"))
        self._empty.setObjectName("Dim")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setWordWrap(True)
        root.addWidget(self._empty)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        holder = QWidget()
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(0, 0, 6, 0)
        self._list.setSpacing(10)
        self._list.addStretch(1)
        self._scroll.setWidget(holder)
        root.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ data
    def _reload(self) -> None:
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        for sub in self._store.items:
            self._add_row(sub)
        self._sync_empty()

    def _add(self) -> None:
        url = self._input.text().strip()
        if not url:
            return
        sub = self._store.add(url)
        self._input.clear()
        if sub.url not in self._rows:
            self._add_row(sub)
        self._sync_empty()
        self._check(sub)

    def _add_row(self, sub: Subscription) -> None:
        frame = QFrame()
        frame.setObjectName("QueueRow")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(sub.title or sub.url)
        title.setObjectName("H2")
        title.setWordWrap(True)
        meta = QLabel(self._meta_text(sub))
        meta.setObjectName("Dim")
        text.addWidget(title)
        text.addWidget(meta)
        lay.addLayout(text, 1)

        badge = pill(tr("NewVideos", count=sub.new_count))
        badge.setVisible(sub.new_count > 0)
        lay.addWidget(badge)

        check_btn = QPushButton(tr("CheckNow"))
        check_btn.setObjectName("Ghost")
        check_btn.clicked.connect(lambda: self._check(sub))
        dl_btn = QPushButton(tr("Download"))
        dl_btn.setObjectName("Primary")
        dl_btn.clicked.connect(lambda: self._download(sub))
        rm_btn = QPushButton(tr("Remove"))
        rm_btn.setObjectName("Ghost")
        rm_btn.clicked.connect(lambda: self._remove(sub))
        lay.addWidget(check_btn)
        lay.addWidget(dl_btn)
        lay.addWidget(rm_btn)

        frame._title = title  # type: ignore[attr-defined]
        frame._meta = meta  # type: ignore[attr-defined]
        frame._badge = badge  # type: ignore[attr-defined]
        self._rows[sub.url] = frame
        self._list.insertWidget(self._list.count() - 1, frame)

    def _meta_text(self, sub: Subscription) -> str:
        if not sub.last_checked:
            return tr("LastChecked") + ": —"
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(sub.last_checked))
        return f"{tr('LastChecked')}: {when}"

    def _check(self, sub: Subscription) -> None:
        task = _CheckTask(self._store, sub)
        task.signals.done.connect(self._on_checked)
        self._pool.start(task)

    def _check_all_now(self) -> None:
        for sub in self._store.items:
            self._check(sub)

    def _on_checked(self, url: str, new_count: int, error: str) -> None:
        sub = next((s for s in self._store.items if s.url == url), None)
        frame = self._rows.get(url)
        if sub is None or frame is None:
            return
        frame._title.setText(sub.title or sub.url)  # type: ignore[attr-defined]
        frame._meta.setText(self._meta_text(sub))  # type: ignore[attr-defined]
        badge = frame._badge  # type: ignore[attr-defined]
        badge.setText(tr("NewVideos", count=new_count))
        badge.setVisible(new_count > 0)
        if error:
            self.toast.emit(f"{tr('Error')}: {error}")
        elif new_count:
            self.toast.emit(tr("NewVideos", count=new_count))

    def _download(self, sub: Subscription) -> None:
        self.download_requested.emit(sub.url)
        self._store.mark_downloaded(sub)
        frame = self._rows.get(sub.url)
        if frame is not None:
            frame._badge.setVisible(False)  # type: ignore[attr-defined]

    def _remove(self, sub: Subscription) -> None:
        self._store.remove(sub.url)
        frame = self._rows.pop(sub.url, None)
        if frame is not None:
            frame.setParent(None)
            frame.deleteLater()
        self._sync_empty()

    def _sync_empty(self) -> None:
        has = bool(self._rows)
        self._empty.setVisible(not has)
        self._scroll.setVisible(has)
