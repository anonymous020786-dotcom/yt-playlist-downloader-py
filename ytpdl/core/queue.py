"""Download queue: owns the thread pool and the list of jobs.

The UI talks only to this object — it never creates a :class:`DownloadJob`
directly. Concurrency is bounded by ``QThreadPool.maxThreadCount`` which tracks
the user's "concurrent downloads" preference.
"""

from __future__ import annotations

import json
import logging
import uuid

from PySide6.QtCore import QObject, QThreadPool, Signal

from .. import config
from .downloader import DownloadJob, JobState
from .models import ResolvedSource
from .settings import DownloadSettings, SettingsStore

log = logging.getLogger(__name__)

_UNFINISHED = (JobState.QUEUED, JobState.RUNNING, JobState.PAUSED, JobState.FAILED)


class DownloadQueue(QObject):
    job_added = Signal(str)          # job_id
    job_removed = Signal(str)        # job_id
    job_progress = Signal(str, float, str, str, str)
    job_item_progress = Signal(str, int, int)
    job_state_changed = Signal(str, object)
    job_finished = Signal(str, str)
    queue_idle = Signal()

    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self._settings = settings
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(1, settings.app.concurrent_downloads))
        self._jobs: dict[str, DownloadJob] = {}
        self._order: list[str] = []

    # -- config ------------------------------------------------------------
    def set_concurrency(self, count: int) -> None:
        self._pool.setMaxThreadCount(max(1, count))

    # -- introspection ---------------------------------------------------
    def jobs(self) -> list[DownloadJob]:
        return [self._jobs[j] for j in self._order if j in self._jobs]

    def job(self, job_id: str) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def active_count(self) -> int:
        return sum(1 for j in self._jobs.values()
                   if j.state in (JobState.RUNNING, JobState.QUEUED, JobState.PAUSED))

    # -- mutation --------------------------------------------------------
    def enqueue(self, source: ResolvedSource, settings: DownloadSettings | None = None) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = DownloadJob(
            job_id,
            source,
            (settings or self._settings.download).clone(),
            rate_limit_kib=self._settings.app.rate_limit_kib,
            cookies_from_browser=self._settings.app.cookies_from_browser,
        )
        job.signals.progress.connect(self.job_progress)
        job.signals.item_progress.connect(self.job_item_progress)
        job.signals.state_changed.connect(self.job_state_changed)
        job.signals.finished.connect(self._on_job_finished)

        self._jobs[job_id] = job
        self._order.append(job_id)
        self.job_added.emit(job_id)
        self._pool.start(job)
        return job_id

    def enqueue_many(self, sources: list[ResolvedSource]) -> list[str]:
        return [self.enqueue(s) for s in sources]

    def cancel(self, job_id: str) -> None:
        if job := self._jobs.get(job_id):
            job.cancel()

    def pause(self, job_id: str) -> None:
        if job := self._jobs.get(job_id):
            job.pause()
            self.job_state_changed.emit(job_id, JobState.PAUSED)

    def resume(self, job_id: str) -> None:
        if job := self._jobs.get(job_id):
            job.resume()
            self.job_state_changed.emit(job_id, JobState.RUNNING)

    def retry(self, job_id: str) -> str | None:
        job = self._jobs.get(job_id)
        if job is None or job.state not in (JobState.FAILED, JobState.CANCELLED):
            return None
        self.remove(job_id)
        return self.enqueue(job.source)

    def remove(self, job_id: str) -> None:
        job = self._jobs.pop(job_id, None)
        if job is None:
            return
        job.cancel()
        if job_id in self._order:
            self._order.remove(job_id)
        self.job_removed.emit(job_id)

    def clear_finished(self) -> None:
        for job_id in list(self._order):
            job = self._jobs.get(job_id)
            if job and job.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
                self.remove(job_id)

    def cancel_all(self) -> None:
        for job in self._jobs.values():
            job.cancel()

    def _on_job_finished(self, job_id: str, error: str) -> None:
        self.job_finished.emit(job_id, error)
        if self.active_count() == 0:
            self.queue_idle.emit()

    def wait_for_done(self, msec: int = -1) -> bool:
        self.cancel_all()
        return self._pool.waitForDone(msec)

    # -- persistence -----------------------------------------------------
    def save_state(self) -> None:
        """Write unfinished jobs so a crash / quit doesn't lose the queue."""
        pending = [
            {"source": job.source.to_dict(), "settings": job.settings.to_dict()}
            for job in self.jobs()
            if job.state in _UNFINISHED
        ]
        try:
            if pending:
                config.QUEUE_STATE_FILE.write_text(
                    json.dumps(pending, ensure_ascii=False), encoding="utf-8"
                )
            else:
                config.QUEUE_STATE_FILE.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("could not save queue state: %s", exc)

    @staticmethod
    def load_pending() -> list[tuple[ResolvedSource, DownloadSettings]]:
        """Read + delete the saved queue. Returns [(source, settings), ...]."""
        path = config.QUEUE_STATE_FILE
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = []
        path.unlink(missing_ok=True)
        out: list[tuple[ResolvedSource, DownloadSettings]] = []
        for entry in raw:
            try:
                out.append((
                    ResolvedSource.from_dict(entry["source"]),
                    DownloadSettings.from_dict(entry["settings"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def restore(self, pending: list[tuple[ResolvedSource, DownloadSettings]]) -> None:
        for source, settings in pending:
            self.enqueue(source, settings)
