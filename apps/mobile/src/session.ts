import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

export type SellerSession = { id: string; guestToken: string };
const key = "proofscan-seller-v1";
const originValue = process.env.EXPO_PUBLIC_PROOFSCAN_ORIGIN;
const idPattern = /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const tokenPattern = /^[A-Za-z0-9_-]{43}$/;

export function apiOrigin() {
  if (!originValue) throw new Error("Set EXPO_PUBLIC_PROOFSCAN_ORIGIN before opening a seller session.");
  const url = new URL(originValue);
  if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("Use the configured ProofScan server origin, without a path or credentials.");
  }
  if (url.protocol !== "https:" && !(__DEV__ && url.protocol === "http:")) {
    throw new Error("The ProofScan server must use HTTPS.");
  }
  return url.origin;
}

export function parseSellerLink(raw: string): SellerSession {
  const link = new URL(raw.trim());
  if (link.origin !== apiOrigin() || link.username || link.password) throw new Error("Use a seller link from your configured ProofScan server.");
  const path = link.pathname.split("/");
  const id = path[2] ?? "";
  const guestToken = link.hash.slice(1);
  if (path.length !== 3 || path[1] !== "seller" || !idPattern.test(id) || !tokenPattern.test(guestToken)) {
    throw new Error("Paste the original seller link, including its private access code.");
  }
  return { id, guestToken };
}

type Store = {
  seller: SellerSession | null;
  restored: boolean;
  restore: () => Promise<void>;
  save: (seller: SellerSession) => Promise<void>;
  clear: () => Promise<void>;
};

export const useSession = create<Store>(set => ({
  seller: null,
  restored: false,
  async restore() {
    try {
      const raw = await SecureStore.getItemAsync(key);
      if (raw) {
        const value = JSON.parse(raw);
        if (value.origin === apiOrigin() && idPattern.test(value.id) && tokenPattern.test(value.guestToken)) {
          set({ seller: { id: value.id, guestToken: value.guestToken } });
        }
      }
    } finally { set({ restored: true }); }
  },
  async save(seller) {
    await SecureStore.setItemAsync(key, JSON.stringify({ ...seller, origin: apiOrigin() }));
    set({ seller, restored: true });
  },
  async clear() {
    await SecureStore.deleteItemAsync(key);
    set({ seller: null, restored: true });
  },
}));
