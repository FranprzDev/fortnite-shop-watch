import { ShopItemType, VBUCKS_CURRENCY, type RawShopEntry, type RawShopResponse, type ShopItem, type ShopOffer, type Snapshot } from "./types.ts";

const SHOP_URL = "https://fortnite-api.com/v2/shop?language=es";
const USER_AGENT = "fortnite-shop-watch/1.0";
const REQUEST_TIMEOUT_MS = 20000;
const MAX_ATTEMPTS = 3;
const RETRY_DELAY_MS = 3000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function resolveName(entry: RawShopEntry): string {
  const firstItem = entry.brItems?.[0];
  if (firstItem?.name) {
    return firstItem.name;
  }
  if (entry.bundle?.name) {
    return entry.bundle.name;
  }
  const track = entry.tracks?.[0];
  if (track?.title) {
    return track.artist ? `${track.title} - ${track.artist}` : track.title;
  }
  const named = entry.instruments?.[0]?.name ?? entry.cars?.[0]?.name ?? entry.legoKits?.[0]?.name;
  if (named) {
    return named;
  }
  return entry.devName ?? entry.offerId ?? "unknown";
}

function resolveImageUrl(entry: RawShopEntry): string | null {
  const renderImage = entry.newDisplayAsset?.renderImages?.[0]?.image;
  if (renderImage) {
    return renderImage;
  }
  const firstItem = entry.brItems?.[0];
  const brImage = firstItem?.images?.featured ?? firstItem?.images?.icon ?? firstItem?.images?.smallIcon;
  if (brImage) {
    return brImage;
  }
  const trackArt = entry.tracks?.[0]?.albumArt;
  if (trackArt) {
    return trackArt;
  }
  const sizedImage = entry.instruments?.[0]?.images?.large ?? entry.instruments?.[0]?.images?.small ?? entry.cars?.[0]?.images?.large ?? entry.cars?.[0]?.images?.small;
  if (sizedImage) {
    return sizedImage;
  }
  const legoImage = entry.legoKits?.[0]?.images?.featured ?? entry.legoKits?.[0]?.images?.icon;
  if (legoImage) {
    return legoImage;
  }
  return entry.bundle?.image ?? null;
}

function collectItemNames(entry: RawShopEntry): string[] {
  const names: string[] = [];
  for (const item of entry.brItems ?? []) {
    if (item.name) {
      names.push(item.name);
    }
  }
  for (const track of entry.tracks ?? []) {
    if (track.title) {
      names.push(track.artist ? `${track.title} - ${track.artist}` : track.title);
    }
  }
  for (const group of [entry.instruments ?? [], entry.cars ?? [], entry.legoKits ?? []]) {
    for (const item of group) {
      if (item.name) {
        names.push(item.name);
      }
    }
  }
  return names;
}

function resolveCurrency(devName: string): string {
  const currencies: string[] = [];
  for (const match of devName.matchAll(/for\s+-?\d+\s+(\w+)/g)) {
    const currency = match[1];
    if (currency !== undefined && !currencies.includes(currency)) {
      currencies.push(currency);
    }
  }
  if (currencies.length === 0) {
    return "unknown";
  }
  if (currencies.length === 1 && currencies[0] === VBUCKS_CURRENCY) {
    return VBUCKS_CURRENCY;
  }
  return currencies.join(",");
}

function resolveBrItemType(value: string | undefined): ShopItemType {
  switch (value) {
    case ShopItemType.Outfit:
    case ShopItemType.Backpack:
    case ShopItemType.Pickaxe:
    case ShopItemType.Emote:
    case ShopItemType.Glider:
    case ShopItemType.Wrap:
    case ShopItemType.Shoe:
    case ShopItemType.Sidekick:
    case ShopItemType.LoadingScreen:
    case ShopItemType.Contrail:
    case ShopItemType.Spray:
    case ShopItemType.Emoticon:
    case ShopItemType.Toy:
    case ShopItemType.Umbrella:
      return value;
    default:
      return ShopItemType.Other;
  }
}

function collectItems(entry: RawShopEntry): ShopItem[] {
  const items: ShopItem[] = [];
  for (const item of entry.brItems ?? []) {
    if (item.id) {
      items.push({ id: item.id, name: item.name ?? "", type: resolveBrItemType(item.type?.value) });
    }
  }
  for (const track of entry.tracks ?? []) {
    if (track.id) {
      items.push({ id: track.id, name: track.title ?? "", type: ShopItemType.Track });
    }
  }
  for (const item of entry.instruments ?? []) {
    if (item.id) {
      items.push({ id: item.id, name: item.name ?? "", type: ShopItemType.Instrument });
    }
  }
  for (const item of entry.cars ?? []) {
    if (item.id) {
      items.push({ id: item.id, name: item.name ?? "", type: ShopItemType.Car });
    }
  }
  for (const item of entry.legoKits ?? []) {
    if (item.id) {
      items.push({ id: item.id, name: item.name ?? "", type: ShopItemType.Lego });
    }
  }
  return items;
}

function isNamedBundle(entry: RawShopEntry): boolean {
  return typeof entry.bundle === "object" && entry.bundle !== null && typeof entry.bundle.name === "string" && entry.bundle.name.length > 0;
}

function normalizeEntry(entry: RawShopEntry): ShopOffer | null {
  if (!entry.offerId) {
    return null;
  }
  const devName = entry.devName ?? "";
  return {
    offerId: entry.offerId,
    section: entry.layout?.name ?? entry.layoutId ?? "unknown",
    name: resolveName(entry),
    devName,
    itemNames: collectItemNames(entry),
    finalPrice: entry.finalPrice ?? 0,
    regularPrice: entry.regularPrice ?? 0,
    outDate: entry.outDate ?? null,
    imageUrl: resolveImageUrl(entry),
    currency: resolveCurrency(devName),
    items: collectItems(entry),
    namedBundle: isNamedBundle(entry),
  };
}

async function requestShop(): Promise<RawShopResponse> {
  const response = await fetch(SHOP_URL, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`shop request failed with HTTP ${response.status}`);
  }
  return (await response.json()) as RawShopResponse;
}

export async function fetchShopSnapshot(): Promise<Snapshot> {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const body = await requestShop();
      const data = body.data;
      if (body.status !== 200 || !data || !Array.isArray(data.entries) || typeof data.date !== "string" || typeof data.hash !== "string") {
        throw new Error("shop response failed validation");
      }
      const offers = data.entries
        .map(normalizeEntry)
        .filter((offer): offer is ShopOffer => offer !== null);
      if (offers.length === 0) {
        throw new Error("shop response contained no valid offers");
      }
      return { date: data.date, hash: data.hash, offers };
    } catch (error) {
      lastError = error;
      if (attempt < MAX_ATTEMPTS) {
        await sleep(RETRY_DELAY_MS);
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}
