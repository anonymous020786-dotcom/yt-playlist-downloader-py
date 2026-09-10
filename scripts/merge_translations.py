"""Fold scripts/translations_extra.py into ytpdl/i18n/locales/<code>.json.

Idempotent: existing keys are overwritten with the values from
translations_extra, everything else is left alone. Run after editing the
translation table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translations_extra import T

LOCALES = Path(__file__).resolve().parent.parent / "ytpdl" / "i18n" / "locales"


def main() -> int:
    langs = sorted({lang for by_lang in T.values() for lang in by_lang})
    for code in langs:
        path = LOCALES / f"{code}.json"
        if not path.exists():
            print(f"skip {code}: no locale file")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        strings = data.setdefault("strings", {})
        added = 0
        for key, by_lang in T.items():
            value = by_lang.get(code)
            if value and strings.get(key) != value:
                strings[key] = value
                added += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{code}: {added} strings written ({len(strings)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
