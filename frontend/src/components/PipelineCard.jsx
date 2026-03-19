import { useNavigate } from 'react-router-dom'
import styles from './PipelineCard.module.css'
import { StatusBadge } from './StatusBadge'

function formatRelativeTime(isoString) {
  if (!isoString) return ''
  const diff = Date.now() - new Date(isoString).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60)  return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60)  return `${m}m ago`
  const h = Math.floor(m / 60)
  return `${h}h ago`
}

function formatDuration(seconds) {
  if (seconds == null) return ''
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return s > 0 ? `${m}m ${s}s` : `${m}m`
}

export function PipelineCard({ pipeline }) {
  const navigate = useNavigate()
  const currentStage = pipeline._currentStage ?? pipeline.stages?.find(s => s.status === 'running')
  const totalStages  = pipeline.stages?.length ?? 0

  return (
    <div className={styles.card} onClick={() => navigate(`/pipelines/${pipeline.id}`)}>
      <div className={styles.header}>
        <StatusBadge status={pipeline.status} />
        <span className={styles.name}>{pipeline.name}</span>
        <span className={styles.id}>#{pipeline.id}</span>
      </div>
      <div className={styles.repo}>
        {pipeline.repository} @ {pipeline.branch}
      </div>
      <div className={styles.meta}>
        {pipeline.status === 'running' && currentStage ? (
          <>
            <span>Stage {currentStage.order}/{totalStages}</span>
            <span className={styles.dot}>•</span>
            <span>{currentStage.name}</span>
          </>
        ) : (
          <>
            <span>{pipeline.status}</span>
            {pipeline.duration_seconds != null && (
              <>
                <span className={styles.dot}>•</span>
                <span>{formatDuration(pipeline.duration_seconds)}</span>
              </>
            )}
            {pipeline.finished_at && (
              <>
                <span className={styles.dot}>•</span>
                <span>{formatRelativeTime(pipeline.finished_at)}</span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}
