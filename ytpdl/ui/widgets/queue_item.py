"""One row in the download queue."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ...core.downloader import DownloadJob, JobState
from ...i18n import tr
from .common import Thumbnail

_STATE_KEY = {
    JobState.QUEUED: "Queued",
    JobState.RUNNING: "Downloading",
    JobState.PAUSED: "Pause",
    JobState.COMPLETED: "Completed",
    JobState.FAILED: "Failed",
    JobState.CANCELLED: "Cancelled",
}


class QueueItem(QFrame):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    remove_requested = Signal(str)
    pause_requested = Signal(str)
    resume_requested = Signal(str)
    open_requested = Signal(str)

    def __init__(self, job: DownloadJob) -> None:
        super().__init__()
        self.job_id = job.job_id
        self.setObjectName("QueueRow")
        self._build(job)
        self.set_state(job.state)
        self.set_items(job.done_count, job.total)

    def _build(self, job: DownloadJob) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(14)

        self.thumb = Thumbnail(120, 68)
        self.thumb.load(job.source.thumbnail)
        outer.addWidget(self.thumb, 0, Qt.AlignTop)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        self.title = QLabel(job.source.title)
        self.title.setObjectName("H2")
        self.title.setWordWrap(True)
        mid.addWidget(self.title)

        self.sub = QLabel("")
        self.sub.setObjectName("Dim")
        mid.addWidget(self.sub)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        mid.addWidget(self.bar)

        self.status = QLabel("")
        self.status.setObjectName("Dim")
        mid.addWidget(self.status)
        outer.addLayout(mid, 1)

        btns = QVBoxLayout()
        btns.setSpacing(6)
        self.btn_primary = QPushButton("")
        self.btn_primary.setObjectName("Ghost")
        self.btn_primary.clicked.connect(self._primary_clicked)
        self.btn_remove = QPushButton(tr("Remove"))
        self.btn_remove.setObjectName("Ghost")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.job_id))
        self.btn_open = QPushButton(tr("OpenFolder"))
        self.btn_open.setObjectName("Ghost")
        self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.job_id))
        btns.addWidget(self.btn_primary)
        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_remove)
        btns.addStretch(1)
        outer.addLayout(btns)

    # ------------------------------------------------------------------ slots
    def _primary_clicked(self) -> None:
        state = self._state
        if state == JobState.RUNNING:
            self.pause_requested.emit(self.job_id)
        elif state == JobState.PAUSED:
            self.resume_requested.emit(self.job_id)
        elif state in (JobState.FAILED, JobState.CANCELLED):
            self.retry_requested.emit(self.job_id)
        else:
            self.cancel_requested.emit(self.job_id)

    def set_progress(self, pct: float, status: str, speed: str, eta: str) -> None:
        self.bar.setValue(int(pct))
        parts = [p for p in (status, speed, (f"{tr('ETA')} {eta}" if eta else "")) if p]
        self.status.setText("   ·   ".join(parts))

    def set_items(self, done: int, total: int) -> None:
        self.sub.setText(f"{done} / {total}" if total else tr("Analyzing"))

    def set_state(self, state: JobState) -> None:
        self._state = state
        self.setProperty("state", state.value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.status.setText(tr(_STATE_KEY.get(state, "Ready")))

        if state == JobState.RUNNING:
            self.btn_primary.setText(tr("Pause"))
        elif state == JobState.PAUSED:
            self.btn_primary.setText(tr("Resume"))
        elif state in (JobState.FAILED, JobState.CANCELLED):
            self.btn_primary.setText(tr("Retry"))
        elif state == JobState.COMPLETED:
            self.btn_primary.setText("")
            self.btn_primary.setVisible(False)
            self.bar.setValue(100)
        else:
            self.btn_primary.setText(tr("Cancel"))

        self.btn_open.setVisible(state == JobState.COMPLETED)
