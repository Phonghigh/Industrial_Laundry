import { create } from "zustand";

export type EventType = "started" | "completed" | "issue_flagged" | "skipped";

interface StationState {
  stationId: string;
  batchCode: string;
  pendingCount: number;
  lastAction: string;
  scannerOpen: boolean;
  voiceListening: boolean;

  setStationId: (id: string) => void;
  setBatchCode: (code: string) => void;
  setPendingCount: (n: number) => void;
  flashAction: (msg: string) => void;
  clearAction: () => void;
  openScanner: () => void;
  closeScanner: () => void;
  setVoiceListening: (v: boolean) => void;
}

export const useStationStore = create<StationState>((set) => ({
  stationId: localStorage.getItem("active_station") ?? "station_intake_01",
  batchCode: "",
  pendingCount: 0,
  lastAction: "",
  scannerOpen: false,
  voiceListening: false,

  setStationId: (id) => {
    localStorage.setItem("active_station", id);
    set({ stationId: id });
  },

  setBatchCode: (code) => set({ batchCode: code }),

  setPendingCount: (n) => set({ pendingCount: n }),

  flashAction: (msg) => {
    set({ lastAction: msg });
    setTimeout(() => set({ lastAction: "" }), 3000);
  },

  clearAction: () => set({ lastAction: "" }),

  openScanner: () => set({ scannerOpen: true }),

  closeScanner: () => set({ scannerOpen: false }),

  setVoiceListening: (v) => set({ voiceListening: v }),
}));
