from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .models import Change, ChangeKind, ShopOffer


def format_out_date(out_date: Optional[str]) -> str:
    if not out_date:
        return "sin fecha de salida"
    try:
        date = datetime.fromisoformat(out_date.replace("Z", "+00:00"))
    except ValueError:
        return out_date
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    date = date.astimezone(timezone.utc)
    day = str(date.day).zfill(2)
    month = str(date.month).zfill(2)
    return f"{day}/{month}/{date.year}"


def offer_line(offer: ShopOffer) -> str:
    parts = [f"- {offer.name} ({offer.section})", f"{offer.finalPrice} PaVos", f"sale {format_out_date(offer.outDate)}"]
    if offer.imageUrl:
        parts.append(offer.imageUrl)
    return " — ".join(parts)


def price_change_line(change: Change) -> str:
    old_price = change.oldPrice if change.oldPrice is not None else "?"
    new_price = change.newPrice if change.newPrice is not None else change.offer.finalPrice
    parts = [f"- {change.offer.name} ({change.offer.section})", f"{old_price} -> {new_price} PaVos"]
    if change.offer.imageUrl:
        parts.append(change.offer.imageUrl)
    return " — ".join(parts)


def group_by_section(changes: list[Change]) -> dict[str, list[Change]]:
    grouped: dict[str, list[Change]] = {}
    for change in changes:
        section = change.offer.section
        grouped.setdefault(section, []).append(change)
    return grouped


SECTION_TITLES = {
    ChangeKind.Added: "### Nuevos",
    ChangeKind.Removed: "### Salieron",
    ChangeKind.PriceChanged: "### Cambios de precio",
}


def build_report(shop_date: str, previous_date: Optional[str], changes: list[Change]) -> str:
    comparison = f" (vs {previous_date})" if previous_date else ""
    lines = [f"## Cambios en la tienda — {shop_date}{comparison}", ""]
    if len(changes) == 0:
        lines.append("Sin cambios respecto a la rotación anterior.")
        return "\n".join(lines) + "\n"
    for kind in (ChangeKind.Added, ChangeKind.Removed, ChangeKind.PriceChanged):
        of_kind = [change for change in changes if change.kind == kind]
        if len(of_kind) == 0:
            continue
        lines.append(SECTION_TITLES[kind])
        lines.append("")
        for change in of_kind:
            lines.append(price_change_line(change) if kind == ChangeKind.PriceChanged else offer_line(change.offer))
        lines.append("")
    return "\n".join(lines) + "\n"


def build_baseline_report(shop_date: str, offers: list[ShopOffer]) -> str:
    lines = [f"## Base inicial — {shop_date}", ""]
    changes = [Change(kind=ChangeKind.Added, offer=offer) for offer in offers]
    for section, section_changes in group_by_section(changes).items():
        lines.append(f"### {section}")
        lines.append("")
        for change in section_changes:
            lines.append(offer_line(change.offer))
        lines.append("")
    return "\n".join(lines) + "\n"
