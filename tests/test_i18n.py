from __future__ import annotations

from ytpdl.i18n import available_locales, translator


def test_all_locales_load_and_have_flow_direction():
    locales = available_locales()
    assert len(locales) == 14
    for loc in locales:
        translator.set_locale(loc.code)
        assert translator.tr("FlowDirection") in ("LeftToRight", "RightToLeft")
        assert translator.is_rtl == loc.rtl
    translator.set_locale("en")


def test_missing_key_falls_back_to_english_extra_then_key():
    translator.set_locale("de")
    assert translator.tr("AddToQueue") == "Add to queue"  # extra, untranslated
    assert translator.tr("totally-unknown-key") == "totally-unknown-key"
    translator.set_locale("en")


def test_format_params():
    translator.set_locale("en")
    assert translator.tr("NewVideos", count=3) == "3 new"
