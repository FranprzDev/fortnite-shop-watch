export const VBUCKS_CURRENCY = "MtxCurrency";

export enum CurrencyStatus {
  Verified = "verified",
  NonVbucks = "nonVbucks",
  Unverified = "unverified",
}

export function currencyStatus(offer: { currency?: string }): CurrencyStatus {
  if (offer.currency === VBUCKS_CURRENCY) {
    return CurrencyStatus.Verified;
  }
  if (offer.currency === undefined || offer.currency === "unknown") {
    return CurrencyStatus.Unverified;
  }
  return CurrencyStatus.NonVbucks;
}

export enum ShopItemType {
  Outfit = "outfit",
  Backpack = "backpack",
  Pickaxe = "pickaxe",
  Emote = "emote",
  Glider = "glider",
  Wrap = "wrap",
  Shoe = "shoe",
  Sidekick = "sidekick",
  LoadingScreen = "loadingscreen",
  Contrail = "contrail",
  Spray = "spray",
  Emoticon = "emoticon",
  Toy = "toy",
  Umbrella = "umbrella",
  Track = "track",
  Instrument = "instrument",
  Car = "car",
  Lego = "lego",
  Other = "other",
}

export interface ShopItem {
  id: string;
  name: string;
  type: ShopItemType;
}

export interface ShopOffer {
  offerId: string;
  section: string;
  name: string;
  devName: string;
  itemNames: string[];
  finalPrice: number;
  regularPrice: number;
  outDate: string | null;
  imageUrl: string | null;
  currency: string;
  items: ShopItem[];
  namedBundle: boolean;
}

export interface Snapshot {
  date: string;
  hash: string;
  offers: ShopOffer[];
}

export enum ChangeKind {
  Added = "added",
  Removed = "removed",
  PriceChanged = "priceChanged",
}

export interface Change {
  kind: ChangeKind;
  offer: ShopOffer;
  oldPrice?: number;
  newPrice?: number;
}

export interface RawShopImageSet {
  featured?: string;
  icon?: string;
  smallIcon?: string;
}

export interface RawValue {
  value?: string;
}

export interface RawShopItem {
  id?: string;
  name?: string;
  type?: RawValue;
  images?: RawShopImageSet;
}

export interface RawTrack {
  id?: string;
  title?: string;
  artist?: string;
  albumArt?: string;
}

export interface RawSizedImages {
  small?: string;
  large?: string;
}

export interface RawNamedCosmetic {
  id?: string;
  name?: string;
  images?: RawSizedImages;
}

export interface RawLegoKit {
  id?: string;
  name?: string;
  images?: RawShopImageSet;
}

export interface RawBundle {
  name?: string;
  image?: string;
}

export interface RawRenderImage {
  image?: string;
}

export interface RawDisplayAsset {
  renderImages?: RawRenderImage[];
}

export interface RawShopLayout {
  id?: string;
  name?: string;
}

export interface RawShopEntry {
  offerId?: string;
  devName?: string;
  finalPrice?: number;
  regularPrice?: number;
  outDate?: string;
  layoutId?: string;
  layout?: RawShopLayout;
  brItems?: RawShopItem[];
  tracks?: RawTrack[];
  instruments?: RawNamedCosmetic[];
  cars?: RawNamedCosmetic[];
  legoKits?: RawLegoKit[];
  bundle?: RawBundle;
  newDisplayAsset?: RawDisplayAsset;
}

export interface RawShopResponse {
  status?: number;
  data?: {
    hash?: string;
    date?: string;
    entries?: RawShopEntry[];
  };
}
