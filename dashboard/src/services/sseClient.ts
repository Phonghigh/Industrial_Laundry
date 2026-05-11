const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface OperationalState {
  type: "operational_state";
  stuck_batches: { batch_code: string; station: string; stuck_mins: number }[];
  inactive_stations: { station: string; silent_mins: number }[];
  station_throughput: { station: string; completed_last_hour: number }[];
  computed_at: string;
}

export function connectSSE(onState: (state: OperationalState) => void): () => void {
  const source = new EventSource(`${API_BASE}/api/v1/manager/overview`);

  source.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data) as OperationalState;
      onState(data);
    } catch {
      // malformed frame — skip
    }
  };

  source.onerror = () => {
    // SSE auto-reconnects natively; no manual retry needed
  };

  return () => source.close();
}
