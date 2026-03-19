import styles from './StatusBadge.module.css'
import { STATUS_LABELS } from '../utils/constants'

export function StatusBadge({ status }) {
  return (
    <span className={`${styles.badge} ${styles[status] || ''}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}
