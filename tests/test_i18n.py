from __future__ import annotations

from ytpdl.i18n import _EXTRA_EN, available_locales, translator


def test_all_locales_load_and_have_flow_direction():
    locales = available_locales()
    assert len(locales) == 14
    for loc in locales:
        translator.set_locale(loc.code)
        assert translator.tr("FlowDirection") in ("LeftToRight", "RightToLeft")
        assert translator.is_rtl == loc.rtl
    translator.set_locale("en")


def test_unknown_key_returns_itself():
    translator.set_locale("de")
    assert translator.tr("totally-unknown-key") == "totally-unknown-key"
    translator.set_locale("en")


def test_extra_en_keys_always_resolve_in_every_locale():
    for loc in available_locales():
        translator.set_locale(loc.code)
        for key in _EXTRA_EN:
            assert translator.tr(key), f"{loc.code}:{key} resolved to empty"
    translator.set_locale("en")


def test_translated_extra_key_uses_the_locale_value():
    translator.set_locale("de")
    assert translator.tr("AddToQueue") == "Zur Warteschlange"
    translator.set_locale("fr")
    assert translator.tr("Cancel") == "Annuler"
    translator.set_locale("en")


def test_format_params():
    translator.set_locale("en")
    assert translator.tr("NewVideos", count=3) == "3 new"
    translator.set_locale("de")
    assert translator.tr("SelectedOfTotal", count=2, total=9) == "2 von 9 ausgewählt"
    translator.set_locale("en")
