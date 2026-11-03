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


def _offer_dict(offer: Any) -> Any:
    if is_dataclass(offer):
        return asdict(offer)
    return offer


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

    missing_from_api = [
        tile for tile in official_tiles or [] if tile.get("offerId") not in snapshot_by_id
    ]
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
    }


def _normalize_official_tile(tile: dict) -> dict[str, Any]:
    offer_id = tile["offerId"]
    name = tile.get("name") or offer_id
    price = tile.get("price")
    return {
        "offerId": offer_id,
        "name": name,
        "devName": f"[VIRTUAL]1 x {name} for {price} {VBUCKS_CURRENCY}",
        "finalPrice": price,
        "regularPrice": price,
        "currency": VBUCKS_CURRENCY,
        "section": tile.get("section"),
        "itemNames": [name],
        "imageUrl": tile.get("imageUrl"),
        "outDate": tile.get("outDate"),
        "items": copy.deepcopy(tile.get("items") or []),
        "namedBundle": False,
    }


def merge_official(snapshot: Any, official_tiles: list[dict]) -> tuple[Any, list[str]]:
    if not isinstance(snapshot, dict):
        snapshot = asdict(snapshot) if is_dataclass(snapshot) else {"offers": list(snapshot or [])}
    augmented = copy.deepcopy(snapshot)
    offers = augmented.setdefault("offers", [])

    existing_ids = {
        offer_id
        for offer in offers
        if (offer_id := _offer_id(offer)) is not None
    }
    merged_ids: list[str] = []
    for tile in official_tiles or []:
        offer_id = tile.get("offerId")
        if not offer_id or offer_id in existing_ids:
            continue
        offers.append(_normalize_official_tile(tile))
        existing_ids.add(offer_id)
        merged_ids.append(offer_id)

    return augmented, merged_ids


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
    augmented, merged_ids = merge_official(snapshot, tiles)
    report = cross_check(snapshot, tiles)
    counts = {
        "snapshot": len(_snapshot_offers(snapshot)),
        "official": len(tiles),
        "merged": len(merged_ids),
        "augmented": len(_snapshot_offers(augmented)),
        "missing_from_api": len(report["missing_from_api"]),
        "missing_from_official": len(report["missing_from_official"]),
        "price_mismatches": len(report["price_mismatches"]),
    }
    sidecar = {
        "merged": merged_ids,
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
        f"{report['counts']['merged']} missing_from_api="
        f"{report['counts']['missing_from_api']} price_mismatches="
        f"{report['counts']['price_mismatches']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())