import { ChangeKind, type Change, type ShopOffer, type Snapshot } from "./types.ts";

function indexByOfferId(offers: ShopOffer[]): Map<string, ShopOffer> {
  const map = new Map<string, ShopOffer>();
  for (const offer of offers) {
    map.set(offer.offerId, offer);
  }
  return map;
}

export function diffSnapshots(previous: Snapshot, next: Snapshot): Change[] {
  const changes: Change[] = [];
  const previousById = indexByOfferId(previous.offers);
  const nextById = indexByOfferId(next.offers);
  for (const offer of next.offers) {
    const before = previousById.get(offer.offerId);
    if (!before) {
      changes.push({ kind: ChangeKind.Added, offer });
    } else if (before.finalPrice !== offer.finalPrice) {
      changes.push({ kind: ChangeKind.PriceChanged, offer, oldPrice: before.finalPrice, newPrice: offer.finalPrice });
    }
  }
  for (const offer of previous.offers) {
    if (!nextById.has(offer.offerId)) {
      changes.push({ kind: ChangeKind.Removed, offer });
    }
  }
  return changes;
}
