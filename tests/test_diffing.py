"""Unit tests for shopwatch.diffing (pure fixtures, no network)."""

from __future__ import annotations

from shopwatch.diffing import diff_snapshots
from shopwatch.models import ChangeKind, ShopOffer, Snapshot


def make_offer(offer_id, price, currency="MtxCurrency"):
    return ShopOffer(
        offerId=offer_id,
        section="Featured",
        name=offer_id,
        devName=f"[VIRTUAL]1 x {offer_id} for {price} {currency}",
        itemNames=[offer_id],
        finalPrice=price,
        regularPrice=price,
        outDate=None,
        imageUrl=None,
        currency=currency,
    )


def snapshot(date, offers):
    return Snapshot(date=date, hash="h", offers=offers)


def kinds(changes):
    return sorted(change.kind.value for change in changes)


def test_added_removed_and_price_changed():
    previous = snapshot("2026-11-07", [make_offer("keep", 500), make_offer("drop", 300), make_offer("reprice", 800)])
    current = snapshot("2026-11-08", [make_offer("keep", 500), make_offer("reprice", 1000), make_offer("new", 200)])
    changes = diff_snapshots(previous, current)
    assert kinds(changes) == [ChangeKind.Added.value, ChangeKind.PriceChanged.value, ChangeKind.Removed.value]
    price_change = next(change for change in changes if change.kind == ChangeKind.PriceChanged)
    assert price_change.oldPrice == 800
    assert price_change.newPrice == 1000


def test_non_vbucks_offers_are_ignored():
    previous = snapshot("2026-11-07", [make_offer("pack", 1999, currency="RealMoney")])
    current = snapshot("2026-11-08", [])
    assert diff_snapshots(previous, current) == []
    assert diff_snapshots(current, snapshot("2026-11-09", [make_offer("pack2", 1999, currency="RealMoney")])) == []


def test_no_changes_when_identical():
    previous = snapshot("2026-11-07", [make_offer("keep", 500)])
    current = snapshot("2026-11-08", [make_offer("keep", 500)])
    assert diff_snapshots(previous, current) == []
