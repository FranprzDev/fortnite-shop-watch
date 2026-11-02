import type { RawShopEntry, RawShopResponse, ShopOffer, Snapshot } from "./types.ts";

const SHOP_URL = "https://fortnite-api.com/v2/shop?language=es";
const USER_AGENT = "fortnite-shop-watch/1.0";
const REQUEST_TIMEOUT_MS = 20000;
const MAX_ATTEMPTS = 3;
const RETRY_DELAY_MS = 3000;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeEntry(entry: RawShopEntry): ShopOffer | null {
  if (!entry.offerId) {
    return null;
  }
  const firstItem = entry.brItems?.[0];
  const name = firstItem?.name ?? entry.devName ?? entry.offerId;
  return {
    offerId: entry.offerId,
    section: entry.layout?.name ?? entry.layoutId ?? "unknown",
    name,
    itemNames: (entry.brItems ?? []).map((item) => item.name).filter((n): n is string => typeof n === "string" && n.length > 0),
    finalPrice: entry.finalPrice ?? 0,
    regularPrice: entry.regularPrice ?? 0,
    outDate: entry.outDate ?? null,
    imageUrl: firstItem?.images?.featured ?? firstItem?.images?.icon ?? firstItem?.images?.smallIcon ?? null,
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
