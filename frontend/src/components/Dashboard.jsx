import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import styles from './Dashboard.module.css'
import { fetchDashboard } from '../utils/api'
import { StatusBadge } from './StatusBadge'
import { usePipelineContext } from '../context/PipelineContext'

function formatDuration(seconds) {
  if (seconds == null) return 'N/A'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

export function Dashboard() {
  const navigate = useNavigate()
  const { lastMessage } = usePipelineContext()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      const d = await fetchDashboard()
      setData(d)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  // Refresh when a pipeline completes
  useEffect(() => {
    if (lastMessage?.type === 'pipeline_completed') load()
  }, [lastMessage])

  if (loading) return <p className={styles.loading}>Loading dashboard...</p>
  if (!data)   return <p className={styles.loading}>Could not load dashboard.</p>

  const { summary, avg_duration_seconds, success_rate_percent, recent_pipelines } = data
  const total = summary.total_pipelines || 1

  const statuses = ['pending', 'running', 'success', 'failed', 'cancelled']

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>Dashboard</h1>

      <div className={styles.cards}>
        <div className={styles.card}>
          <span className={styles.value}>{summary.total_pipelines}</span>
          <span className={styles.label}>Total</span>
        </div>
        <div className={styles.card}>
          <span className={styles.value}>{(summary.by_status.running ?? 0) + (summary.by_status.pending ?? 0)}</span>
          <span className={styles.label}>Active</span>
        </div>
        <div className={styles.card}>
          <span className={styles.value}>
            {success_rate_percent != null ? `${success_rate_percent.toFixed(0)}%` : 'N/A'}
          </span>
          <span className={styles.label}>Pass Rate</span>
        </div>
        <div className={styles.card}>
          <span className={styles.value}>{formatDuration(avg_duration_seconds)}</span>
          <span className={styles.label}>Avg Duration</span>
        </div>
      </div>

      <div className={styles.breakdown}>
        <h2>Status Breakdown</h2>
        {statuses.map(s => {
          const count = summary.by_status[s] ?? 0
          const pct   = Math.round((count / total) * 100)
          return (
            <div key={s} className={styles.barRow}>
              <span className={styles.barLabel}>{s}</span>
              <div className={styles.barTrack}>
                <div
                  className={`${styles.barFill} ${styles[s]}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className={styles.barCount}>{pct}% ({count})</span>
            </div>
          )
        })}
      </div>

      <div className={styles.recent}>
        <h2>Recent Pipelines</h2>
        <ul>
          {recent_pipelines.map(p => (
            <li
              key={p.id}
              className={styles.recentItem}
              onClick={() => navigate(`/pipelines/${p.id}`)}
            >
              <StatusBadge status={p.status} />
              <span className={styles.recentName}>{p.name} #{p.id}</span>
              {p.status === 'running'
                ? <span className={styles.recentMeta}>running</span>
                : p.duration_seconds != null
                  ? <span className={styles.recentMeta}>{formatDuration(p.duration_seconds)}</span>
                  : null}
            </li>
          ))}
          {recent_pipelines.length === 0 && (
            <li className={styles.empty}>No pipelines yet.</li>
          )}
        </ul>
      </div>
    </div>
  )
}
