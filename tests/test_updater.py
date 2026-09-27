from __future__ import annotations

import hashlib
import threading

import pytest

from ytpdl.core import updater
from ytpdl.core.settings import AppSettings
from ytpdl.core.updater import ReleaseAsset

ASSETS = [
    ReleaseAsset("YouTube-Playlist-Downloader-Setup-2.1.0.exe", "u/exe", 10),
    ReleaseAsset("YTPDL-linux.AppImage", "u/appimage", 10),
    ReleaseAsset("YTPDL-macos.dmg", "u/dmg", 10),
]


@pytest.mark.parametrize("candidate,current,newer", [
    ("v2.0.5", "2.0.4", True),
    ("2.1", "2.0.9", True),
    ("v2.0.4", "2.0.4", False),
    ("v2.0.3", "2.0.4", False),
    ("v10.0.0", "9.9.9", True),
])
def test_is_newer(candidate, current, newer):
    assert updater.is_newer(candidate, current) is newer


def test_parse_asset_reads_sha256_digest():
    a = updater._parse_asset({"name": "x.exe", "browser_download_url": "u", "size": 3,
                              "digest": "sha256:ABCD"})
    assert a == ReleaseAsset("x.exe", "u", 3, "abcd")
    assert updater._parse_asset({"name": "x"}) is None


def test_install_kind(tmp_path):
    exe = tmp_path / "app.exe"
    exe.touch()
    kw = {"environ": {}, "executable": str(exe)}
    assert updater.install_kind("win32", frozen=True, **kw) == updater.INSTALL_MANUAL
    (tmp_path / "unins000.exe").touch()
    assert updater.install_kind("win32", frozen=True, **kw) == updater.INSTALL_WINDOWS_SETUP
    assert updater.install_kind("win32", frozen=False, **kw) == updater.INSTALL_MANUAL
    assert updater.install_kind("darwin", frozen=True, **kw) == updater.INSTALL_MACOS_DMG
    assert updater.install_kind("linux", environ={"APPIMAGE": "/a"}, executable="x",
                                frozen=True) == updater.INSTALL_APPIMAGE


@pytest.mark.parametrize("kind,name", [
    (updater.INSTALL_WINDOWS_SETUP, "YouTube-Playlist-Downloader-Setup-2.1.0.exe"),
    (updater.INSTALL_APPIMAGE, "YTPDL-linux.AppImage"),
    (updater.INSTALL_MACOS_DMG, "YTPDL-macos.dmg"),
])
def test_pick_asset(kind, name):
    assert updater.pick_asset(ASSETS, kind).name == name


def test_pick_asset_manual_has_none():
    assert updater.pick_asset(ASSETS, updater.INSTALL_MANUAL) is None


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers = {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, size):
        for i in range(0, len(self.body), 4):
            yield self.body[i:i + 4]


def _patch_get(monkeypatch, body: bytes) -> list:
    calls = []

    def fake_get(url, **_kw):
        calls.append(url)
        return _FakeResponse(body)

    monkeypatch.setattr(updater.requests, "get", fake_get)
    return calls


def test_download_verifies_and_reuses(monkeypatch, tmp_path):
    body = b"new installer bytes"
    calls = _patch_get(monkeypatch, body)
    asset = ReleaseAsset("Setup.exe", "u", len(body), hashlib.sha256(body).hexdigest())
    seen = []
    path = updater.download_asset(asset, tmp_path, progress=lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == body
    assert seen[-1] == (len(body), len(body))
    # second call finds the verified file on disk and doesn't re-download
    assert updater.download_asset(asset, tmp_path) == path
    assert len(calls) == 1


def test_download_rejects_bad_checksum(monkeypatch, tmp_path):
    body = b"tampered"
    _patch_get(monkeypatch, body)
    asset = ReleaseAsset("Setup.exe", "u", len(body), "0" * 64)
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.download_asset(asset, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_cancel_cleans_up(monkeypatch, tmp_path):
    _patch_get(monkeypatch, b"x" * 64)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(updater.UpdateCancelled):
        updater.download_asset(ReleaseAsset("S.exe", "u", 64), tmp_path, cancel=cancel)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("data,mode", [
    ({}, "ask"),
    ({"check_for_updates": False}, "off"),
    ({"check_for_updates": True}, "ask"),
    ({"update_mode": "auto", "check_for_updates": False}, "auto"),
    ({"update_mode": "bogus"}, "ask"),
])
def test_update_mode_migration(data, mode):
    assert AppSettings.from_dict(data).update_mode == mode
