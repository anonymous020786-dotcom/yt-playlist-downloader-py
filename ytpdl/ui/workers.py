"""Tiny QRunnable wrappers for blocking core calls (link resolution, update
checks) so the UI thread never stalls.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..core.models import ResolvedSource
from ..core.resolver import ResolveError, resolve
from ..core.updater import UpdateInfo, check_for_update


class _Sig(QObject):
    ok = Signal(object)
    err = Signal(str)


class ResolveWorker(QRunnable):
    def __init__(self, text: str, cookies_from_browser: str = "") -> None:
        super().__init__()
        self.text = text
        self.cookies = cookies_from_browser
        self.signals = _Sig()

    def run(self) -> None:
        try:
            source: ResolvedSource = resolve(self.text, cookies_from_browser=self.cookies)
            self.signals.ok.emit(source)
        except ResolveError as exc:
            self.signals.err.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.signals.err.emit(str(exc))


class BulkResolveWorker(QRunnable):
    def __init__(self, lines: list[str], cookies_from_browser: str = "") -> None:
        super().__init__()
        self.lines = lines
        self.cookies = cookies_from_browser
        self.signals = _Sig()

    def run(self) -> None:
        resolved: list[ResolvedSource] = []
        errors: list[str] = []
        for line in self.lines:
            line = line.strip()
            if not line:
                continue
            try:
                resolved.append(resolve(line, cookies_from_browser=self.cookies))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{line} — {exc}")
        self.signals.ok.emit((resolved, errors))


class UpdateWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = _Sig()

    def run(self) -> None:
        info: UpdateInfo | None = check_for_update()
        self.signals.ok.emit(info)
