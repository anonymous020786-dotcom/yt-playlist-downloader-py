"""Update check.

The original app shipped an Inno Setup installer and self-updated on exit. The
Python build is distributed as a wheel / PyInstaller bundle, so "update" here
means: compare the running version against the latest GitHub release and, if
newer, point the user at the release page. yt-dlp updates itself on its own
cadence and is checked separately.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from .. import __version__, config

log = logging.getLogger(__name__)
_RELEASES_API = f"https://api.github.com/repos/{config.GITHUB_REPO}/releases/latest"
_TIMEOUT = 8


@dataclass
class UpdateInfo:
    current: str
    latest: str
    url: str
    notes: str
    update_available: bool


def _parse_version(text: str) -> tuple[int, ...]:
    cleaned = text.lstrip("vV").split("-")[0]
    parts: list[int] = []
    for chunk in cleaned.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            break
    return tuple(parts) or (0,)


def check_for_update() -> UpdateInfo | None:
    try:
        resp = requests.get(_RELEASES_API, timeout=_TIMEOUT,
                            headers={"Accept": "application/vnd.github+json"})
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.info("update check failed: %s", exc)
        return None

    latest = str(data.get("tag_name") or data.get("name") or "").strip()
    if not latest:
        return None

    available = _parse_version(latest) > _parse_version(__version__)
    return UpdateInfo(
        current=__version__,
        latest=latest,
        url=data.get("html_url") or f"https://github.com/{config.GITHUB_REPO}/releases",
        notes=(data.get("body") or "").strip(),
        update_available=available,
    )
