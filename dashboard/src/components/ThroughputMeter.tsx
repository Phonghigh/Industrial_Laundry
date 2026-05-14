import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import type { StationThroughput } from '../types'

interface Props {
  data: StationThroughput[];
}

export function ThroughputMeter({ data }: Props) {
  return (
    <section className="grid-card col-wide">
      <div className="card-header">
        <h3 className="card-title">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16"
            style={{ color: 'var(--accent-color)' }}>
            <path d="M0 0h1v15h15v1H0V0zm10 5h2v8h-2V5zM6 8h2v5H6V8zm10-5h2v10h-2V3z" />
          </svg>
          Station Throughput
        </h3>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Completed Last 60 Mins
        </span>
      </div>

      <div style={{ width: '100%', height: 300 }}>
        {data.length > 0 ? (
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="station"
                stroke="var(--text-secondary)"
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="var(--text-secondary)"
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                contentStyle={{
                  backgroundColor: '#151d30',
                  borderColor: 'var(--border-glow)',
                  borderRadius: '8px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                }}
              />
              <Bar dataKey="completed_last_hour" radius={[4, 4, 0, 0]}>
                {data.map((_entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={index % 2 === 0 ? 'var(--accent-color)' : '#818cf8'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <div>No data recorded for this period</div>
          </div>
        )}
      </div>
    </section>
  )
}
