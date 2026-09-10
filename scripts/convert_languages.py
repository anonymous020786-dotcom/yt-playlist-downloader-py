"""One-shot importer: convert the original WPF `.xaml` language dictionaries
into flat JSON locale files used by :mod:`ytpdl.i18n`.

Run from the repo root with the path to the original project's ``Languages``
folder::

    python scripts/convert_languages.py "C:/path/to/YoutubePlaylistDownloader/Languages"

The output lands in ``ytpdl/i18n/locales/<code>.json``. English is treated as
the reference; every other locale is merged on top of the English defaults so a
missing key still renders readable text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Original display name -> (locale code, English name, native name, rtl)
LANGUAGES = {
    "English": ("en", "English", "English", False),
    "Deutsch": ("de", "German", "Deutsch", False),
    "Dutch (NL)": ("nl", "Dutch", "Nederlands", False),
    "Español": ("es", "Spanish", "Español", False),
    "Français": ("fr", "French", "Français", False),
    "Italiano": ("it", "Italian", "Italiano", False),
    "Polski": ("pl", "Polish", "Polski", False),
    "Português (BR)": ("pt_BR", "Portuguese (Brazil)", "Português (BR)", False),
    "Română": ("ro", "Romanian", "Română", False),
    "Türkçe": ("tr", "Turkish", "Türkçe", False),
    "Русский": ("ru", "Russian", "Русский", False),
    "עברית": ("he", "Hebrew", "עברית", True),
    "العربية": ("ar", "Arabic", "العربية", True),
    "中文": ("zh", "Chinese", "中文", False),
}

KEY_RE = re.compile(r'x:Key="([^"]+)"')
VALUE_RE = re.compile(r'>(.*?)</(?:s:String|FlowDirection|HorizontalAlignment)>', re.DOTALL)


def parse_xaml(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    out: dict[str, str] = {}
    # Each entry: <s:String x:Key="Foo">bar</s:String>
    entry_re = re.compile(
        r'<(?:s:String|FlowDirection|HorizontalAlignment)\s+x:Key="([^"]+)"\s*>(.*?)'
        r'</(?:s:String|FlowDirection|HorizontalAlignment)>',
        re.DOTALL,
    )
    for key, value in entry_re.findall(text):
        out[key] = _unescape(value)
    return out


def _unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#10;", "\n")
        .replace("&#13;", "\r")
    )


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"Not a directory: {src}")
        return 1

    out_dir = Path(__file__).resolve().parent.parent / "ytpdl" / "i18n" / "locales"
    out_dir.mkdir(parents=True, exist_ok=True)

    english = parse_xaml(src / "English.xaml")
    index: list[dict] = []

    for display, (code, en_name, native, rtl) in LANGUAGES.items():
        xaml = src / f"{display}.xaml"
        strings = dict(english)
        if xaml.exists():
            strings.update({k: v for k, v in parse_xaml(xaml).items() if v.strip()})
        strings.setdefault("FlowDirection", "RightToLeft" if rtl else "LeftToRight")

        payload = {
            "@meta": {
                "code": code,
                "english_name": en_name,
                "native_name": native,
                "rtl": rtl,
            },
            "strings": strings,
        }
        (out_dir / f"{code}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        index.append({"code": code, "english_name": en_name, "native_name": native, "rtl": rtl})
        print(f"wrote {code}.json ({len(strings)} keys)")

    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote index.json ({len(index)} locales)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
