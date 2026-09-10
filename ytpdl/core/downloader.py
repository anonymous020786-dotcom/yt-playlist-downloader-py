"""The download engine.

A :class:`DownloadJob` wraps a single yt-dlp run (one video / playlist / channel)
and reports progress through Qt signals. Files are downloaded into a private temp
folder, then renamed with the user's filename template, tagged, and moved to the
destination — mirroring the original app's temp-then-copy design, which keeps a
half-finished batch from littering the output folder and gives us full control
over naming and tagging.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, DownloadError

from .. import config
from .filenames import render_template
from .models import ResolvedSource, SourceKind
from .settings import DownloadSettings
from .tagging import tag_audio_file

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"([A-Za-z0-9_-]{11})(?=\.[^.]+$|$)")
_AUDIO_CONTAINERS = {"mp3", "m4a", "aac", "opus", "flac", "wav", "ogg", "vorbis", "alac"}


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSignals(QObject):
    # job_id, percent 0-100, human status line, speed text, eta text
    progress = Signal(str, float, str, str, str)
    # job_id, done_count, total_count
    item_progress = Signal(str, int, int)
    # job_id, new JobState
    state_changed = Signal(str, object)
    # job_id, error message (may be empty)
    finished = Signal(str, str)


class DownloadJob(QRunnable):
    def __init__(self, job_id: str, source: ResolvedSource, settings: DownloadSettings,
                 rate_limit_kib: int = 0, cookies_from_browser: str = "") -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.job_id = job_id
        self.source = source
        self.settings = settings
        self.rate_limit_kib = rate_limit_kib
        self.cookies_from_browser = cookies_from_browser
        self.signals = JobSignals()

        self.state = JobState.QUEUED
        self.error = ""
        self.done_count = 0
        self.not_downloaded: list[tuple[str, str]] = []

        self._cancelled = False
        self._paused = False
        self._work_dir = config.TEMP_DIR / job_id
        self._index_by_id = self._build_index_map()
        self.total = len(self._index_by_id) or self.source.count

    # -- public controls -------------------------------------------------------
    def cancel(self) -> None:
        self._cancelled = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # -- helpers -------------------------------------------------------------
    def _build_index_map(self) -> dict[str, int]:
        s = self.settings
        videos = self.source.videos
        start = max(1, s.subset_start) if s.use_subset else 1
        end = s.subset_end if (s.use_subset and s.subset_end) else len(videos)
        chosen = videos[start - 1 : end]
        return {v.id: (start + i) for i, v in enumerate(chosen) if v.id}

    def _set_state(self, state: JobState) -> None:
        self.state = state
        self.signals.state_changed.emit(self.job_id, state)

    @property
    def destination(self) -> Path:
        base = Path(self.settings.save_path)
        if self.settings.separate_playlist_folders and self.source.is_collection:
            base = base / _sanitize_dir(self.source.title)
        return base

    # -- yt-dlp option assembly --------------------------------------------
    def _build_opts(self) -> dict:
        s = self.settings
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "ignoreerrors": True,
            "outtmpl": {"default": str(self._work_dir / "%(playlist_index|1)s__%(id)s.%(ext)s")},
            "paths": {"home": str(self._work_dir)},
            "windowsfilenames": True,
            "retries": 5,
            "fragment_retries": 5,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._pp_hook],
            "post_hooks": [self._post_hook],
        }

        if self.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self.cookies_from_browser,)
        if self.rate_limit_kib > 0:
            opts["ratelimit"] = self.rate_limit_kib * 1024

        # -- item selection ---------------------------------------------------
        if s.use_subset:
            end = str(s.subset_end) if s.subset_end else ""
            opts["playlist_items"] = f"{max(1, s.subset_start)}:{end}"

        if s.filter_by_length:
            minutes = s.filter_minutes
            cmp = ">" if s.filter_longer_than else "<"
            opts["match_filter"] = _duration_filter(minutes * 60, cmp)

        if s.skip_existing:
            opts["download_archive"] = str(config.DOWNLOAD_ARCHIVE_FILE)
            opts["overwrites"] = False

        # -- format + postprocessors ---------------------------------------
        pps: list[dict] = []
        target_is_audio = s.audio_only or (s.convert and s.audio_format in _AUDIO_CONTAINERS
                                           and not s.video_format)

        if s.audio_only:
            opts["format"] = _audio_format_string(s)
            pp = {"key": "FFmpegExtractAudio", "preferredcodec": _codec(s.audio_format)}
            if s.set_bitrate and s.bitrate.isdigit():
                pp["preferredquality"] = s.bitrate
            pps.append(pp)
        else:
            opts["format"] = _video_format_string(s)
            opts["merge_output_format"] = s.video_format
            if s.prefer_highest_fps:
                opts["format_sort"] = [f"res:{s.quality}", "fps", "vcodec:av01"]
            else:
                opts["format_sort"] = [f"res:{s.quality}"]
            if s.convert:
                pps.append({"key": "FFmpegVideoConvertor", "preferedformat": s.video_format})

        if s.audio_language and s.audio_language != "default":
            # Prefer a matching audio track when the video ships multiple languages.
            opts["format_sort"] = [f"lang:{s.audio_language}", *opts.get("format_sort", [])]

        if s.download_subtitles:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = s.auto_subtitles
            opts["subtitleslangs"] = [x.strip() for x in s.subtitle_languages.split(",") if x.strip()] or ["en"]
            if s.embed_subtitles and not s.audio_only:
                pps.append({"key": "FFmpegEmbedSubtitle"})

        if s.embed_thumbnail:
            opts["writethumbnail"] = True
            pps.append({"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
            pps.append({"key": "EmbedThumbnail"})

        pps.append({"key": "FFmpegMetadata", "add_metadata": True})
        opts["postprocessors"] = pps
        self._target_is_audio = target_is_audio or s.audio_only
        return opts

    # -- hooks -------------------------------------------------------------
    def _guard(self) -> None:
        if self._cancelled:
            raise DownloadCancelled()
        while self._paused and not self._cancelled:
            time.sleep(0.2)
        if self._cancelled:
            raise DownloadCancelled()

    def _progress_hook(self, d: dict) -> None:
        self._guard()
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes") or 0
            pct = (got / total * 100) if total else 0.0
            title = (d.get("info_dict") or {}).get("title") or ""
            self.signals.progress.emit(
                self.job_id, pct,
                _("Downloading") + (f" — {title}" if title else ""),
                _fmt_speed(d.get("speed")),
                _fmt_eta(d.get("eta")),
            )
        elif status == "finished":
            self.signals.progress.emit(self.job_id, 100.0, _("Merging"), "", "")

    def _pp_hook(self, d: dict) -> None:
        self._guard()
        if d.get("status") == "started":
            name = (d.get("postprocessor") or "").replace("FFmpeg", "")
            self.signals.progress.emit(self.job_id, 100.0, f"{_('Merging')} ({name})", "", "")

    def _post_hook(self, filepath: str) -> None:
        """Called once per finished file with its final path in the temp dir."""
        try:
            self._finalize_file(Path(filepath))
        except Exception as exc:  # noqa: BLE001
            log.exception("finalize failed for %s", filepath)
            self.not_downloaded.append((Path(filepath).name, str(exc)))

    def _finalize_file(self, src: Path) -> None:
        if not src.exists() or src.suffix.lower() in (".part", ".ytdl", ".webp", ".jpg", ".png"):
            return
        m = _ID_RE.search(src.name)
        vid_id = m.group(1) if m else ""
        index = self._index_by_id.get(vid_id, self.done_count + 1)
        video = next((v for v in self.source.videos if v.id == vid_id), None)

        dest_dir = self.destination
        dest_dir.mkdir(parents=True, exist_ok=True)

        if video is not None:
            stem = render_template(self.settings.filename_template, video, index, self.source.title)
        else:
            stem = src.stem.split("__", 1)[-1]

        target = _unique_path(dest_dir / f"{stem}{src.suffix}")
        shutil.move(str(src), str(target))

        if self.settings.tag_audio and self._target_is_audio and video is not None:
            tag_audio_file(target, video, index, self.source.title, self.source.author)

        self.done_count += 1
        self.signals.item_progress.emit(self.job_id, self.done_count, self.total)

    # -- QRunnable entry point --------------------------------------------
    def run(self) -> None:
        self._set_state(JobState.RUNNING)
        self._work_dir.mkdir(parents=True, exist_ok=True)
        try:
            opts = self._build_opts()
            self.signals.item_progress.emit(self.job_id, 0, self.total)
            with YoutubeDL(opts) as ydl:
                ydl.download([self.source.url])
        except DownloadCancelled:
            self._set_state(JobState.CANCELLED)
            self.signals.finished.emit(self.job_id, "")
            self._cleanup()
            return
        except (DownloadError, OSError) as exc:
            self.error = str(exc)
            self._set_state(JobState.FAILED)
            self.signals.finished.emit(self.job_id, self.error)
            self._cleanup()
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("unexpected error in job %s", self.job_id)
            self.error = str(exc)
            self._set_state(JobState.FAILED)
            self.signals.finished.emit(self.job_id, self.error)
            self._cleanup()
            return

        self._cleanup()
        if self._cancelled:
            self._set_state(JobState.CANCELLED)
        elif self.not_downloaded and self.done_count == 0:
            self.error = "; ".join(f"{n}: {r}" for n, r in self.not_downloaded[:5])
            self._set_state(JobState.FAILED)
        else:
            self._set_state(JobState.COMPLETED)
        self.signals.finished.emit(self.job_id, self.error)

    def _cleanup(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)


# -- module helpers -------------------------------------------------------------
def _(key: str) -> str:  # local import guard to avoid a cycle at import time
    from ..i18n import tr

    return tr(key)


def _sanitize_dir(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().strip(".")[:120] or "playlist"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    i = 1
    while True:
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _codec(fmt: str) -> str:
    return {"ogg": "vorbis"}.get(fmt, fmt)


def _audio_format_string(s: DownloadSettings) -> str:
    if s.audio_language and s.audio_language != "default":
        return f"bestaudio[language^={s.audio_language}]/bestaudio/best"
    return "bestaudio/best"


def _video_format_string(s: DownloadSettings) -> str:
    q = s.quality
    return (
        f"bestvideo[height<=?{q}]+bestaudio/best[height<=?{q}]/best"
    )


def _duration_filter(seconds: float, cmp: str):
    def _filter(info, *, incomplete=False):
        dur = info.get("duration")
        if dur is None:
            return None
        if cmp == ">" and dur > seconds:
            return None
        if cmp == "<" and dur < seconds:
            return None
        return f"video is {'shorter' if cmp == '>' else 'longer'} than the configured limit"

    return _filter


def _fmt_speed(speed: float | None) -> str:
    if not speed:
        return ""
    mib = speed / (1 << 20)
    if mib >= 1:
        return f"{mib:.2f} MiB/s"
    return f"{speed / 1024:.0f} KiB/s"


def _fmt_eta(eta: float | None) -> str:
    if not eta:
        return ""
    eta = int(eta)
    m, s = divmod(eta, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
