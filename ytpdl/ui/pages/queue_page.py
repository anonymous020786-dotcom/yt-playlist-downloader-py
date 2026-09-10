"""Queue: live list of every download with per-job controls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.downloader import JobState
from ...core.queue import DownloadQueue
from ...i18n import tr
from ..widgets.common import heading
from ..widgets.queue_item import QueueItem


class QueuePage(QWidget):
    def __init__(self, queue: DownloadQueue) -> None:
        super().__init__()
        self._queue = queue
        self._rows: dict[str, QueueItem] = {}
        self._build()

        queue.job_added.connect(self._add_row)
        queue.job_removed.connect(self._remove_row)
        queue.job_progress.connect(self._on_progress)
        queue.job_item_progress.connect(self._on_item_progress)
        queue.job_state_changed.connect(self._on_state)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.addWidget(heading(tr("Queue")))
        header.addStretch(1)
        self._clear_btn = QPushButton(tr("Clear") + " ✓")
        self._clear_btn.setObjectName("Ghost")
        self._clear_btn.clicked.connect(self._queue.clear_finished)
        self._cancel_all = QPushButton(tr("Canceling").split(",")[0] if False else tr("Cancel"))
        self._cancel_all.setObjectName("Danger")
        self._cancel_all.clicked.connect(self._queue.cancel_all)
        header.addWidget(self._clear_btn)
        header.addWidget(self._cancel_all)
        root.addLayout(header)

        self._empty = QLabel(tr("NothingInQueue"))
        self._empty.setObjectName("Dim")
        self._empty.setAlignment(Qt.AlignCenter)
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
        self._sync_empty()

    # ------------------------------------------------------------------ slots
    def _add_row(self, job_id: str) -> None:
        job = self._queue.job(job_id)
        if job is None or job_id in self._rows:
            return
        row = QueueItem(job)
        row.cancel_requested.connect(self._queue.cancel)
        row.retry_requested.connect(self._retry)
        row.remove_requested.connect(self._queue.remove)
        row.pause_requested.connect(self._queue.pause)
        row.resume_requested.connect(self._queue.resume)
        row.open_requested.connect(self._open_folder)
        self._rows[job_id] = row
        self._list.insertWidget(self._list.count() - 1, row)
        self._sync_empty()

    def _remove_row(self, job_id: str) -> None:
        row = self._rows.pop(job_id, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        self._sync_empty()

    def _retry(self, job_id: str) -> None:
        self._queue.retry(job_id)

    def _on_progress(self, job_id: str, pct: float, status: str, speed: str, eta: str) -> None:
        if row := self._rows.get(job_id):
            row.set_progress(pct, status, speed, eta)

    def _on_item_progress(self, job_id: str, done: int, total: int) -> None:
        if row := self._rows.get(job_id):
            row.set_items(done, total)

    def _on_state(self, job_id: str, state: JobState) -> None:
        if row := self._rows.get(job_id):
            row.set_state(state)

    def _open_folder(self, job_id: str) -> None:
        job = self._queue.job(job_id)
        if job is None:
            return
        path = job.destination
        if not path.exists():
            path = Path(job.settings.save_path)
        _reveal(path)

    def _sync_empty(self) -> None:
        has_rows = bool(self._rows)
        self._empty.setVisible(not has_rows)
        self._scroll.setVisible(has_rows)


def _reveal(path: Path) -> None:
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass
