"""Filesystem locations and process-wide constants.

Mirrors the original ``GlobalConsts`` static class: an app-data folder holds the
JSON settings, the error log, the download archive and the subscription store;
a temp folder is used for in-progress downloads.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_NAME = "YouTube Playlist Downloader"
APP_DIR_NAME = "YoutubePlaylistDownloader"
GITHUB_REPO = "shaked6540/YoutubePlaylistDownloader"


def _appdata_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Path(base) / APP_DIR_NAME


APP_DATA_DIR: Path = _appdata_dir()
SETTINGS_FILE: Path = APP_DATA_DIR / "settings.json"
DOWNLOAD_SETTINGS_FILE: Path = APP_DATA_DIR / "download_settings.json"
ERROR_LOG_FILE: Path = APP_DATA_DIR / "errors.log"
SUBSCRIPTIONS_FILE: Path = APP_DATA_DIR / "subscriptions.json"
DOWNLOAD_ARCHIVE_FILE: Path = APP_DATA_DIR / "download_archive.txt"
QUEUE_STATE_FILE: Path = APP_DATA_DIR / "queue_state.json"

TEMP_DIR: Path = Path(tempfile.gettempdir()) / APP_DIR_NAME

RESOURCES_DIR: Path = Path(__file__).resolve().parent / "resources"
ICON_FILE: Path = RESOURCES_DIR / "app.png"


def ensure_dirs() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def clean_temp_dir() -> None:
    import shutil

    if TEMP_DIR.exists():
        for child in TEMP_DIR.iterdir():
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except OSError:
                pass


# Default media containers offered in the UI.
AUDIO_FORMATS = ["mp3", "m4a", "aac", "opus", "flac", "wav", "ogg", "vorbis", "alac"]
VIDEO_FORMATS = ["mp4", "mkv", "webm", "mov"]
RESOLUTIONS = ["144", "240", "360", "480", "720", "1080", "1440", "2160", "4320"]

# Accent palette (name -> hex). Matches the spirit of the original MahApps accents.
ACCENTS: dict[str, str] = {
    "Red": "#E51C23",
    "Green": "#4CAF50",
    "Blue": "#2196F3",
    "Purple": "#9C27B0",
    "Orange": "#FF9800",
    "Lime": "#CDDC39",
    "Emerald": "#2ECC71",
    "Teal": "#009688",
    "Cyan": "#00BCD4",
    "Cobalt": "#0050EF",
    "Indigo": "#3F51B5",
    "Violet": "#AA00FF",
    "Pink": "#E91E63",
    "Magenta": "#D80073",
    "Crimson": "#A20025",
    "Amber": "#FFC107",
    "Yellow": "#FFEB3B",
    "Brown": "#795548",
    "Olive": "#6D8764",
    "Steel": "#647687",
    "Mauve": "#76608A",
    "Taupe": "#87794E",
    "Sienna": "#A0522D",
}
