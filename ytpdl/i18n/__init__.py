"""Runtime translation layer.

Locale data lives in ``locales/<code>.json`` (imported from the original WPF
resource dictionaries by ``scripts/convert_languages.py``). The public surface is
small:

* :func:`available_locales` — list of ``LocaleInfo`` for the settings dropdown.
* :func:`set_locale` — switch the active language.
* :func:`tr` — translate a key, with ``str.format`` style parameters.
* :data:`translator` — a ``QObject`` emitting ``locale_changed`` so widgets can
  re-render live.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"

# Strings the modern UI needs that the original resource files never had.
# English is authoritative; other locales fall back to these until translated.
_EXTRA_EN: dict[str, str] = {
    "Home": "Home",
    "StartADownload": "Start a download",
    "PasteLinkHint": "Paste a video, playlist or channel link — it's analyzed automatically.",
    "Options": "Options",
    "Channel": "Channel",
    "SelectAll": "Select all",
    "SelectNone": "Select none",
    "SelectedOfTotal": "{count} of {total} selected",
    "BulkHint": "One link per line — videos, playlists or channels.",
    "RestoreQueuePrompt": "{count} unfinished download(s) from your last session. Resume them?",
    "RunningInBackground": "Still downloading ({count}) — the app is running in the tray.",
    "Help": "Help",
    "FFmpegMissing": "FFmpeg was not found. Audio-only downloads still work, but "
    "video downloads, format conversion and subtitle embedding need FFmpeg on your PATH.",
    "Queue": "Queue",
    "Subscriptions": "Subscriptions",
    "Bulk": "Bulk",
    "AddToQueue": "Add to queue",
    "DownloadNow": "Download now",
    "Paste": "Paste",
    "Clear": "Clear",
    "Browse": "Browse",
    "Remove": "Remove",
    "Retry": "Retry",
    "Cancel": "Cancel",
    "Pause": "Pause",
    "Resume": "Resume",
    "OpenFolder": "Open folder",
    "Analyzing": "Analyzing link…",
    "Ready": "Ready",
    "Queued": "Queued",
    "Completed": "Completed",
    "Failed": "Failed",
    "Cancelled": "Cancelled",
    "Merging": "Merging",
    "Tagging": "Tagging",
    "NothingInQueue": "Nothing in the queue yet.",
    "NoSubscriptions": "No subscriptions yet. Add a channel to track new uploads.",
    "AddSubscription": "Add channel",
    "CheckNow": "Check now",
    "LastChecked": "Last checked",
    "NewVideos": "{count} new",
    "Format": "Format",
    "Quality": "Quality",
    "AudioOnly": "Audio only",
    "Convert": "Convert / re-encode",
    "Advanced": "Advanced",
    "General": "General",
    "Appearance": "Appearance",
    "Downloads": "Downloads",
    "FilenameTemplate": "Filename template",
    "FilenameTemplateHint": "Tokens: $title $index $artist $songtitle $channel $playlist $genre $videoid",
    "SubsetRange": "Only download items in range",
    "FilterByLength": "Filter by duration (minutes)",
    "Shorter": "shorter than",
    "Longer": "longer than",
    "SkipExisting": "Skip files that already exist",
    "TagAudio": "Auto-tag audio (artist / title / album art)",
    "EmbedThumbnail": "Embed thumbnail",
    "EmbedSubtitles": "Embed subtitles when converting",
    "SeparateFolders": "Save each playlist in its own folder",
    "OpenWhenDone": "Open destination folder when finished",
    "ConcurrentDownloads": "Concurrent downloads",
    "RateLimit": "Speed limit (KiB/s, 0 = unlimited)",
    "SubtitleLanguages": "Subtitle languages (comma separated)",
    "AutoSubtitles": "Include auto-generated subtitles",
    "CookiesFromBrowser": "Load cookies from browser",
    "None": "None",
    "RestoreDefaults": "Restore defaults",
    "Save": "Save",
    "Apply": "Apply",
    "AccentColor": "Accent color",
    "FollowSystem": "Follow system",
    "Light": "Light",
    "Dark": "Dark",
    "ETA": "ETA",
    "Speed": "Speed",
    "Size": "Size",
    "CheckForUpdatesNow": "Check for updates now",
    "UpToDate": "You are running the latest version.",
    "DownloadPathMissing": "Choose a valid download folder first.",
    "InvalidLink": "That doesn't look like a YouTube video, playlist, or channel link.",
    "ItemsSelected": "{count} items",
    "PlaylistBy": "by {author}",
}


@dataclass(frozen=True)
class LocaleInfo:
    code: str
    english_name: str
    native_name: str
    rtl: bool

    @property
    def label(self) -> str:
        if self.native_name and self.native_name != self.english_name:
            return f"{self.native_name} ({self.english_name})"
        return self.english_name


class _Translator(QObject):
    locale_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._code = "en"
        self._strings: dict[str, str] = {}
        self._rtl = False
        self.set_locale("en")

    # -- state -----------------------------------------------------------------
    @property
    def code(self) -> str:
        return self._code

    @property
    def is_rtl(self) -> bool:
        return self._rtl

    def set_locale(self, code: str) -> None:
        data = _load_locale(code)
        if data is None:
            if code != "en":
                self.set_locale("en")
            return
        merged = dict(_EXTRA_EN)
        merged.update(data["strings"])
        self._strings = merged
        self._code = code
        self._rtl = bool(data["@meta"].get("rtl"))
        self.locale_changed.emit(code)

    # -- lookup --------------------------------------------------------------
    def tr(self, key: str, /, **params: object) -> str:
        text = self._strings.get(key) or _EXTRA_EN.get(key) or key
        if params:
            try:
                return text.format(**params)
            except (KeyError, IndexError, ValueError):
                return text
        return text


@cache
def _load_locale(code: str) -> dict | None:
    path = _LOCALES_DIR / f"{code}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def available_locales() -> list[LocaleInfo]:
    index_path = _LOCALES_DIR / "index.json"
    with index_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        LocaleInfo(r["code"], r["english_name"], r["native_name"], bool(r["rtl"]))
        for r in raw
    ]


translator = _Translator()


def tr(key: str, /, **params: object) -> str:
    """Module-level shortcut for ``translator.tr``."""
    return translator.tr(key, **params)


def set_locale(code: str) -> None:
    translator.set_locale(code)
