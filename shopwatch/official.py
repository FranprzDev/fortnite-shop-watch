"""Reconciliation between the fortnite-api.com snapshot and the official web catalog.

Rules (kept conservative; nothing is removed without official confirmation):
- Non-V-Bucks tiles (RealMoney) are ignored everywhere and only counted.
- Official-only PaVos tiles are appended with provenance="official-web". Their
  name is the official tile title; offers that exist in the API keep the API
  (Spanish) name.
- Stale API duplicates (same item set, different offerId/price) are removed
  only when the official catalog contains exactly one offerId of the group.
  Without official data, nothing is removed.
- When an official tile carries its bundle item list, items missing from the
  API offer are reported in the sidecar; the offer itself is never mutated.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

from .models import VBUCKS_CURRENCY

PROVENANCE = "official-web"


def _snapshot_offers(snapshot: Any) -> list[Any]:
    if isinstance(snapshot, dict):
        return list(snapshot.get("offers") or [])
    if is_dataclass(snapshot):
        return list(getattr(snapshot, "offers", []) or [])
    return list(snapshot or [])


def _offer_id(offer: Any) -> Optional[str]:
    if isinstance(offer, dict):
        return offer.get("offerId")
    return getattr(offer, "offerId", None)


def _offer_name(offer: Any) -> Optional[str]:
    if isinstance(offer, dict):
        return offer.get("name")
    return getattr(offer, "name", None)


def _offer_price(offer: Any) -> Any:
    if isinstance(offer, dict):
        return offer.get("finalPrice")
    return getattr(offer, "finalPrice", None)


def _offer_item_names(offer: Any) -> list[str]:
    if isinstance(offer, dict):
        names = offer.get("itemNames")
    else:
        names = getattr(offer, "itemNames", None)
    return [name for name in names or [] if isinstance(name, str) and name]


def _offer_dict(offer: Any) -> Any:
    if is_dataclass(offer):
        return asdict(offer)
    return offer


def _tile_currency(tile: dict) -> Optional[str]:
    cur = tile.get("cur") or tile.get("currency")
    if isinstance(cur, str) and cur:
        return cur
    return None


def _is_non_vbucks_tile(tile: dict) -> bool:
    cur = _tile_currency(tile)
    return cur is not None and cur != VBUCKS_CURRENCY


def cross_check(snapshot_offers: Any, official_tiles: list[dict]) -> dict[str, Any]:
    offers = _snapshot_offers(snapshot_offers)
    snapshot_by_id = {
        offer_id: offer
        for offer in offers
        if (offer_id := _offer_id(offer)) is not None
    }
    official_by_id = {
        tile.get("offerId"): tile
        for tile in official_tiles or []
        if tile.get("offerId") is not None
    }

    skipped_non_vbucks = 0
    missing_from_api = []
    for tile in official_tiles or []:
        if _is_non_vbucks_tile(tile):
            skipped_non_vbucks += 1
            continue
        if tile.get("offerId") not in snapshot_by_id:
            missing_from_api.append(tile)
    missing_from_official = [
        _offer_dict(offer)
        for offer in offers
        if _offer_id(offer) not in official_by_id
    ]

    price_mismatches = []
    for offer_id, tile in official_by_id.items():
        offer = snapshot_by_id.get(offer_id)
        if offer is None:
            continue
        snapshot_price = _offer_price(offer)
        official_price = tile.get("price")
        if snapshot_price != official_price:
            price_mismatches.append(
                {
                    "offerId": offer_id,
                    "name": _offer_name(offer),
                    "snapshotPrice": snapshot_price,
                    "officialPrice": official_price,
                }
            )

    return {
        "missing_from_api": missing_from_api,
        "missing_from_official": missing_from_official,
        "price_mismatches": price_mismatches,
        "skipped_non_vbucks": skipped_non_vbucks,
    }


def _normalize_official_tile(tile: dict) -> dict[str, Any]:
    offer_id = tile["offerId"]
    name = tile.get("name") or tile.get("title") or offer_id
    price = tile.get("price")
    return {
        "offerId": offer_id,
        "name": name,
        "devName": f"[VIRTUAL]1 x {name} for {price} {VBUCKS_CURRENCY}",
        "finalPrice": price,
        "regularPrice": price,
        "currency": VBUCKS_CURRENCY,
        "section": tile.get("section") or tile.get("sec"),
        "itemNames": [name],
        "imageUrl": tile.get("imageUrl") or tile.get("img"),
        "outDate": tile.get("outDate"),
        "items": copy.deepcopy(tile.get("items") or []),
        "namedBundle": False,
    }


def _find_stale_duplicates(offers: list[Any], official_ids: set[str]) -> list[dict[str, Any]]:
    """Snapshot offers confirmed stale by the official catalog.

    Groups offers by their exact item-name set and by their exact (casefolded)
    display name: both signals catch API entries left behind at an old price
    while a variant (same contents or same name) is live at a new price. A
    group is only eligible when it has more than one offerId and at least two
    distinct prices; the stale entries are removed only when the official
    catalog confirms exactly one offerId of the group as current. Anything
    ambiguous is kept, and without official data nothing is removed.
    """
    if not official_ids:
        return []
    groups: dict[Any, list[Any]] = {}
    for offer in offers:
        item_names = _offer_item_names(offer)
        if item_names:
            groups.setdefault(("items", frozenset(item_names)), []).append(offer)
        name = _offer_name(offer)
        if isinstance(name, str) and name.strip():
            groups.setdefault(("name", name.strip().casefold()), []).append(offer)
    stale_by_id: dict[str, dict[str, Any]] = {}
    for group in groups.values():
        offer_ids = {_offer_id(offer) for offer in group}
        offer_ids.discard(None)
        prices = {_offer_price(offer) for offer in group}
        if len(offer_ids) < 2 or len(prices) < 2:
            continue
        kept_ids = offer_ids & official_ids
        if len(kept_ids) != 1:
            continue
        kept_id = next(iter(kept_ids))
        for offer in group:
            offer_id = _offer_id(offer)
            if offer_id is None or offer_id == kept_id or offer_id in stale_by_id:
                continue
            stale_by_id[offer_id] = {
                "offerId": offer_id,
                "name": _offer_name(offer),
                "finalPrice": _offer_price(offer),
                "keptOfferId": kept_id,
            }
    return list(stale_by_id.values())


def _audit_bundle_items(snapshot_offers: list[Any], official_tiles: list[dict]) -> list[dict[str, Any]]:
    """Report tile items missing from the matching API offer (never mutates)."""
    by_id = {
        offer_id: offer
        for offer in snapshot_offers
        if (offer_id := _offer_id(offer)) is not None
    }
    findings: list[dict[str, Any]] = []
    for tile in official_tiles or []:
        offer_id = tile.get("offerId")
        items = tile.get("items") or []
        tile_names = [
            item.get("name")
            for item in items
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item.get("name")
        ]
        if not offer_id or not tile_names:
            continue
        offer = by_id.get(offer_id)
        if offer is None:
            continue
        offer_names = set(_offer_item_names(offer))
        missing = [name for name in tile_names if name not in offer_names]
        if missing:
            findings.append(
                {
                    "offerId": offer_id,
                    "name": _offer_name(offer),
                    "missingItemNames": missing,
                }
            )
    return findings


def merge_official(snapshot: Any, official_tiles: list[dict]) -> tuple[Any, list[str], dict[str, Any]]:
    if not isinstance(snapshot, dict):
        snapshot = asdict(snapshot) if is_dataclass(snapshot) else {"offers": list(snapshot or [])}
    augmented = copy.deepcopy(snapshot)
    offers = augmented.setdefault("offers", [])

    vbucks_tiles = [tile for tile in official_tiles or [] if not _is_non_vbucks_tile(tile)]
    official_ids = {
        offer_id
        for tile in vbucks_tiles
        if (offer_id := tile.get("offerId")) is not None
    }

    stale = _find_stale_duplicates(offers, official_ids)
    if stale:
        stale_ids = {entry["offerId"] for entry in stale}
        augmented["offers"] = [offer for offer in offers if _offer_id(offer) not in stale_ids]
        offers = augmented["offers"]

    existing_ids = {
        offer_id
        for offer in offers
        if (offer_id := _offer_id(offer)) is not None
    }
    merged_ids: list[str] = []
    for tile in vbucks_tiles:
        offer_id = tile.get("offerId")
        if not offer_id or offer_id in existing_ids:
            continue
        normalized = _normalize_official_tile(tile)
        normalized["provenance"] = PROVENANCE
        offers.append(normalized)
        existing_ids.add(offer_id)
        merged_ids.append(offer_id)

    extra = {
        "removed_stale": stale,
        "missing_items": _audit_bundle_items(_snapshot_offers(snapshot), official_tiles),
    }
    return augmented, merged_ids, extra


def _write_json(path: str, value: Any) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(snapshot_path: str, official_path: str, out_path: str) -> dict[str, Any]:
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    with open(official_path, "r", encoding="utf-8") as handle:
        official = json.load(handle)

    tiles = official.get("tiles") or []
    augmented, merged_ids, extra = merge_official(snapshot, tiles)
    report = cross_check(snapshot, tiles)
    counts = {
        "snapshot": len(_snapshot_offers(snapshot)),
        "official": len(tiles),
        "merged": len(merged_ids),
        "removed_stale": len(extra["removed_stale"]),
        "missing_items": len(extra["missing_items"]),
        "skipped_non_vbucks": report["skipped_non_vbucks"],
        "augmented": len(_snapshot_offers(augmented)),
        "missing_from_api": len(report["missing_from_api"]),
        "missing_from_official": len(report["missing_from_official"]),
        "price_mismatches": len(report["price_mismatches"]),
    }
    sidecar = {
        "merged": merged_ids,
        "removed_stale": extra["removed_stale"],
        "missing_items": extra["missing_items"],
        "provenance": PROVENANCE,
        "counts": counts,
    }

    _write_json(out_path, augmented)
    _write_json(f"{out_path}.official-report.json", sidecar)
    return sidecar


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shopwatch.official",
        description="Cross-check del snapshot de la API contra el scrape oficial y fusiona ofertas faltantes.",
    )
    parser.add_argument("snapshot", help="Snapshot JSON de la API")
    parser.add_argument("official", help="Catálogo JSON oficial (tiles del loaderData)")
    parser.add_argument("--out", required=True, help="Ruta del snapshot aumentado")
    args = parser.parse_args(argv)

    try:
        report = run(args.snapshot, args.official, args.out)
    except Exception as exc:  # noqa: BLE001 - CLI failure reporting
        print(f"[shop-watch] ERROR {exc}", file=__import__("sys").stderr)
        return 1

    print(
        "[shop-watch] official merged="
        f"{report['counts']['merged']} removed_stale="
        f"{report['counts']['removed_stale']} missing_items="
        f"{report['counts']['missing_items']} missing_from_api="
        f"{report['counts']['missing_from_api']} price_mismatches="
        f"{report['counts']['price_mismatches']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
