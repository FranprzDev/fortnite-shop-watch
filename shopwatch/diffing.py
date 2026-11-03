from __future__ import annotations

from .models import Change, ChangeKind, CurrencyStatus, ShopOffer, Snapshot, currency_status


def _index_by_offer_id(offers: list[ShopOffer]) -> dict[str, ShopOffer]:
    index: dict[str, ShopOffer] = {}
    for offer in offers:
        index[offer.offerId] = offer
    return index


def diff_snapshots(previous: Snapshot, next: Snapshot) -> list[Change]:
    changes: list[Change] = []
    previous_by_id = _index_by_offer_id(previous.offers)
    next_by_id = _index_by_offer_id(next.offers)
    for offer in next.offers:
        if currency_status(offer) != CurrencyStatus.Verified:
            continue
        before = previous_by_id.get(offer.offerId)
        if before is None:
            changes.append(Change(kind=ChangeKind.Added, offer=offer))
        elif before.finalPrice != offer.finalPrice:
            changes.append(
                Change(
                    kind=ChangeKind.PriceChanged,
                    offer=offer,
                    oldPrice=before.finalPrice,
                    newPrice=offer.finalPrice,
                )
            )
    for offer in previous.offers:
        if currency_status(offer) == CurrencyStatus.Verified and offer.offerId not in next_by_id:
            changes.append(Change(kind=ChangeKind.Removed, offer=offer))
    return changes
