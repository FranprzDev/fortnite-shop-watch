"""Unit tests for shopwatch.normalize (pure fixtures, no network)."""

from __future__ import annotations

from shopwatch.normalize import normalize_entry, resolve_currency, resolve_name


def test_resolve_currency_single_vbucks():
    assert resolve_currency("[VIRTUAL]1 x Skin for 1500 MtxCurrency") == "MtxCurrency"


def test_resolve_currency_unknown_when_no_match():
    assert resolve_currency("[VIRTUAL]1 x Skin for free") == "unknown"


def test_resolve_currency_multiple_joined():
    dev_name = "[VIRTUAL]1 x A for 100 MtxCurrency, 1 x B for 5 RealMoney"
    assert resolve_currency(dev_name) == "MtxCurrency,RealMoney"


def test_resolve_name_prefers_bundle():
    entry = {"bundle": {"name": "Lote X"}, "brItems": [{"name": "Skin Y"}]}
    assert resolve_name(entry) == "Lote X"


def test_resolve_name_falls_back_to_first_br_item():
    assert resolve_name({"brItems": [{"name": "Skin Y"}]}) == "Skin Y"


def test_resolve_name_track_title_with_artist():
    entry = {"tracks": [{"title": "Song", "artist": "Artist"}]}
    assert resolve_name(entry) == "Song - Artist"


def test_normalize_entry_returns_none_without_offer_id():
    assert normalize_entry({"devName": "x"}) is None


def test_normalize_entry_maps_minimal_entry():
    entry = {
        "offerId": "abc",
        "devName": "[VIRTUAL]1 x Skin Y for 1200 MtxCurrency",
        "finalPrice": 1200,
        "regularPrice": 1600,
        "brItems": [{"name": "Skin Y", "images": {"icon": "https://img/icon.png"}}],
        "layout": {"name": "Featured"},
    }
    offer = normalize_entry(entry)
    assert offer is not None
    assert offer.offerId == "abc"
    assert offer.name == "Skin Y"
    assert offer.section == "Featured"
    assert offer.finalPrice == 1200
    assert offer.regularPrice == 1600
    assert offer.currency == "MtxCurrency"
    assert offer.itemNames == ["Skin Y"]
    assert offer.imageUrl == "https://img/icon.png"
