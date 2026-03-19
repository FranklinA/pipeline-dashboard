import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import styles from './PipelineDetail.module.css'
import { fetchPipeline, cancelPipeline, retryPipeline, deletePipeline } from '../utils/api'
import { usePipelineContext } from '../context/PipelineContext'
import { StatusBadge } from './StatusBadge'
import { StageProgress } from './StageProgress'
import { LogViewer } from './LogViewer'

export function PipelineDetail() {
  const { id }     = useParams()
  const navigate   = useNavigate()
  const pipelineId = Number(id)
  const { lastMessage } = usePipelineContext()

  const [pipeline,      setPipeline]      = useState(null)
  const [loading,       setLoading]       = useState(true)
  const [selectedStage, setSelectedStage] = useState(null)
  const [actionError,   setActionError]   = useState('')

  const load = useCallback(async () => {
    try {
      const p = await fetchPipeline(pipelineId)
      setPipeline(p)
      // Auto-select the running or failed stage on first load
      setSelectedStage(prev => {
        if (prev) return prev
        const active = p.stages?.find(s => s.status === 'running' || s.status === 'failed')
        return active?.id ?? null
      })
    } catch {
      setPipeline(null)
    } finally {
      setLoading(false)
    }
  }, [pipelineId])

  useEffect(() => { load() }, [load])

  // Re-fetch when relevant WS messages arrive for this pipeline
  useEffect(() => {
    if (!lastMessage) return
    if (lastMessage.pipeline_id !== pipelineId) return
    if (lastMessage.type === 'pipeline_update' || lastMessage.type === 'pipeline_completed') {
      load()
    }
  }, [lastMessage, pipelineId, load])

  async function handleCancel() {
    setActionError('')
    try { await cancelPipeline(pipelineId); await load() }
    catch (err) { setActionError(err.message) }
  }

  async function handleRetry() {
    setActionError('')
    try {
      const newPipeline = await retryPipeline(pipelineId)
      navigate(`/pipelines/${newPipeline.id}`)
    } catch (err) { setActionError(err.message) }
  }

  async function handleDelete() {
    setActionError('')
    try { await deletePipeline(pipelineId); navigate('/pipelines') }
    catch (err) { setActionError(err.message) }
  }

  if (loading)   return <p className={styles.loading}>Loading...</p>
  if (!pipeline) return <p className={styles.loading}>Pipeline not found.</p>

  const { status } = pipeline
  const canCancel = status === 'pending' || status === 'running'
  const canRetry  = status === 'failed'  || status === 'cancelled'
  const canDelete = status === 'success' || status === 'failed' || status === 'cancelled'

  const selectedStageName = selectedStage
    ? pipeline.stages?.find(s => s.id === selectedStage)?.name ?? ''
    : ''

  return (
    <div className={styles.container}>
      <button className={styles.back} onClick={() => navigate('/pipelines')}>
        ← Back to Pipelines
      </button>

      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h1>{pipeline.name} <span className={styles.id}>#{pipeline.id}</span></h1>
          <StatusBadge status={status} />
        </div>
        <p className={styles.repo}>{pipeline.repository} @ {pipeline.branch}</p>
        <p className={styles.meta}>
          Triggered: {pipeline.trigger_type}
          {pipeline.started_at && ` • Started: ${new Date(pipeline.started_at).toLocaleTimeString()}`}
          {pipeline.duration_seconds != null && ` • Duration: ${pipeline.duration_seconds}s`}
        </p>
        <div className={styles.actions}>
          {canCancel && <button className={styles.btnCancel} onClick={handleCancel}>Cancel</button>}
          {canRetry  && <button className={styles.btnRetry}  onClick={handleRetry}>Retry</button>}
          {canDelete && <button className={styles.btnDelete} onClick={handleDelete}>Delete</button>}
        </div>
        {actionError && <p className={styles.error}>{actionError}</p>}
      </div>

      <div className={styles.stages}>
        {pipeline.stages?.map(stage => (
          <StageProgress
            key={stage.id}
            stage={stage}
            active={selectedStage === stage.id}
            onClick={() => setSelectedStage(stage.id)}
          />
        ))}
      </div>

      <div className={styles.logs}>
        <h3>Logs{selectedStageName ? `: ${selectedStageName}` : ''}</h3>
        <LogViewer pipelineId={pipelineId} stageId={selectedStage} />
      </div>
    </div>
  )
}
