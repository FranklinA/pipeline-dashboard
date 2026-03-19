/** Funciones fetch al backend REST. */

import { API_BASE } from './constants'

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body?.detail?.message ?? `HTTP ${res.status}`)
    err.status = res.status
    err.code   = body?.detail?.code
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Pipelines ──────────────────────────────────────────────────────────────

export function fetchPipelines(params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
  ).toString()
  return request(`/pipelines${qs ? `?${qs}` : ''}`)
}

export function fetchPipeline(id) {
  return request(`/pipelines/${id}`)
}

export function createPipeline(data) {
  return request('/pipelines', { method: 'POST', body: JSON.stringify(data) })
}

export function cancelPipeline(id) {
  return request(`/pipelines/${id}/cancel`, { method: 'POST' })
}

export function retryPipeline(id) {
  return request(`/pipelines/${id}/retry`, { method: 'POST' })
}

export function deletePipeline(id) {
  return request(`/pipelines/${id}`, { method: 'DELETE' })
}

export function fetchStageLogs(pipelineId, stageId) {
  return request(`/pipelines/${pipelineId}/stages/${stageId}/logs`)
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export function fetchDashboard() {
  return request('/dashboard')
}
