"""Lightweight value objects shared between the resolver, the queue and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceKind(str, Enum):
    VIDEO = "video"
    PLAYLIST = "playlist"
    CHANNEL = "channel"


@dataclass(frozen=True)
class VideoInfo:
    id: str
    title: str
    url: str
    author: str = ""
    duration: float | None = None  # seconds
    thumbnail: str = ""

    @property
    def duration_text(self) -> str:
        if not self.duration:
            return "--:--"
        total = int(self.duration)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@dataclass
class ResolvedSource:
    kind: SourceKind
    title: str
    url: str
    author: str = ""
    thumbnail: str = ""
    videos: list[VideoInfo] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.videos)

    @property
    def is_collection(self) -> bool:
        return self.kind in (SourceKind.PLAYLIST, SourceKind.CHANNEL)
