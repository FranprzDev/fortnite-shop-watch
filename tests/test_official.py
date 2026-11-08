"""Unit tests for shopwatch.official (pure fixtures, no network)."""

from __future__ import annotations

from shopwatch.official import cross_check, merge_official

VBUCKS = "MtxCurrency"


def make_offer(offer_id, price, item_names, name=None, currency=VBUCKS):
    return {
        "offerId": offer_id,
        "section": "Featured",
        "name": name or offer_id,
        "devName": f"[VIRTUAL]1 x {name or offer_id} for {price} {currency}",
        "itemNames": list(item_names),
        "finalPrice": price,
        "regularPrice": price,
        "outDate": None,
        "imageUrl": None,
        "currency": currency,
    }


def make_tile(offer_id, price, title=None, cur=VBUCKS, items=None):
    tile = {"offerId": offer_id, "price": price, "title": title or offer_id, "cur": cur}
    if items is not None:
        tile["items"] = items
    return tile


def snapshot_with(offers):
    return {"date": "2026-11-08T00:00:00Z", "hash": "abc", "offers": offers}


def test_cross_check_skips_non_vbucks_tiles_in_missing_from_api():
    snapshot = snapshot_with([make_offer("a", 500, ["Skin A"])])
    tiles = [
        make_tile("a", 500),
        make_tile("b", 800, cur="RealMoney"),
        make_tile("c", 1200),
    ]
    report = cross_check(snapshot, tiles)
    assert [tile["offerId"] for tile in report["missing_from_api"]] == ["c"]
    assert report["skipped_non_vbucks"] == 1


def test_cross_check_reports_price_mismatch_for_shared_offer():
    snapshot = snapshot_with([make_offer("a", 500, ["Skin A"], name="Skin A")])
    report = cross_check(snapshot, [make_tile("a", 800)])
    assert report["price_mismatches"] == [
        {"offerId": "a", "name": "Skin A", "snapshotPrice": 500, "officialPrice": 800}
    ]


def test_merge_appends_official_only_tile_with_provenance():
    snapshot = snapshot_with([make_offer("a", 500, ["Skin A"])])
    augmented, merged_ids, extra = merge_official(snapshot, [make_tile("b", 800, title="Tile B")])
    assert merged_ids == ["b"]
    added = [offer for offer in augmented["offers"] if offer["offerId"] == "b"][0]
    assert added["provenance"] == "official-web"
    assert added["name"] == "Tile B"
    assert added["currency"] == VBUCKS
    assert extra["removed_stale"] == []


def test_merge_removes_stale_duplicate_only_when_official_confirms_current():
    stale = make_offer("old", 1000, ["Skin X", "Pickaxe X"], name="Bundle X")
    current = make_offer("new", 1500, ["Skin X", "Pickaxe X"], name="Bundle X")
    snapshot = snapshot_with([stale, current])
    tiles = [make_tile("new", 1500)]
    augmented, merged_ids, extra = merge_official(snapshot, tiles)
    remaining_ids = {offer["offerId"] for offer in augmented["offers"]}
    assert remaining_ids == {"new"}
    assert extra["removed_stale"] == [
        {"offerId": "old", "name": "Bundle X", "finalPrice": 1000, "keptOfferId": "new"}
    ]
    assert merged_ids == []


def test_same_name_variants_are_never_removed_only_reported():
    # Real 2026-11-08 case: same bundle name, different sizes/prices. Even
    # with the official catalog confirming one offerId, a partial scrape
    # could be missing a legitimate variant, so code must keep both and
    # report the group for human curation.
    older = make_offer("old", 1000, ["Skin X"], name="Lote X")
    current = make_offer("new", 1500, ["Skin X", "Pickaxe X", "Glider X", "Wrap X"], name="Lote X")
    snapshot = snapshot_with([older, current])
    augmented, _, extra = merge_official(snapshot, [make_tile("new", 1500)])
    assert {offer["offerId"] for offer in augmented["offers"]} == {"old", "new"}
    assert extra["removed_stale"] == []
    assert extra["suspected_stale"] == [
        {
            "name": "Lote X",
            "offerIds": ["new", "old"],
            "prices": [1000, 1500],
            "officialConfirmedOfferIds": ["new"],
        }
    ]


def test_partial_catalog_missing_variant_does_not_remove_it():
    # Partial scrape: official shows only the cheap variant; the expensive
    # one may still be live. Nothing is removed.
    cheap = make_offer("cheap", 800, ["Skin Y"], name="Lote Y")
    full = make_offer("full", 1600, ["Skin Y", "Glider Y"], name="Lote Y")
    snapshot = snapshot_with([cheap, full])
    augmented, _, extra = merge_official(snapshot, [make_tile("cheap", 800)])
    assert {offer["offerId"] for offer in augmented["offers"]} == {"cheap", "full"}
    assert extra["removed_stale"] == []
    assert extra["suspected_stale"][0]["officialConfirmedOfferIds"] == ["cheap"]


def test_partial_catalog_missing_jam_tracks_leaves_them_untouched():
    # The official main page shows only a subset of jam tracks; API offers
    # absent from the official catalog must survive the merge.
    track_a = make_offer("t1", 500, ["Song A - Artist A"], name="Song A - Artist A")
    track_b = make_offer("t2", 500, ["Song B - Artist B"], name="Song B - Artist B")
    skin = make_offer("s1", 1200, ["Skin Z"], name="Skin Z")
    snapshot = snapshot_with([track_a, track_b, skin])
    augmented, _, extra = merge_official(snapshot, [make_tile("s1", 1200)])
    assert {offer["offerId"] for offer in augmented["offers"]} == {"t1", "t2", "s1"}
    assert extra["removed_stale"] == []
    assert extra["suspected_stale"] == []


def test_merge_keeps_same_name_group_when_official_shows_both():
    first = make_offer("one", 1000, ["Skin X"], name="Lote X")
    second = make_offer("two", 1500, ["Skin X", "Pickaxe X"], name="Lote X")
    snapshot = snapshot_with([first, second])
    tiles = [make_tile("one", 1000), make_tile("two", 1500)]
    augmented, _, extra = merge_official(snapshot, tiles)
    assert {offer["offerId"] for offer in augmented["offers"]} == {"one", "two"}
    assert extra["removed_stale"] == []


def test_merge_keeps_duplicates_when_official_data_absent():
    stale = make_offer("old", 1000, ["Skin X", "Pickaxe X"])
    current = make_offer("new", 1500, ["Skin X", "Pickaxe X"])
    snapshot = snapshot_with([stale, current])
    augmented, _, extra = merge_official(snapshot, [])
    assert {offer["offerId"] for offer in augmented["offers"]} == {"old", "new"}
    assert extra["removed_stale"] == []


def test_merge_keeps_group_when_official_confirms_none_or_both():
    first = make_offer("one", 1000, ["Skin X"])
    second = make_offer("two", 1500, ["Skin X"])
    snapshot = snapshot_with([first, second])
    ambiguous = merge_official(snapshot, [make_tile("other", 300)])[0]
    assert {offer["offerId"] for offer in ambiguous["offers"]} == {"one", "two", "other"}
    both = merge_official(snapshot_with([first, second]), [make_tile("one", 1000), make_tile("two", 1500)])[0]
    assert {offer["offerId"] for offer in both["offers"]} == {"one", "two"}


def test_merge_keeps_group_when_prices_equal():
    first = make_offer("one", 1000, ["Skin X"])
    second = make_offer("two", 1000, ["Skin X"])
    augmented, _, extra = merge_official(snapshot_with([first, second]), [make_tile("one", 1000)])
    assert {offer["offerId"] for offer in augmented["offers"]} == {"one", "two"}
    assert extra["removed_stale"] == []


def test_bundle_item_audit_reports_missing_items_without_mutating_offer():
    offer = make_offer("bundle", 2000, ["Skin A", "Skin B"], name="Bundle AB")
    tile = make_tile(
        "bundle",
        2000,
        items=[{"name": "Skin A"}, {"name": "Skin B"}, {"name": "Pickaxe C"}],
    )
    augmented, _, extra = merge_official(snapshot_with([offer]), [tile])
    assert extra["missing_items"] == [
        {"offerId": "bundle", "name": "Bundle AB", "missingItemNames": ["Pickaxe C"]}
    ]
    kept = [entry for entry in augmented["offers"] if entry["offerId"] == "bundle"][0]
    assert kept["itemNames"] == ["Skin A", "Skin B"]
