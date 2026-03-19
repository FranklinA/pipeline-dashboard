import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { fetchPipelines } from '../utils/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { DEFAULT_PER_PAGE } from '../utils/constants'

const PipelineContext = createContext(null)

export function PipelineProvider({ children }) {
  const [pipelines,   setPipelines]   = useState([])
  const [pagination,  setPagination]  = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [filters,     setFilters]     = useState({ status: '', repository: '', page: 1 })
  const [liveLogs,    setLiveLogs]    = useState({})   // { stageId: LogEntry[] }
  const [lastMessage, setLastMessage] = useState(null)

  const load = useCallback(async (f) => {
    setLoading(true)
    try {
      const res = await fetchPipelines({
        status:     f.status     || undefined,
        repository: f.repository || undefined,
        page:       f.page,
        per_page:   DEFAULT_PER_PAGE,
      })
      setPipelines(res.data)
      setPagination(res.pagination)
    } catch (err) {
      console.error('Error loading pipelines:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(filters) }, [filters, load])

  const handleMessage = useCallback((msg) => {
    setLastMessage(msg)

    if (msg.type === 'pipeline_update') {
      setPipelines(prev => prev.map(p => {
        if (p.id !== msg.pipeline_id) return p
        const updatedStages = msg.data.stages_summary
          ? p.stages?.map(s => {
              const u = msg.data.stages_summary.find(x => x.id === s.id)
              return u ? { ...s, ...u } : s
            })
          : p.stages
        return { ...p, status: msg.data.status, stages: updatedStages, _currentStage: msg.data.current_stage }
      }))
    } else if (msg.type === 'pipeline_completed') {
      setPipelines(prev => prev.map(p =>
        p.id === msg.pipeline_id
          ? { ...p, status: msg.data.status, duration_seconds: msg.data.duration_seconds, finished_at: msg.data.finished_at, _currentStage: null }
          : p
      ))
    } else if (msg.type === 'log_entry') {
      setLiveLogs(prev => ({
        ...prev,
        [msg.stage_id]: [...(prev[msg.stage_id] || []), msg.data],
      }))
    }
  }, [])

  const { isConnected, reconnecting } = useWebSocket(handleMessage)

  const addPipeline = useCallback((pipeline) => {
    setPipelines(prev => [pipeline, ...prev])
  }, [])

  return (
    <PipelineContext.Provider value={{
      pipelines, pagination, loading, filters, setFilters,
      reload: load, addPipeline,
      liveLogs,
      lastMessage,
      isConnected, reconnecting,
    }}>
      {children}
    </PipelineContext.Provider>
  )
}

export function usePipelineContext() {
  const ctx = useContext(PipelineContext)
  if (!ctx) throw new Error('usePipelineContext must be used within PipelineProvider')
  return ctx
}
