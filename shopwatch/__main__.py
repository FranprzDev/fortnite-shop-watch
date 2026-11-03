from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any, Optional

from .client import fetch_shop_snapshot
from .diffing import diff_snapshots
from .models import Change, ChangeKind, CurrencyStatus, ShopOffer, Snapshot, currency_status
from .report import build_baseline_report, build_report

SNAPSHOT_PATH = os.environ.get("SNAPSHOT_PATH", "data/shop-latest.json")
REPORTS_DIR = os.environ.get("REPORTS_DIR", "reports")


def info(message: str) -> None:
    print(f"[shop-watch] {message}")


def error(message: str) -> None:
    print(f"[shop-watch] ERROR {message}", file=sys.stderr)


def load_previous_snapshot() -> Optional[Snapshot]:
    try:
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        offers = []
        for offer in raw.get("offers") or []:
            offers.append(
                ShopOffer(
                    offerId=offer["offerId"],
                    section=offer["section"],
                    name=offer["name"],
                    devName=offer["devName"],
                    itemNames=list(offer.get("itemNames") or []),
                    finalPrice=offer["finalPrice"],
                    regularPrice=offer["regularPrice"],
                    outDate=offer.get("outDate"),
                    imageUrl=offer.get("imageUrl"),
                    currency=offer["currency"],
                )
            )
        return Snapshot(date=raw["date"], hash=raw["hash"], offers=offers)
    except Exception:  # noqa: BLE001 - mirror TS catch-all
        return None


def shop_date_key(date: str) -> str:
    return date[:10]


def change_to_dict(change: Change) -> dict[str, Any]:
    data: dict[str, Any] = {
        "kind": change.kind.value if isinstance(change.kind, ChangeKind) else change.kind,
        "offer": asdict(change.offer),
    }
    if change.oldPrice is not None:
        data["oldPrice"] = change.oldPrice
    if change.newPrice is not None:
        data["newPrice"] = change.newPrice
    return data


def write_json(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run() -> None:
    snapshot = fetch_shop_snapshot()
    previous = load_previous_snapshot()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_path = os.path.join(REPORTS_DIR, f"{shop_date_key(snapshot.date)}.md")
    display_date = "/".join(reversed(shop_date_key(snapshot.date).split("-")))
    previous_display_date = (
        None if previous is None else "/".join(reversed(shop_date_key(previous.date).split("-")))
    )
    excluded_non_vbucks = [
        {"name": offer.name, "offerId": offer.offerId, "currency": offer.currency}
        for offer in snapshot.offers
        if currency_status(offer) == CurrencyStatus.NonVbucks
    ]
    excluded_unverified = [
        {"name": offer.name, "offerId": offer.offerId}
        for offer in snapshot.offers
        if currency_status(offer) == CurrencyStatus.Unverified
    ]
    non_vbucks_note = (
        f"\nOfertas excluidas por no comprarse con PaVos: {len(excluded_non_vbucks)}\n"
        if len(excluded_non_vbucks) > 0
        else ""
    )
    unverified_note = (
        f"\nOfertas excluidas por moneda no verificada: {len(excluded_unverified)}\n"
        if len(excluded_unverified) > 0
        else ""
    )
    excluded_note = non_vbucks_note + unverified_note
    if previous is None:
        verified_offers = [
            offer for offer in snapshot.offers if currency_status(offer) == CurrencyStatus.Verified
        ]
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(build_baseline_report(display_date, verified_offers) + excluded_note)
        info(f"baseline seeded: {len(verified_offers)} offers")
        if excluded_note:
            info(excluded_note)
    else:
        changes = diff_snapshots(previous, snapshot)
        changes_json_path = os.path.join(REPORTS_DIR, f"{shop_date_key(snapshot.date)}.json")
        if len(changes) == 0 and os.path.exists(report_path):
            info("added=0 removed=0 priceChanged=0 (existing report kept)")
        else:
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(build_report(display_date, previous_display_date, changes) + excluded_note)
            write_json(
                changes_json_path,
                {
                    "shopDate": display_date,
                    "previousDate": previous_display_date,
                    "changes": [change_to_dict(change) for change in changes],
                    "excludedNonVbucks": excluded_non_vbucks,
                    "excludedUnverified": excluded_unverified,
                },
            )
            added = sum(1 for change in changes if change.kind == ChangeKind.Added)
            removed = sum(1 for change in changes if change.kind == ChangeKind.Removed)
            price_changed = sum(1 for change in changes if change.kind == ChangeKind.PriceChanged)
            info(f"added={added} removed={removed} priceChanged={price_changed}")
            if excluded_note:
                info(excluded_note)
    write_json(SNAPSHOT_PATH, asdict(snapshot))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shopwatch",
        description="Descarga la tienda de Fortnite, compara con el snapshot anterior y genera reportes.",
    )
    parser.parse_args(argv)
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - mirror TS catch-all
        error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())