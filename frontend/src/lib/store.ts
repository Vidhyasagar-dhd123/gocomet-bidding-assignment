import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

/**
 * Global client state (server state lives in TanStack Query):
 * - actingSupplierId: the backend has no auth, so the user picks who they bid as.
 * - clockOffsetMs: server time − client time, so countdowns don't trust the local clock.
 */
interface AppState {
  actingSupplierId: number | null;
  setActingSupplier: (id: number | null) => void;
  clockOffsetMs: number;
  syncClock: (serverIso: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      actingSupplierId: null,
      setActingSupplier: (id) => set({ actingSupplierId: id }),
      clockOffsetMs: 0,
      syncClock: (serverIso) => set({ clockOffsetMs: Date.parse(serverIso) - Date.now() }),
    }),
    {
      name: "rfq-app",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ actingSupplierId: s.actingSupplierId }),
    },
  ),
);

export const serverNow = () => Date.now() + useAppStore.getState().clockOffsetMs;
