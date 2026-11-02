import { ChangeKind, type Change, type ShopOffer } from "./types.ts";

function formatOutDate(outDate: string | null): string {
  if (!outDate) {
    return "sin fecha de salida";
  }
  const date = new Date(outDate);
  if (Number.isNaN(date.getTime())) {
    return outDate;
  }
  const day = String(date.getUTCDate()).padStart(2, "0");
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${day}/${month}/${date.getUTCFullYear()}`;
}

function offerLine(offer: ShopOffer): string {
  const parts = [`- ${offer.name} (${offer.section})`, `${offer.finalPrice} PaVos`, `sale ${formatOutDate(offer.outDate)}`];
  if (offer.imageUrl) {
    parts.push(offer.imageUrl);
  }
  return parts.join(" — ");
}

function priceChangeLine(change: Change): string {
  const parts = [`- ${change.offer.name} (${change.offer.section})`, `${change.previousPrice ?? "?"} -> ${change.offer.finalPrice} PaVos`];
  if (change.offer.imageUrl) {
    parts.push(change.offer.imageUrl);
  }
  return parts.join(" — ");
}

function groupBySection(changes: Change[]): Map<string, Change[]> {
  const grouped = new Map<string, Change[]>();
  for (const change of changes) {
    const section = change.offer.section;
    const list = grouped.get(section) ?? [];
    list.push(change);
    grouped.set(section, list);
  }
  return grouped;
}

const SECTION_TITLES: Record<ChangeKind, string> = {
  [ChangeKind.Added]: "### Nuevos",
  [ChangeKind.Removed]: "### Salieron",
  [ChangeKind.PriceChanged]: "### Cambios de precio",
};

export function buildReport(shopDate: string, previousDate: string | null, changes: Change[]): string {
  const comparison = previousDate ? ` (vs ${previousDate})` : "";
  const lines: string[] = [`## Cambios en la tienda — ${shopDate}${comparison}`, ""];
  if (changes.length === 0) {
    lines.push("Sin cambios respecto a la rotación anterior.");
    return lines.join("\n") + "\n";
  }
  for (const kind of [ChangeKind.Added, ChangeKind.Removed, ChangeKind.PriceChanged]) {
    const ofKind = changes.filter((change) => change.kind === kind);
    if (ofKind.length === 0) {
      continue;
    }
    lines.push(SECTION_TITLES[kind], "");
    for (const change of ofKind) {
      lines.push(kind === ChangeKind.PriceChanged ? priceChangeLine(change) : offerLine(change.offer));
    }
    lines.push("");
  }
  return lines.join("\n") + "\n";
}

export function buildBaselineReport(shopDate: string, offers: ShopOffer[]): string {
  const lines: string[] = [`## Base inicial — ${shopDate}`, ""];
  const changes = offers.map((offer) => ({ kind: ChangeKind.Added, offer }));
  for (const [section, sectionChanges] of groupBySection(changes)) {
    lines.push(`### ${section}`, "");
    for (const change of sectionChanges) {
      lines.push(offerLine(change.offer));
    }
    lines.push("");
  }
  return lines.join("\n") + "\n";
}
