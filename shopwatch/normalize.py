from __future__ import annotations

import re
from typing import Optional

from .models import VBUCKS_CURRENCY, ShopOffer

_CURRENCY_RE = re.compile(r"for\s+-?\d+\s+(\w+)", re.ASCII)


def resolve_name(entry: dict) -> str:
    bundle = entry.get("bundle")
    if bundle and bundle.get("name"):
        return bundle["name"]
    items = entry.get("brItems") or []
    first_item = items[0] if items else None
    if first_item and first_item.get("name"):
        return first_item["name"]
    tracks = entry.get("tracks") or []
    track = tracks[0] if tracks else None
    if track and track.get("title"):
        return f"{track['title']} - {track['artist']}" if track.get("artist") else track["title"]
    named = None
    for group_key in ("instruments", "cars", "legoKits"):
        group = entry.get(group_key) or []
        if group and group[0].get("name"):
            named = group[0]["name"]
            break
    if named:
        return named
    return entry.get("devName") or entry.get("offerId") or "unknown"


def resolve_image_url(entry: dict) -> Optional[str]:
    render_images = (entry.get("newDisplayAsset") or {}).get("renderImages") or []
    render_image = render_images[0].get("image") if render_images else None
    if render_image:
        return render_image
    br_items = entry.get("brItems") or []
    first_item = br_items[0] if br_items else None
    if first_item:
        images = first_item.get("images") or {}
        br_image = images.get("featured") or images.get("icon") or images.get("smallIcon")
        if br_image:
            return br_image
    tracks = entry.get("tracks") or []
    track_art = tracks[0].get("albumArt") if tracks else None
    if track_art:
        return track_art
    sized_image = None
    for group_key in ("instruments", "cars"):
        group = entry.get(group_key) or []
        if group:
            images = group[0].get("images") or {}
            sized_image = images.get("large") or images.get("small")
            if sized_image:
                break
    if sized_image:
        return sized_image
    lego_kits = entry.get("legoKits") or []
    if lego_kits:
        images = lego_kits[0].get("images") or {}
        lego_image = images.get("featured") or images.get("icon")
        if lego_image:
            return lego_image
    bundle = entry.get("bundle")
    return bundle.get("image") if bundle and bundle.get("image") else None


def collect_item_names(entry: dict) -> list[str]:
    names: list[str] = []
    for item in entry.get("brItems") or []:
        if item.get("name"):
            names.append(item["name"])
    for track in entry.get("tracks") or []:
        if track.get("title"):
            names.append(f"{track['title']} - {track['artist']}" if track.get("artist") else track["title"])
    for group_key in ("instruments", "cars", "legoKits"):
        for item in entry.get(group_key) or []:
            if item.get("name"):
                names.append(item["name"])
    return names


def resolve_currency(dev_name: str) -> str:
    currencies: list[str] = []
    for match in _CURRENCY_RE.finditer(dev_name):
        currency = match.group(1)
        if currency is not None and currency not in currencies:
            currencies.append(currency)
    if len(currencies) == 0:
        return "unknown"
    if len(currencies) == 1 and currencies[0] == VBUCKS_CURRENCY:
        return VBUCKS_CURRENCY
    return ",".join(currencies)


def normalize_entry(entry: dict) -> Optional[ShopOffer]:
    offer_id = entry.get("offerId")
    if not offer_id:
        return None
    dev_name = entry.get("devName") or ""
    layout = entry.get("layout") or {}
    return ShopOffer(
        offerId=offer_id,
        section=layout.get("name") or entry.get("layoutId") or "unknown",
        name=resolve_name(entry),
        devName=dev_name,
        itemNames=collect_item_names(entry),
        finalPrice=entry.get("finalPrice") if entry.get("finalPrice") is not None else 0,
        regularPrice=entry.get("regularPrice") if entry.get("regularPrice") is not None else 0,
        outDate=entry.get("outDate") if entry.get("outDate") is not None else None,
        imageUrl=resolve_image_url(entry),
        currency=resolve_currency(dev_name),
    )
