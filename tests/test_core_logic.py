"""Unit tests for the provider-agnostic core logic (no network, no Qt)."""

from __future__ import annotations

import json

import pytest

from ytpdl.core.filenames import clean_filename, render_template
from ytpdl.core.models import VideoInfo
from ytpdl.core.resolver import _strip_playlist_context
from ytpdl.core.settings import AppSettings, DownloadSettings
from ytpdl.core.titleparse import extract_genre, split_artist_title


@pytest.mark.parametrize(
    "title, genre, cleaned",
    [
        ("[Melodic Dubstep] Artist - Song Name", "Melodic Dubstep", "Artist - Song Name"),
        ("[NCS Release] Foo - Bar", "", "Foo - Bar"),  # promo word -> dropped
        ("Just A Plain Title", "", "Just A Plain Title"),
    ],
)
def test_extract_genre(title, genre, cleaned):
    g, c = extract_genre(title)
    assert g == genre
    assert c == cleaned


def test_split_artist_title():
    assert split_artist_title("A & B - Great Song") == ("Great Song", ["A", "B"])
    assert split_artist_title("Solo Artist - Track feat. Guest") == (
        "Track feat. Guest",
        ["Solo Artist"],
    )
    assert split_artist_title("No Dash Here") is None


def test_render_template_tokens():
    v = VideoInfo(id="abcdefghijk", title="[House] DJ X - Night Drive", url="u", author="DJ X")
    name = render_template("$index. $artist - $songtitle [$genre]", v, 3, "Summer Mix")
    assert name == "3. DJ X - Night Drive [House]"


def test_render_template_fallback_when_empty():
    v = VideoInfo(id="abcdefghijk", title="Plain", url="u")
    assert render_template("$artist", v, 1) == "Plain"


def test_clean_filename_strips_invalid():
    assert clean_filename('a/b:c*d?"e') == "a_b_c_d__e"
    assert clean_filename("") == "video"
    assert clean_filename("CON.txt").startswith("_")


def test_settings_roundtrip():
    d = DownloadSettings(audio_only=True, quality="720", filename_template="$index-$title")
    restored = DownloadSettings.from_dict(json.loads(json.dumps(d.to_dict())))
    assert restored == d


def test_settings_ignores_unknown_keys_and_coerces_types():
    a = AppSettings.from_dict({"concurrent_downloads": "4", "bogus": 1, "theme": "light"})
    assert a.concurrent_downloads == 4
    assert a.theme == "light"


def test_download_settings_clone_is_independent():
    a = DownloadSettings()
    b = a.clone()
    b.audio_only = True
    assert a.audio_only is False


@pytest.mark.parametrize(
    "url, expected",
    [
        # v= + list= from watching a video inside a playlist/queue: v= wins,
        # not "download the whole playlist" (the bug this guards against).
        (
            "https://www.youtube.com/watch?v=abc12345678&list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "https://www.youtube.com/watch?v=abc12345678",
        ),
        # index= from queue position should go too.
        (
            "https://www.youtube.com/watch?v=abc12345678&list=PLxxx&index=5",
            "https://www.youtube.com/watch?v=abc12345678",
        ),
        # youtu.be short link with a stray list= behaves the same way.
        (
            "https://youtu.be/abc12345678?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "https://youtu.be/abc12345678",
        ),
        # a bare playlist link (no v=) is genuine playlist intent — untouched.
        (
            "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        ),
        # a plain video link with no list= is untouched.
        (
            "https://www.youtube.com/watch?v=abc12345678",
            "https://www.youtube.com/watch?v=abc12345678",
        ),
    ],
)
def test_strip_playlist_context(url, expected):
    assert _strip_playlist_context(url) == expected
