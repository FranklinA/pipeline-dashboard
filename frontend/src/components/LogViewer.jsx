import { useEffect, useRef, useState } from 'react'
import styles from './LogViewer.module.css'
import { fetchStageLogs } from '../utils/api'
import { usePipelineContext } from '../context/PipelineContext'

const LEVEL_CLASS = {
  info:    styles.info,
  warning: styles.warning,
  error:   styles.error,
}

function formatTime(isoString) {
  if (!isoString) return ''
  return new Date(isoString).toLocaleTimeString('en-US', { hour12: false })
}

export function LogViewer({ pipelineId, stageId }) {
  const [logs,    setLogs]    = useState([])
  const [loading, setLoading] = useState(false)
  const { liveLogs } = usePipelineContext()
  const bottomRef = useRef(null)

  useEffect(() => {
    if (!stageId) return
    setLogs([])
    setLoading(true)
    fetchStageLogs(pipelineId, stageId)
      .then(res => setLogs(res.logs ?? []))
      .catch(() => setLogs([]))
      .finally(() => setLoading(false))
  }, [pipelineId, stageId])

  // Merge live entries for this stage (deduplicated by timestamp+message)
  const liveEntries = liveLogs[stageId] ?? []
  const allLogs = [...logs]
  for (const entry of liveEntries) {
    const exists = allLogs.some(l => l.timestamp === entry.timestamp && l.message === entry.message)
    if (!exists) allLogs.push(entry)
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [allLogs.length])

  if (!stageId) {
    return <p className={styles.hint}>Click a stage to view its logs.</p>
  }

  return (
    <div className={styles.viewer}>
      {loading && <p className={styles.loading}>Loading logs...</p>}
      <div className={styles.lines}>
        {allLogs.map((entry, i) => (
          <div key={i} className={`${styles.line} ${LEVEL_CLASS[entry.level] ?? ''}`}>
            <span className={styles.time}>{formatTime(entry.timestamp)}</span>
            <span className={styles.level}>[{entry.level?.toUpperCase()}]</span>
            <span className={styles.msg}>{entry.message}</span>
          </div>
        ))}
        {!loading && allLogs.length === 0 && (
          <p className={styles.empty}>No logs yet.</p>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
