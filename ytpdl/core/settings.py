"""Typed, JSON-backed settings.

Two records, matching the split in the original app:

* :class:`DownloadSettings` — everything that controls *how* a download runs
  (format, quality, filters, tagging). Cloned per job so mid-flight settings
  changes don't affect running downloads.
* :class:`AppSettings` — everything else (theme, language, folders, update and
  concurrency preferences).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from .. import config

log = logging.getLogger(__name__)


def _default_video_dir() -> str:
    for name in ("Videos", "Movies"):
        candidate = Path.home() / name
        if candidate.exists():
            return str(candidate)
    return str(Path.home() / "Downloads")


@dataclass
class DownloadSettings:
    save_path: str = field(default_factory=_default_video_dir)
    audio_only: bool = False
    audio_format: str = "mp3"
    video_format: str = "mkv"
    quality: str = "1080"  # target height in pixels, as a string
    prefer_highest_fps: bool = False
    convert: bool = False
    set_bitrate: bool = False
    bitrate: str = "192"  # kbit/s for audio re-encode

    download_subtitles: bool = False
    auto_subtitles: bool = False
    subtitle_languages: str = "en"
    embed_subtitles: bool = True

    separate_playlist_folders: bool = True
    open_folder_when_done: bool = False
    skip_existing: bool = False
    tag_audio: bool = True
    embed_thumbnail: bool = True

    use_subset: bool = False
    subset_start: int = 1
    subset_end: int = 0  # 0 == until the end

    filter_by_length: bool = False
    filter_longer_than: bool = False  # False => "shorter than"
    filter_minutes: float = 4.0

    filename_template: str = "$title"
    audio_language: str = "default"

    def clone(self) -> DownloadSettings:
        return dataclasses.replace(self)

    # -- (de)serialization -------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadSettings:
        return _coerce(cls, data)


@dataclass
class AppSettings:
    theme: str = "dark"  # "light" | "dark" | "system"
    accent: str = "Red"
    language: str = "en"
    save_directory: str = field(default_factory=_default_video_dir)

    check_for_updates: bool = True
    confirm_on_exit: bool = True
    save_download_options: bool = True

    concurrent_downloads: int = 2
    rate_limit_kib: int = 0  # 0 == unlimited

    cookies_from_browser: str = ""  # "", "chrome", "firefox", "edge", ...

    check_subscriptions: bool = False
    subscription_interval_minutes: int = 60

    options_expanded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppSettings:
        return _coerce(cls, data)


def _coerce(cls, data: dict[str, Any]):
    """Build a dataclass from a dict, ignoring unknown keys and fixing types."""
    kwargs: dict[str, Any] = {}
    valid = {f.name: f for f in fields(cls)}
    for name, f in valid.items():
        if name not in data:
            continue
        value = data[name]
        try:
            if f.type in ("bool", bool):
                value = bool(value)
            elif f.type in ("int", int):
                value = int(value)
            elif f.type in ("float", float):
                value = float(value)
            elif f.type in ("str", str):
                value = str(value)
        except (TypeError, ValueError):
            continue
        kwargs[name] = value
    return cls(**kwargs)


class SettingsStore:
    """Loads/saves both records and hands out clones for the UI to edit."""

    def __init__(self) -> None:
        config.ensure_dirs()
        self.app = self._load(config.SETTINGS_FILE, AppSettings)
        self.download = self._load(config.DOWNLOAD_SETTINGS_FILE, DownloadSettings)
        # Keep the two save-directory fields in agreement.
        if self.download.save_path != self.app.save_directory:
            self.download.save_path = self.app.save_directory

    @staticmethod
    def _load(path: Path, cls):
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as exc:
                log.warning("Could not read %s: %s — using defaults", path.name, exc)
        return cls()

    def save(self) -> None:
        self.app.save_directory = self.download.save_path
        _atomic_write(config.SETTINGS_FILE, self.app.to_dict())
        if self.app.save_download_options:
            _atomic_write(config.DOWNLOAD_SETTINGS_FILE, self.download.to_dict())

    def restore_defaults(self) -> None:
        self.app = AppSettings()
        self.download = DownloadSettings()
        self.save()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
