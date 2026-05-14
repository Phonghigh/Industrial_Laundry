import { create } from "zustand";
import type { OperationalState } from "../types";

interface DashboardState {
  operationalState: OperationalState | null;
  connected: boolean;
  lastUpdated: string;

  applySnapshot: (data: OperationalState) => void;
  setConnected: (v: boolean) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  operationalState: null,
  connected: false,
  lastUpdated: "",

  // Each SSE event is a full snapshot — replace state, never merge (ADR-004)
  applySnapshot: (data) =>
    set({
      operationalState: data,
      connected: true,
      lastUpdated: new Date().toLocaleTimeString(),
    }),

  setConnected: (v) => set({ connected: v }),
}));
