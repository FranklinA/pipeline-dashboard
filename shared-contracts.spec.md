# Especificación: Contratos Compartidos

**Versión:** 1.0  
**Estado:** Draft  

**⚠️ ESTE ARCHIVO ES LA FUENTE DE VERDAD para los modelos de datos.
Tanto el backend como el frontend DEBEN respetar estos contratos exactamente.
Si necesitas cambiar un campo, cámbialo AQUÍ PRIMERO y luego actualiza ambos lados.**

---

## 1. Modelo: Pipeline

Representa un pipeline CI/CD (ej: "Deploy Web App to Production").

### Campos

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| id | integer | No | Autoincrement |
| name | string | No | Nombre descriptivo (ej: "Deploy Web App") |
| repository | string | No | Repo asociado (ej: "org/web-app") |
| branch | string | No | Branch (ej: "main", "develop") |
| trigger_type | string | No | Cómo se disparó: `manual`, `push`, `schedule` |
| status | string | No | Estado global del pipeline (ver sección estados) |
| started_at | datetime | Sí | Cuándo empezó la ejecución (null si pending) |
| finished_at | datetime | Sí | Cuándo terminó (null si no ha terminado) |
| duration_seconds | integer | Sí | Duración total en segundos (null si no ha terminado) |
| created_at | datetime | No | Cuándo se creó el registro |

---

## 2. Modelo: Stage

Representa una etapa dentro de un pipeline. Un pipeline tiene múltiples stages ordenados.

### Campos

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| id | integer | No | Autoincrement |
| pipeline_id | integer (FK) | No | Pipeline al que pertenece |
| name | string | No | Nombre del stage (ej: "Build", "Test", "Deploy") |
| order | integer | No | Posición en la secuencia (1, 2, 3...) |
| status | string | No | Estado del stage (ver sección estados) |
| started_at | datetime | Sí | Cuándo empezó |
| finished_at | datetime | Sí | Cuándo terminó |
| duration_seconds | integer | Sí | Duración en segundos |

### Relación
- Un Pipeline tiene muchos Stages (1:N)
- ON DELETE CASCADE — al eliminar pipeline se eliminan sus stages

---

## 3. Modelo: LogEntry

Representa una línea de log de un stage.

### Campos

| Campo | Tipo | Nullable | Descripción |
|-------|------|----------|-------------|
| id | integer | No | Autoincrement |
| stage_id | integer (FK) | No | Stage al que pertenece |
| timestamp | datetime | No | Momento del log |
| level | string | No | `info`, `warning`, `error` |
| message | string | No | Contenido del log |

### Relación
- Un Stage tiene muchos LogEntries (1:N)
- ON DELETE CASCADE

---

## 4. Diagrama de estados

### Pipeline status

```
                    ┌──────────┐
                    │ pending  │
                    └────┬─────┘
                         │ (primer stage inicia)
                    ┌────▼─────┐
              ┌─────│ running  │─────┐
              │     └────┬─────┘     │
              │          │           │
         (un stage  (todos los  (cancelado
          falla)     stages OK)  manualmente)
              │          │           │
        ┌─────▼──┐  ┌────▼────┐ ┌───▼──────┐
        │ failed │  │ success │ │ cancelled │
        └────────┘  └─────────┘ └──────────┘
```

**Valores válidos de Pipeline.status:**
`pending`, `running`, `success`, `failed`, `cancelled`

### Stage status

```
        ┌──────────┐
        │ pending  │
        └────┬─────┘
             │ (le toca ejecutar)
        ┌────▼─────┐
   ┌────│ running  │────┐
   │    └──────────┘    │
   │                    │
(falla)            (completa OK)
   │                    │
┌──▼─────┐      ┌──────▼───┐
│ failed │      │ success  │
└────────┘      └──────────┘
```

**Valores válidos de Stage.status:**
`pending`, `running`, `success`, `failed`

**Nota:** Cuando un stage falla, los stages posteriores permanecen en `pending`.
Cuando un pipeline se cancela, los stages `pending` y `running` quedan como están
(el frontend los muestra como "cancelados" por contexto del pipeline).

---

## 5. Templates de pipeline (para simulación)

El sistema incluye templates predefinidos que definen qué stages tiene cada tipo de pipeline:

### Template: "CI/CD Standard"
```json
{
  "name": "CI/CD Standard",
  "stages": [
    { "name": "Checkout", "order": 1, "simulated_duration_range": [2, 5] },
    { "name": "Install Dependencies", "order": 2, "simulated_duration_range": [5, 15] },
    { "name": "Lint", "order": 3, "simulated_duration_range": [3, 8] },
    { "name": "Unit Tests", "order": 4, "simulated_duration_range": [10, 30] },
    { "name": "Build", "order": 5, "simulated_duration_range": [8, 20] },
    { "name": "Deploy", "order": 6, "simulated_duration_range": [5, 15] }
  ]
}
```

### Template: "Quick Test"
```json
{
  "name": "Quick Test",
  "stages": [
    { "name": "Checkout", "order": 1, "simulated_duration_range": [1, 3] },
    { "name": "Test", "order": 2, "simulated_duration_range": [5, 10] }
  ]
}
```

### Template: "Full Deploy"
```json
{
  "name": "Full Deploy",
  "stages": [
    { "name": "Checkout", "order": 1, "simulated_duration_range": [2, 4] },
    { "name": "Install", "order": 2, "simulated_duration_range": [5, 12] },
    { "name": "Lint & Format", "order": 3, "simulated_duration_range": [3, 6] },
    { "name": "Unit Tests", "order": 4, "simulated_duration_range": [10, 25] },
    { "name": "Integration Tests", "order": 5, "simulated_duration_range": [15, 40] },
    { "name": "Build Docker Image", "order": 6, "simulated_duration_range": [10, 20] },
    { "name": "Push to Registry", "order": 7, "simulated_duration_range": [5, 10] },
    { "name": "Deploy to Staging", "order": 8, "simulated_duration_range": [8, 15] },
    { "name": "Smoke Tests", "order": 9, "simulated_duration_range": [5, 10] },
    { "name": "Deploy to Production", "order": 10, "simulated_duration_range": [8, 15] }
  ]
}
```

`simulated_duration_range` = [min_seconds, max_seconds] para la simulación.
Los stages se ejecutan **secuencialmente** (uno tras otro, no en paralelo).

---

## 6. Schemas JSON (contratos de response)

### PipelineResponse (lo que devuelve el API y consume el frontend)

```json
{
  "id": 1,
  "name": "Deploy Web App",
  "repository": "org/web-app",
  "branch": "main",
  "trigger_type": "manual",
  "status": "running",
  "started_at": "2026-03-17T10:30:00Z",
  "finished_at": null,
  "duration_seconds": null,
  "created_at": "2026-03-17T10:30:00Z",
  "stages": [
    {
      "id": 1,
      "name": "Checkout",
      "order": 1,
      "status": "success",
      "started_at": "2026-03-17T10:30:00Z",
      "finished_at": "2026-03-17T10:30:03Z",
      "duration_seconds": 3
    },
    {
      "id": 2,
      "name": "Build",
      "order": 2,
      "status": "running",
      "started_at": "2026-03-17T10:30:03Z",
      "finished_at": null,
      "duration_seconds": null
    },
    {
      "id": 3,
      "name": "Deploy",
      "order": 3,
      "status": "pending",
      "started_at": null,
      "finished_at": null,
      "duration_seconds": null
    }
  ]
}
```

### PipelineListResponse

```json
{
  "data": [ ...array de PipelineResponse... ],
  "pagination": {
    "total": 50,
    "page": 1,
    "per_page": 10,
    "total_pages": 5
  }
}
```

### DashboardResponse

```json
{
  "summary": {
    "total_pipelines": 50,
    "by_status": {
      "pending": 2,
      "running": 3,
      "success": 40,
      "failed": 4,
      "cancelled": 1
    }
  },
  "recent_pipelines": [ ...últimos 5 PipelineResponse... ],
  "avg_duration_seconds": 120,
  "success_rate_percent": 80.0
}
```

### WebSocket message (server → client)

```json
{
  "type": "pipeline_update",
  "pipeline_id": 1,
  "data": {
    "status": "running",
    "current_stage": {
      "id": 2,
      "name": "Build",
      "order": 2,
      "status": "running"
    },
    "stages_summary": [
      { "id": 1, "name": "Checkout", "order": 1, "status": "success" },
      { "id": 2, "name": "Build", "order": 2, "status": "running" },
      { "id": 3, "name": "Deploy", "order": 3, "status": "pending" }
    ]
  }
}
```

### WebSocket message: pipeline_completed

```json
{
  "type": "pipeline_completed",
  "pipeline_id": 1,
  "data": {
    "status": "success",
    "duration_seconds": 45,
    "finished_at": "2026-03-17T10:30:45Z"
  }
}
```

### WebSocket message: log_entry

```json
{
  "type": "log_entry",
  "pipeline_id": 1,
  "stage_id": 2,
  "data": {
    "timestamp": "2026-03-17T10:30:15Z",
    "level": "info",
    "message": "Building Docker image..."
  }
}
```

---

## 7. Colores por estado (usado en frontend)

| Status | Color | Uso |
|--------|-------|-----|
| pending | `#6B7280` (gray-500) | Todavía no inicia |
| running | `#3B82F6` (blue-500) | En ejecución (con animación) |
| success | `#10B981` (green-500) | Completado exitosamente |
| failed | `#EF4444` (red-500) | Falló |
| cancelled | `#F59E0B` (amber-500) | Cancelado manualmente |

Estos colores deben definirse como variables CSS en `:root` y usarse consistentemente.
