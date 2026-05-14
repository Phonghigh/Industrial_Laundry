import type { StuckBatch } from '../types'

interface Props {
  batches: StuckBatch[];
}

export function StuckBatchAlert({ batches }: Props) {
  return (
    <section className="grid-card col-narrow">
      <div className="card-header">
        <h3 className="card-title">
          <span style={{ color: 'var(--accent-danger)' }}>⚠️</span> Stuck Batches
        </h3>
        {batches.length > 0 && (
          <span className="alert-tag danger">{batches.length} Alerts</span>
        )}
      </div>

      <div className="alert-list">
        {batches.length > 0 ? (
          batches.map((b, i) => (
            <div key={i} className="alert-item stuck">
              <div className="alert-info">
                <span className="alert-main-text">Batch: {b.batch_code}</span>
                <span className="alert-sub-text">Currently at {b.station}</span>
              </div>
              <span style={{ color: 'var(--accent-danger)', fontWeight: 600, fontSize: '0.9rem' }}>
                {b.stuck_mins}m stuck
              </span>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <div className="empty-icon" style={{ color: 'var(--accent-success)' }}>✓</div>
            <div style={{ fontWeight: 500 }}>All systems normal</div>
            <div style={{ fontSize: '0.8rem' }}>No batches are currently stuck.</div>
          </div>
        )}
      </div>
    </section>
  )
}
