import styles from './StageProgress.module.css'

const STATUS_ICONS = {
  pending: '⏳',
  running: '🔵',
  success: '✅',
  failed:  '❌',
}

function getProgress(stage) {
  if (stage.status === 'success') return 100
  if (stage.status === 'pending') return 0
  if (stage.status === 'failed')  return 50
  return null // running → indeterminate
}

export function StageProgress({ stage, active, onClick }) {
  const progress       = getProgress(stage)
  const isIndeterminate = stage.status === 'running'

  return (
    <div
      className={`${styles.stage} ${active ? styles.active : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick?.()}
    >
      <div className={styles.header}>
        <span className={styles.icon}>{STATUS_ICONS[stage.status] ?? '⏳'}</span>
        <span className={styles.order}>{stage.order}.</span>
        <span className={styles.name}>{stage.name}</span>
        <span className={styles.detail}>
          {stage.status === 'running' && 'running'}
          {stage.status === 'success' && stage.duration_seconds != null && `${stage.duration_seconds}s`}
          {stage.status === 'pending' && 'pending'}
          {stage.status === 'failed'  && 'failed'}
        </span>
      </div>
      <div className={`${styles.bar} ${styles[stage.status]}`}>
        {isIndeterminate ? (
          <div className={styles.indeterminate} />
        ) : (
          <div className={styles.fill} style={{ width: `${progress}%` }} />
        )}
      </div>
    </div>
  )
}
