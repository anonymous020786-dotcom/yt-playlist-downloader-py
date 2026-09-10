"""Channel / playlist subscriptions.

Each subscription records the newest video id we've seen. "Check now" re-resolves
the source (flat, so it's cheap), diffs against the stored id, and reports how
many new uploads appeared. Downloading them reuses the normal queue with a
``download_archive`` so nothing is fetched twice.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import config
from .models import ResolvedSource
from .resolver import ResolveError, resolve


@dataclass
class Subscription:
    url: str
    title: str = ""
    last_seen_id: str = ""
    last_checked: float = 0.0
    new_count: int = 0
    known_ids: list[str] = field(default_factory=list)


class SubscriptionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or config.SUBSCRIPTIONS_FILE
        self.items: list[Subscription] = []
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self.items = [Subscription(**{"known_ids": [], **d}) for d in raw]
            except (OSError, ValueError, TypeError):
                self.items = []

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(s) for s in self.items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, url: str) -> Subscription:
        for existing in self.items:
            if existing.url == url:
                return existing
        sub = Subscription(url=url)
        self.items.append(sub)
        self.save()
        return sub

    def remove(self, url: str) -> None:
        self.items = [s for s in self.items if s.url != url]
        self.save()

    def check(self, sub: Subscription) -> tuple[ResolvedSource | None, str]:
        """Refresh one subscription. Returns ``(source, error_message)``."""
        try:
            source = resolve(sub.url)
        except ResolveError as exc:
            sub.last_checked = time.time()
            self.save()
            return None, str(exc)

        ids = [v.id for v in source.videos if v.id]
        if not sub.known_ids:
            sub.new_count = 0
        else:
            known = set(sub.known_ids)
            sub.new_count = sum(1 for i in ids if i not in known)

        sub.title = source.title or sub.title
        sub.last_seen_id = ids[0] if ids else sub.last_seen_id
        sub.known_ids = ids[:500]
        sub.last_checked = time.time()
        self.save()
        return source, ""

    def mark_downloaded(self, sub: Subscription) -> None:
        sub.new_count = 0
        self.save()
