import json
import sys
from datetime import datetime, timezone
from enum import Enum

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


class Method(Enum):
    ID = "setcover-min-list-price-v2"


class Category(Enum):
    SONGS = "songs"
    BUNDLES = "bundles"
    SKINS = "skins"
    ACCESSORIES = "accessories"
    EMOTES = "emotes"
    OTHER = "other"


class ItemType(Enum):
    TRACK = "track"
    OUTFIT = "outfit"
    EMOTE = "emote"
    PICKAXE = "pickaxe"
    BACKPACK = "backpack"
    WRAP = "wrap"
    GLIDER = "glider"
    SHOE = "shoe"
    SIDEKICK = "sidekick"
    LOADINGSCREEN = "loadingscreen"
    CONTRAIL = "contrail"
    SPRAY = "spray"
    EMOTICON = "emoticon"
    TOY = "toy"
    UMBRELLA = "umbrella"
    INSTRUMENT = "instrument"
    CAR = "car"
    LEGO = "lego"
    OTHER = "other"


TYPE_CATEGORY = {
    ItemType.TRACK.value: Category.SONGS,
    ItemType.OUTFIT.value: Category.SKINS,
    ItemType.EMOTE.value: Category.EMOTES,
    ItemType.PICKAXE.value: Category.ACCESSORIES,
    ItemType.BACKPACK.value: Category.ACCESSORIES,
    ItemType.WRAP.value: Category.ACCESSORIES,
    ItemType.GLIDER.value: Category.ACCESSORIES,
    ItemType.SHOE.value: Category.ACCESSORIES,
    ItemType.SIDEKICK.value: Category.ACCESSORIES,
    ItemType.LOADINGSCREEN.value: Category.ACCESSORIES,
    ItemType.CONTRAIL.value: Category.ACCESSORIES,
    ItemType.SPRAY.value: Category.ACCESSORIES,
    ItemType.EMOTICON.value: Category.ACCESSORIES,
    ItemType.TOY.value: Category.ACCESSORIES,
    ItemType.UMBRELLA.value: Category.ACCESSORIES,
    ItemType.INSTRUMENT.value: Category.OTHER,
    ItemType.CAR.value: Category.OTHER,
    ItemType.LEGO.value: Category.OTHER,
    ItemType.OTHER.value: Category.OTHER,
}

ITEM_OBTAINED_KEYS = {
    Category.SONGS: "songs",
    Category.SKINS: "skins",
    Category.EMOTES: "emotes",
    Category.ACCESSORIES: "accessories",
    Category.OTHER: "other",
}

PRINCIPAL_PRIORITY = [ItemType.OUTFIT.value, ItemType.CAR.value, ItemType.INSTRUMENT.value, ItemType.LEGO.value, ItemType.TRACK.value]


class StatsError(Exception):
    pass


def category_of_type(item_type):
    return TYPE_CATEGORY.get(item_type, Category.OTHER)


def principal_category(items):
    for wanted in PRINCIPAL_PRIORITY:
        for item in items:
            if item["type"] == wanted:
                return category_of_type(wanted)
    return Category.OTHER


def offer_category(offer):
    if offer["namedBundle"]:
        return Category.BUNDLES
    items = offer["items"]
    if len(items) > 1:
        return principal_category(items)
    if items:
        return category_of_type(items[0]["type"])
    return Category.OTHER


def build_constraints(offers, universe_ids, item_index):
    item_count = len(universe_ids)
    offer_count = len(offers)
    rows = []
    cols = []
    for j, offer in enumerate(offers):
        for item_id in {item["id"] for item in offer["items"]}:
            if item_id in item_index:
                rows.append(item_index[item_id])
                cols.append(j)
    data = np.ones(len(rows))
    coverage = np.zeros((item_count, offer_count))
    for r, c in zip(rows, cols):
        coverage[r, c] = 1.0
    prices = np.array([offer["finalPrice"] for offer in offers], dtype=float)
    constraints = [LinearConstraint(coverage, lb=1, ub=np.inf)]
    return prices, constraints


def run_milp(prices, constraints, objective):
    result = milp(
        c=objective,
        integrality=np.ones(len(prices)),
        bounds=Bounds(0, 1),
        constraints=constraints,
    )
    if result.status != 0 or result.x is None:
        message = result.message if result.message else str(result.status)
        print(f"milp status: {result.status} {message}", file=sys.stderr)
        sys.exit(1)
    return result


def exact_cover(offers, universe_ids, item_index):
    prices, constraints = build_constraints(offers, universe_ids, item_index)
    result = run_milp(prices, constraints, prices)
    cost = int(round(result.fun))
    cost_constraint = LinearConstraint(prices.reshape(1, -1), lb=cost, ub=cost)

    fixed = []
    chosen = []
    for j in range(len(offers)):
        extra = [*constraints, cost_constraint]
        if fixed:
            selector = np.zeros((len(fixed), len(offers)))
            bounds = np.zeros(len(fixed))
            for row, (index, value) in enumerate(fixed):
                selector[row, index] = 1.0
                bounds[row] = value
            extra.append(LinearConstraint(selector, lb=bounds, ub=bounds))
        objective = np.zeros(len(offers))
        objective[j] = 1.0
        step = run_milp(prices, extra, objective)
        value = int(round(step.x[j]))
        fixed.append((j, value))
        chosen.append(value)
    total = sum(offers[j]["finalPrice"] * chosen[j] for j in range(len(offers)))
    if total != cost:
        raise StatsError(f"tie-break cost drifted from {cost} to {total}")
    return cost, chosen


def load_snapshot(path):
    with open(path, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    if not isinstance(snapshot, dict) or "date" not in snapshot or "hash" not in snapshot or not isinstance(snapshot.get("offers"), list):
        raise StatsError("snapshot has unexpected schema")
    for offer in snapshot["offers"]:
        if not isinstance(offer.get("items"), list) or "namedBundle" not in offer or "finalPrice" not in offer:
            raise StatsError("snapshot offers are not enriched")
    return snapshot


def compute_stats(snapshot):
    offers = snapshot["offers"]
    universe = {}
    for offer in offers:
        for item in offer["items"]:
            universe.setdefault(item["id"], item)
    universe_ids = list(universe.keys())
    item_index = {item_id: index for index, item_id in enumerate(universe_ids)}

    total_min, chosen = exact_cover(offers, universe_ids, item_index)
    chosen_offers = [offer for offer, value in zip(offers, chosen) if value == 1]

    coverage_count = {}
    obtained = set()
    for offer in chosen_offers:
        for item in offer["items"]:
            coverage_count[item["id"]] = coverage_count.get(item["id"], 0) + 1
            obtained.add(item["id"])
    if len(obtained) != len(universe_ids):
        raise StatsError(f"covered {len(obtained)} of {len(universe_ids)} items")
    overlap = [item_id for item_id, count in coverage_count.items() if count > 1]

    single_ids = set()
    for offer in offers:
        if len(offer["items"]) == 1:
            single_ids.add(offer["items"][0]["id"])
    exclusive = [item_id for item_id in universe_ids if item_id not in single_ids]

    chosen_bundles = [offer for offer in chosen_offers if len(offer["items"]) > 1]
    chosen_singles = [offer for offer in chosen_offers if len(offer["items"]) == 1]
    chosen_named_bundles = [offer for offer in chosen_bundles if offer["namedBundle"]]
    chosen_combo_offers = [offer for offer in chosen_bundles if not offer["namedBundle"]]

    skins_singles = sum(1 for offer in chosen_offers if offer_category(offer) == Category.SKINS and len(offer["items"]) == 1)
    skins_combo_offers = sum(1 for offer in chosen_offers if offer_category(offer) == Category.SKINS and len(offer["items"]) > 1)

    categories = {category.value: {"paVos": 0, "purchases": 0} for category in Category}
    items_obtained = {key: 0 for key in ITEM_OBTAINED_KEYS.values()}
    obtained_by_category = {category: set() for category in ITEM_OBTAINED_KEYS}
    for offer in chosen_offers:
        category = offer_category(offer)
        categories[category.value]["paVos"] += offer["finalPrice"]
        categories[category.value]["purchases"] += 1
        for item in offer["items"]:
            item_category = category_of_type(item["type"])
            obtained_by_category[item_category].add(item["id"])
    for category, ids in obtained_by_category.items():
        items_obtained[ITEM_OBTAINED_KEYS[category]] = len(ids)

    return {
        "totalMinPaVos": total_min,
        "purchases": len(chosen_offers),
        "categories": categories,
        "namedBundlesInCatalog": sum(1 for offer in offers if offer["namedBundle"]),
        "chosenNamedBundles": len(chosen_named_bundles),
        "chosenComboOffers": len(chosen_combo_offers),
        "chosenSingles": len(chosen_singles),
        "skinsSingles": skins_singles,
        "skinsComboOffers": skins_combo_offers,
        "itemsCovered": len(obtained),
        "itemsObtained": items_obtained,
        "namedBundlePaVos": sum(offer["finalPrice"] for offer in chosen_named_bundles),
        "comboPaVos": sum(offer["finalPrice"] for offer in chosen_combo_offers),
        "bundlePaVos": sum(offer["finalPrice"] for offer in chosen_bundles),
        "singlePaVos": sum(offer["finalPrice"] for offer in chosen_singles),
        "overlapItems": len(overlap),
        "bundleExclusiveItems": len(exclusive),
    }


def upsert_totals(path, snapshot, stats):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            totals = json.load(handle)
    except FileNotFoundError:
        totals = {}
    days = totals.get("days")
    if not isinstance(days, dict):
        days = {}
    date_key = str(snapshot["date"])[:10]
    day = {
        "snapshotHash": snapshot["hash"],
        "totalMinPaVos": stats["totalMinPaVos"],
        "purchases": stats["purchases"],
        "categories": stats["categories"],
        "namedBundlesInCatalog": stats["namedBundlesInCatalog"],
        "chosenNamedBundles": stats["chosenNamedBundles"],
        "chosenComboOffers": stats["chosenComboOffers"],
        "chosenSingles": stats["chosenSingles"],
        "skinsSingles": stats["skinsSingles"],
        "skinsComboOffers": stats["skinsComboOffers"],
        "itemsCovered": stats["itemsCovered"],
        "itemsObtained": stats["itemsObtained"],
        "overlapItems": stats["overlapItems"],
    }
    days[date_key] = day
    totals["days"] = days
    totals["method"] = Method.ID.value
    totals["updatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(totals, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return date_key


def main(argv):
    if len(argv) not in (2, 3):
        print("usage: python3 -m shopwatch.stats <snapshot.json> [totals.json]", file=sys.stderr)
        return 2
    snapshot = load_snapshot(argv[1])
    stats = compute_stats(snapshot)
    if len(argv) == 3:
        date_key = upsert_totals(argv[2], snapshot, stats)
    else:
        date_key = str(snapshot["date"])[:10]
    universe_size = stats["itemsCovered"]
    print(
        f"stats: date={date_key} totalMin={stats['totalMinPaVos']} purchases={stats['purchases']} "
        f"bundles={stats['chosenNamedBundles']}/{stats['namedBundlePaVos']} "
        f"combos={stats['chosenComboOffers']}/{stats['comboPaVos']} "
        f"singles={stats['chosenSingles']} covered={stats['itemsCovered']}/{universe_size} "
        f"overlap={stats['overlapItems']}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except StatsError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)