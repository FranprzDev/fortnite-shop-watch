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

export interface RawShopItem {
  name?: string;
  images?: RawShopImageSet;
}

export interface RawTrack {
  title?: string;
  artist?: string;
  albumArt?: string;
}

export interface RawSizedImages {
  small?: string;
  large?: string;
}

export interface RawNamedCosmetic {
  name?: string;
  images?: RawSizedImages;
}

export interface RawLegoKit {
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
