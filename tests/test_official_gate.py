"""Gate tests for the official reconcile trigger: date check and failure modes."""

from __future__ import annotations

import json

from shopwatch.official import main, same_shop_date, shop_date

SNAP = {
    "date": "2026-11-08T00:00:00Z",
    "hash": "abc",
    "offers": [
        {
            "offerId": "a",
            "section": "Featured",
            "name": "Skin A",
            "devName": "[VIRTUAL]1 x Skin A for 500 MtxCurrency",
            "itemNames": ["Skin A"],
            "finalPrice": 500,
            "regularPrice": 500,
            "outDate": None,
            "imageUrl": None,
            "currency": "MtxCurrency",
        }
    ],
}


def official(date, price=500):
    return {
        "date": date,
        "tiles": [{"offerId": "a", "price": price, "title": "Skin A", "cur": "MtxCurrency"}],
    }


def write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_shop_date_reads_first_ten_chars():
    assert shop_date({"date": "2026-11-08T00:00:00Z"}) == "2026-11-08"


def test_shop_date_missing_or_short_is_none():
    assert shop_date({}) is None
    assert shop_date({"date": None}) is None
    assert shop_date({"date": "2026-11"}) is None
    assert shop_date([1, 2]) is None


def test_same_shop_date_true_only_on_exact_match():
    assert same_shop_date({"date": "2026-11-08T00:00:00Z"}, {"date": "2026-11-08"})
    assert not same_shop_date({"date": "2026-11-08"}, {"date": "2026-11-07"})
    assert not same_shop_date({"date": "2026-11-08"}, {})
    assert not same_shop_date({}, {"date": "2026-11-08"})


def test_check_date_exit_zero_on_match(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    off = write(tmp_path, "off.json", official("2026-11-08"))
    assert main([snap, off, "--check-date"]) == 0


def test_check_date_exit_one_on_mismatch(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    off = write(tmp_path, "off.json", official("2026-11-07"))
    assert main([snap, off, "--check-date"]) == 1


def test_check_date_exit_one_on_missing_or_malformed(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([snap, str(bad), "--check-date"]) == 1
    assert main([snap, str(tmp_path / "nope.json"), "--check-date"]) == 1


def test_fail_on_price_mismatch_returns_two(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    off = write(tmp_path, "off.json", official("2026-11-08", price=800))
    assert main([snap, off, "--out", str(tmp_path / "out.json"), "--fail-on-price-mismatch"]) == 2


def test_price_mismatch_without_flag_still_succeeds(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    off = write(tmp_path, "off.json", official("2026-11-08", price=800))
    out = tmp_path / "out.json"
    assert main([snap, off, "--out", str(out)]) == 0
    sidecar = json.loads(
        tmp_path.joinpath("out.json.official-report.json").read_text(encoding="utf-8")
    )
    assert sidecar["counts"]["price_mismatches"] == 1


def test_clean_merge_with_flag_returns_zero(tmp_path):
    snap = write(tmp_path, "snap.json", SNAP)
    off = write(tmp_path, "off.json", official("2026-11-08"))
    assert main([snap, off, "--out", str(tmp_path / "out.json"), "--fail-on-price-mismatch"]) == 0
