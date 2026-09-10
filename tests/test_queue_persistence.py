from __future__ import annotations

from ytpdl.core.models import ResolvedSource, SourceKind, VideoInfo
from ytpdl.core.settings import DownloadSettings


def _sample_source() -> ResolvedSource:
    return ResolvedSource(
        kind=SourceKind.PLAYLIST,
        title="My Mix",
        url="https://youtube.com/playlist?list=abc",
        author="Someone",
        thumbnail="https://img/x.jpg",
        videos=[
            VideoInfo(id="abcdefghij0", title="One", url="u1", author="A", duration=61.0),
            VideoInfo(id="abcdefghij1", title="Two", url="u2", author="B", duration=None),
        ],
    )


def test_resolved_source_roundtrips_through_dict():
    src = _sample_source()
    restored = ResolvedSource.from_dict(src.to_dict())
    assert restored.kind is SourceKind.PLAYLIST
    assert restored.title == src.title
    assert restored.count == 2
    assert restored.videos[0].id == "abcdefghij0"
    assert restored.videos[1].duration is None


def test_queue_state_file_roundtrip(tmp_path, monkeypatch):
    from ytpdl import config
    from ytpdl.core.queue import DownloadQueue

    monkeypatch.setattr(config, "QUEUE_STATE_FILE", tmp_path / "queue.json")

    payload = [{"source": _sample_source().to_dict(), "settings": DownloadSettings().to_dict()}]
    (tmp_path / "queue.json").write_text(__import__("json").dumps(payload), encoding="utf-8")

    pending = DownloadQueue.load_pending()
    assert len(pending) == 1
    source, settings = pending[0]
    assert source.title == "My Mix"
    assert isinstance(settings, DownloadSettings)
    assert not (tmp_path / "queue.json").exists()  # consumed on load
