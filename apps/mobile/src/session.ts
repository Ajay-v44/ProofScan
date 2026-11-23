import * as SecureStore from "expo-secure-store";
import { create } from "zustand";
import { isWorkspaceUrl, parseOrigin } from "./origin.cjs";

export type SellerSession = { id: string; guestToken: string };
const key = "proofscan-seller-v1";
const originValue = process.env.EXPO_PUBLIC_PROOFSCAN_ORIGIN;
const idPattern = /^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
const tokenPattern = /^[A-Za-z0-9_-]{43}$/;

export function apiOrigin() {
  return parseOrigin(originValue, __DEV__);
}

export function parseSellerLink(raw: string): SellerSession {
  const value = raw.trim();
  if (!isWorkspaceUrl(value, apiOrigin())) throw new Error("Use a seller link from your configured ProofScan server.");
  const link = new URL(value);
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

let pendingRestore: Promise<void> | undefined;

export const useSession = create<Store>(set => ({
  seller: null,
  restored: false,
  restore() {
    pendingRestore ??= SecureStore.getItemAsync(key).then(raw => {
      if (!raw) return;
      const value = JSON.parse(raw);
      if (value?.origin === apiOrigin() && typeof value.id === "string" && typeof value.guestToken === "string" &&
        idPattern.test(value.id) && tokenPattern.test(value.guestToken)) {
        set({ seller: { id: value.id, guestToken: value.guestToken } });
      }
    }).finally(() => {
      pendingRestore = undefined;
      set({ restored: true });
    });
    return pendingRestore;
  },
  async save(seller) {
    await SecureStore.setItemAsync(key, JSON.stringify({ ...seller, origin: apiOrigin() }), {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    set({ seller, restored: true });
  },
  async clear() {
    await SecureStore.deleteItemAsync(key);
    set({ seller: null, restored: true });
  },
}));
