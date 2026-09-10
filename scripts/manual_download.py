"""End-to-end: resolve a short video and actually download + convert + tag it."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from ytpdl.core.downloader import DownloadJob
from ytpdl.core.resolver import resolve
from ytpdl.core.settings import DownloadSettings

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
out = Path(tempfile.mkdtemp(prefix="ytpdl_dltest_"))
print("output dir:", out)

source = resolve(url)
print(f"resolved {source.kind} '{source.title}' — {source.count} video(s)")

settings = DownloadSettings()
settings.save_path = str(out)
settings.audio_only = True
settings.audio_format = "mp3"
settings.set_bitrate = True
settings.bitrate = "128"
settings.tag_audio = True
settings.embed_thumbnail = True
settings.separate_playlist_folders = False

job = DownloadJob("test0000", source, settings)
job.signals.progress.connect(lambda _j, p, s, sp, e: print(f"  {p:5.1f}%  {s} {sp} {e}", flush=True))
job.signals.item_progress.connect(lambda _j, d, t: print(f"  item {d}/{t}", flush=True))
job.signals.finished.connect(lambda _j, err: print("FINISHED", repr(err), flush=True))

job.run()

print("state:", job.state)
for f in sorted(out.rglob("*")):
    if f.is_file():
        print("  file:", f.relative_to(out), f"{f.stat().st_size / 1024:.0f} KiB")

try:
    from mutagen import File as MF

    files = [f for f in out.rglob("*") if f.suffix == ".mp3"]
    if files:
        print("tags:", dict(MF(str(files[0]), easy=True) or {}))
except Exception as exc:  # noqa: BLE001
    print("tag read failed:", exc)
