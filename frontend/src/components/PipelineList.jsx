import { useState } from 'react'
import styles from './PipelineList.module.css'
import { PipelineCard } from './PipelineCard'
import { usePipelines } from '../hooks/usePipelines'
import { createPipeline } from '../utils/api'
import { PIPELINE_TEMPLATES, TRIGGER_TYPES } from '../utils/constants'

const EMPTY_FORM = {
  name: '', repository: '', branch: 'main',
  trigger_type: 'manual', template: PIPELINE_TEMPLATES[0],
}

export function PipelineList() {
  const { pipelines, pagination, loading, filters, setFilters, addPipeline } = usePipelines()
  const [showModal, setShowModal] = useState(false)
  const [form,      setForm]      = useState(EMPTY_FORM)
  const [creating,  setCreating]  = useState(false)
  const [formError, setFormError] = useState('')

  function handleFilterChange(key, value) {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }))
  }

  function handlePageChange(delta) {
    setFilters(prev => ({ ...prev, page: prev.page + delta }))
  }

  async function handleCreate(e) {
    e.preventDefault()
    setFormError('')
    setCreating(true)
    try {
      const pipeline = await createPipeline(form)
      addPipeline(pipeline)
      setShowModal(false)
      setForm(EMPTY_FORM)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.toolbar}>
        <button className={styles.newBtn} onClick={() => setShowModal(true)}>
          + New Pipeline
        </button>
        <div className={styles.filters}>
          <select
            value={filters.status}
            onChange={e => handleFilterChange('status', e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <input
            type="text"
            placeholder="Repository..."
            value={filters.repository}
            onChange={e => handleFilterChange('repository', e.target.value)}
          />
        </div>
      </div>

      {loading && <p className={styles.loading}>Loading...</p>}

      <div className={styles.list}>
        {pipelines.map(p => <PipelineCard key={p.id} pipeline={p} />)}
        {!loading && pipelines.length === 0 && (
          <p className={styles.empty}>No pipelines found.</p>
        )}
      </div>

      {pagination && (
        <div className={styles.pagination}>
          <button
            onClick={() => handlePageChange(-1)}
            disabled={pagination.page <= 1}
          >
            ← Previous
          </button>
          <span>Page {pagination.page} of {pagination.total_pages}</span>
          <button
            onClick={() => handlePageChange(1)}
            disabled={pagination.page >= pagination.total_pages}
          >
            Next →
          </button>
        </div>
      )}

      {showModal && (
        <div className={styles.overlay} onClick={() => setShowModal(false)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <h2>New Pipeline</h2>
            <form onSubmit={handleCreate}>
              <label>
                Name *
                <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </label>
              <label>
                Repository *
                <input required value={form.repository} onChange={e => setForm(f => ({ ...f, repository: e.target.value }))} />
              </label>
              <label>
                Branch *
                <input required value={form.branch} onChange={e => setForm(f => ({ ...f, branch: e.target.value }))} />
              </label>
              <label>
                Trigger
                <select value={form.trigger_type} onChange={e => setForm(f => ({ ...f, trigger_type: e.target.value }))}>
                  {TRIGGER_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <label>
                Template
                <select value={form.template} onChange={e => setForm(f => ({ ...f, template: e.target.value }))}>
                  {PIPELINE_TEMPLATES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              {formError && <p className={styles.error}>{formError}</p>}
              <div className={styles.modalActions}>
                <button type="button" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" disabled={creating}>{creating ? 'Creating...' : 'Create'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
