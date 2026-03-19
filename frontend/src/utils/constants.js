/** Configuración global y constantes compartidas. */

export const API_BASE = '/api'
export const WS_URL   = '/ws/pipelines'

/** Colores por estado — deben coincidir con las variables CSS en :root */
export const STATUS_COLORS = {
  pending:   'var(--color-pending)',
  running:   'var(--color-running)',
  success:   'var(--color-success)',
  failed:    'var(--color-failed)',
  cancelled: 'var(--color-cancelled)',
}

/** Etiquetas legibles por estado */
export const STATUS_LABELS = {
  pending:   'Pending',
  running:   'Running',
  success:   'Success',
  failed:    'Failed',
  cancelled: 'Cancelled',
}

/** Templates de pipeline disponibles (deben coincidir con el backend) */
export const PIPELINE_TEMPLATES = [
  'CI/CD Standard',
  'Quick Test',
  'Full Deploy',
]

/** Trigger types disponibles */
export const TRIGGER_TYPES = ['manual', 'push', 'schedule']

/** Paginación por defecto */
export const DEFAULT_PER_PAGE = 10
