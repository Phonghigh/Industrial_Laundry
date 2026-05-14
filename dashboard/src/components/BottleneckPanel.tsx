import type { StationThroughput, InactiveStation } from '../types'

interface Props {
  throughput: StationThroughput[];
  inactive: InactiveStation[];
}

export function BottleneckPanel({ throughput, inactive }: Props) {
  // Bottleneck = active station with lowest completed_last_hour (exclude zero — those are inactive)
  const active = throughput.filter((s) => s.completed_last_hour > 0)
  const bottleneck = active.length >= 2
    ? active.reduce((min, s) => s.completed_last_hour < min.completed_last_hour ? s : min)
    : null

  return (
    <section className="grid-card col-wide">
      <div className="card-header">
        <h3 className="card-title">
          <span style={{ color: 'var(--accent-warning)' }}>⏳</span> Idle / Inactive Stations
        </h3>
        {inactive.length > 0 && (
          <span className="alert-tag warning">{inactive.length} idle</span>
        )}
      </div>

      {bottleneck && (
        <div className="alert-item stuck" style={{ marginBottom: '0.75rem' }}>
          <div className="alert-info">
            <span className="alert-main-text">Bottleneck: {bottleneck.station}</span>
            <span className="alert-sub-text">Lowest active throughput this hour</span>
          </div>
          <span style={{ color: 'var(--accent-danger)', fontWeight: 600, fontSize: '0.9rem' }}>
            {bottleneck.completed_last_hour} batches/h
          </span>
        </div>
      )}

      <div className="alert-list" style={{ maxHeight: 'none' }}>
        {inactive.length > 0 ? (
          inactive.map((s, i) => (
            <div key={i} className="alert-item inactive">
              <div className="alert-info">
                <span className="alert-main-text">Station: {s.station}</span>
                <span className="alert-sub-text">No operational events received recently</span>
              </div>
              <span style={{
                color: s.never_active ? 'var(--text-secondary)' : 'var(--accent-warning)',
                fontWeight: 500,
                fontSize: '0.85rem',
              }}>
                {s.never_active ? 'Never active' : `Idle for ${s.silent_mins} mins`}
              </span>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <div className="empty-icon">✨</div>
            <div>All stations actively reporting throughput</div>
          </div>
        )}
      </div>
    </section>
  )
}
