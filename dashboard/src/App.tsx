import { useEffect } from "react";
import { connectSSE } from "./services/sseClient";
import { useDashboardStore } from "./stores/dashboardStore";
import { StuckBatchAlert } from "./components/StuckBatchAlert";
import { ThroughputMeter } from "./components/ThroughputMeter";
import { BottleneckPanel } from "./components/BottleneckPanel";

export default function App() {
  const { operationalState: state, connected, lastUpdated, applySnapshot, setConnected } =
    useDashboardStore();

  useEffect(() => {
    const disconnect = connectSSE((data) => applySnapshot(data));
    // Mark disconnected if the SSE client fires a close event
    return () => {
      setConnected(false);
      disconnect();
    };
  }, [applySnapshot, setConnected]);

  if (!state) {
    return (
      <div className="loading-container">
        <div className="spinner" />
        <p style={{ color: "var(--text-secondary)", letterSpacing: "0.05em" }}>
          CONNECTING TO REAL-TIME OPERATIONAL STREAM...
        </p>
      </div>
    );
  }

  const totalStuck = state.stuck_batches?.length ?? 0;
  const totalInactive = state.inactive_stations?.length ?? 0;
  const totalThroughput =
    state.station_throughput?.reduce((acc, cur) => acc + (cur.completed_last_hour ?? 0), 0) ?? 0;

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-brand">
          <h1 className="header-title">Industrial Laundry</h1>
          <p className="header-subtitle">Real-time Manager Dashboard — Phú Quốc Facility</p>
        </div>

        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          {lastUpdated && (
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              Sync: {lastUpdated}
            </span>
          )}
          <div className="status-pill">
            <div className={`status-dot ${connected ? "online" : "offline"}`} />
            {connected ? "LIVE SYSTEM CONNECTED" : "STREAM DISCONNECTED"}
          </div>
        </div>
      </header>

      <section className="stats-summary">
        <div className="stat-card">
          <span className="stat-label">Hourly Throughput</span>
          <span className="stat-value">
            {totalThroughput}{" "}
            <span style={{ fontSize: "1.2rem", color: "var(--text-secondary)" }}>batches</span>
          </span>
        </div>

        <div className="stat-card">
          <span className="stat-label">Stuck Batches</span>
          <span className={`stat-value ${totalStuck > 0 ? "danger" : ""}`}>{totalStuck}</span>
        </div>

        <div className="stat-card">
          <span className="stat-label">Inactive Stations</span>
          <span className={`stat-value ${totalInactive > 0 ? "warning" : ""}`}>
            {totalInactive}
          </span>
        </div>
      </section>

      <main className="dashboard-grid">
        <ThroughputMeter data={state.station_throughput ?? []} />
        <StuckBatchAlert batches={state.stuck_batches ?? []} />
        <BottleneckPanel
          throughput={state.station_throughput ?? []}
          inactive={state.inactive_stations ?? []}
        />
      </main>
    </div>
  );
}
