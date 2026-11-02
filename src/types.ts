export interface ShopOffer {
  offerId: string;
  section: string;
  name: string;
  itemNames: string[];
  finalPrice: number;
  regularPrice: number;
  outDate: string | null;
  imageUrl: string | null;
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
  previousPrice?: number;
}

export interface RawShopImageSet {
  featured?: string;
  icon?: string;
  smallIcon?: string;
}

export interface RawShopItem {
  name?: string;
  images?: RawShopImageSet;
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
}

export interface RawShopResponse {
  status?: number;
  data?: {
    hash?: string;
    date?: string;
    entries?: RawShopEntry[];
  };
}
