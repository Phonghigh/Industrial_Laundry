interface StatusBannerProps {
  deviceId: string;
  pendingCount: number;
  lastAction: string;
}

export function StatusBanner({ deviceId, pendingCount, lastAction }: StatusBannerProps) {
  const isSynced = pendingCount === 0;

  return (
    <>
      <header className="station-header">
        <div>
          <div className="header-device">DEVICE ID: {deviceId}</div>
          <h1 className="header-title">OPERATIONAL TERMINAL</h1>
        </div>

        <div className={`sync-indicator ${isSynced ? "synced" : "pending"}`}>
          <div className={`indicator-light ${isSynced ? "green" : "yellow"}`} />
          <span>
            {isSynced ? "SYSTEM SYNCED" : `${pendingCount} LOCAL SYNCING`}
          </span>
        </div>
      </header>

      <footer className="activity-footer">
        <span style={{ color: "var(--color-text-muted)" }}>READY FOR OPERATOR INPUT</span>
        {lastAction && (
          <div className="toast-status success">{lastAction}</div>
        )}
      </footer>
    </>
  );
}
