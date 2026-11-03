from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

VBUCKS_CURRENCY = "MtxCurrency"


class CurrencyStatus(str, Enum):
    Verified = "verified"
    NonVbucks = "nonVbucks"
    Unverified = "unverified"


class ChangeKind(str, Enum):
    Added = "added"
    Removed = "removed"
    PriceChanged = "priceChanged"


def currency_status(offer: object) -> CurrencyStatus:
    currency = getattr(offer, "currency", None)
    if currency == VBUCKS_CURRENCY:
        return CurrencyStatus.Verified
    if currency is None or currency == "unknown":
        return CurrencyStatus.Unverified
    return CurrencyStatus.NonVbucks


@dataclass
class ShopOffer:
    offerId: str
    section: str
    name: str
    devName: str
    itemNames: list[str]
    finalPrice: float
    regularPrice: float
    outDate: Optional[str]
    imageUrl: Optional[str]
    currency: str


@dataclass
class Snapshot:
    date: str
    hash: str
    offers: list[ShopOffer] = field(default_factory=list)


@dataclass
class Change:
    kind: ChangeKind
    offer: ShopOffer
    oldPrice: Optional[float] = None
    newPrice: Optional[float] = None
