# Pipeline Dashboard

Aplicación full-stack que muestra el estado de pipelines CI/CD en tiempo real.
El backend simula la ejecución de pipelines (build → test → deploy) y notifica
al frontend vía WebSocket cuando hay cambios de estado o nuevos logs.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   React 18 + Vite                        │   │
│  │                                                          │   │
│  │  PipelineContext ──┬── PipelineList (lista + filtros)   │   │
│  │  (estado global)   ├── PipelineDetail (stages + logs)   │   │
│  │                    └── Dashboard (métricas)              │   │
│  │                                                          │   │
│  │  useWebSocket ─────── reconexión automática con backoff  │   │
│  └──────────────┬───────────────────────┬───────────────────┘   │
│                 │ REST (fetch)           │ WebSocket              │
└─────────────────┼───────────────────────┼─────────────────────────┘
                  │                       │
┌─────────────────┼───────────────────────┼─────────────────────────┐
│                 ▼       FastAPI          ▼                         │
│                                                                    │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐  │
│  │  REST Endpoints │    │  WebSocket /ws/pipelines             │  │
│  │                 │    │                                      │  │
│  │  /api/pipelines │    │  Broadcast a todos los clientes:     │  │
│  │  /api/dashboard │    │  - pipeline_update                   │  │
│  └────────┬────────┘    │  - pipeline_completed                │  │
│           │             │  - log_entry                         │  │
│           ▼             └──────────────┬─────────────────────┘  │
│  ┌─────────────────┐                   │                         │
│  │   SQLAlchemy    │◄──────────────────┘                         │
│  │   (async)       │        Simulator                            │
│  │   SQLite        │  asyncio background task por pipeline       │
│  └─────────────────┘                                             │
└────────────────────────────────────────────────────────────────────┘
```

### Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend framework | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy 2.0 async |
| Base de datos | SQLite + aiosqlite |
| WebSocket | FastAPI WebSocket nativo |
| Concurrencia | asyncio.create_task |
| Frontend framework | React 18 |
| Build tool | Vite |
| Routing | React Router v6 |
| Estilos | CSS Modules |
| HTTP client | fetch nativo |
| WebSocket client | WebSocket nativo del browser |
| Tests | pytest + pytest-asyncio + httpx (149 tests) |

---

## Vistas principales

### Dashboard (`/`)

```
┌──────────────────────────────────────────────────────────┐
│  Pipeline Dashboard          [Dashboard] [Pipelines]  [●Connected] │
├──────────────────────────────────────────────────────────┤
│                         Dashboard                         │
│                                                           │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │
│  │   17   │  │   2    │  │  41%   │  │  33s   │         │
│  │ Total  │  │ Active │  │  Pass  │  │  Avg   │         │
│  └────────┘  └────────┘  └────────┘  └────────┘         │
│                                                           │
│  Status Breakdown                                         │
│  pending   ░░░░░░░░░░░░░░░░░░░░░  0%  (0)               │
│  running   ██░░░░░░░░░░░░░░░░░░░ 12%  (2)               │
│  success   ████████░░░░░░░░░░░░░ 41%  (7)               │
│  failed    ████████░░░░░░░░░░░░░ 41%  (7)               │
│  cancelled ███░░░░░░░░░░░░░░░░░░ 18%  (3)               │
│                                                           │
│  Recent Pipelines                                         │
│  [Running ] Full Deploy Test #19         running          │
│  [Success ] Quick Test Concurrent #18    11s              │
│  [Cancelled] Quick Test Concurrent #17                    │
│  [Failed  ] Full Deploy Test #16         99s              │
│  [Failed  ] E2E CI/CD Test 2 #15         11s              │
└──────────────────────────────────────────────────────────┘
```

### Lista de Pipelines (`/pipelines`)

```
┌──────────────────────────────────────────────────────────┐
│  [+ New Pipeline]                                         │
│  Status: [All ▼]   Repository: [org/deploy_____________]  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐    │
│  │ [Running ] Full Deploy Test          #19         │    │
│  │ org/deploy @ main                               │    │
│  │ Stage 3/10 • Lint & Format                      │    │
│  └──────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐    │
│  │ [Failed  ] E2E CI/CD Test            #14         │    │
│  │ org/e2e @ main                                  │    │
│  │ failed • 2s • 45m ago                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                           │
│         [← Previous]  Page 1 of 2  [Next →]              │
└──────────────────────────────────────────────────────────┘
```

### Detalle de Pipeline (`/pipelines/:id`)

```
┌──────────────────────────────────────────────────────────┐
│  ← Back to Pipelines                                      │
│                                                           │
│  Full Deploy Test #16     [Failed]      [Retry] [Delete]  │
│  org/deploy @ main                                        │
│  Triggered: manual • Started: 02:26:50 • Duration: 99s   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │ ✅  1. Checkout              3s                    │  │
│  │     ████████████████████████████████ 100%          │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ ✅  5. Integration Tests     39s                   │  │
│  │     ████████████████████████████████ 100%          │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ ❌  6. Build Docker Image    13s    failed         │  │── click →│
│  │     ████████████░░░░░░░░░░░░░░░░ 50%              │           │
│  ├────────────────────────────────────────────────────┤           │
│  │ ⏳  7. Push to Registry      pending               │           │
│  │     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%              │           │
│  └────────────────────────────────────────────────────┘           │
│                                                                    │
│  Logs: Build Docker Image ◄───────────────────────────────────────┘
│  ┌────────────────────────────────────────────────────┐
│  │ 02:29:50 [INFO ] Building image org/deploy:main... │
│  │ 02:29:58 [INFO ] Compressing layers...             │
│  │ 02:30:03 [ERROR] Build Docker Image failed         │
│  └────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────┘
```

---

## Setup

### Requisitos

- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

El backend queda disponible en `http://localhost:8000`.
Documentación interactiva: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

El frontend queda disponible en `http://localhost:5173`.

> El proxy de Vite redirige `/api` → `http://localhost:8000` y `/ws` → `ws://localhost:8000`
> automáticamente durante el desarrollo. No se necesita configuración extra de CORS.

### Tests del backend

```bash
cd backend
pytest tests/ -v
# 149 tests passed
```

---

## API Endpoints

### Pipelines

#### Listar pipelines
```bash
GET /api/pipelines

# Con filtros y paginación:
curl "http://localhost:8000/api/pipelines?status=running&page=1&per_page=10"
curl "http://localhost:8000/api/pipelines?repository=org/web-app"
```

Parámetros de query:
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `status` | string | Filtrar por estado: `pending`, `running`, `success`, `failed`, `cancelled` |
| `repository` | string | Filtrar por repositorio (match exacto) |
| `page` | int | Página (default: 1) |
| `per_page` | int | Resultados por página (default: 10) |
| `sort` | string | Campo de orden (default: `created_at`) |
| `order` | string | `asc` o `desc` (default: `desc`) |

Respuesta:
```json
{
  "data": [
    {
      "id": 19,
      "name": "Full Deploy Test",
      "repository": "org/deploy",
      "branch": "main",
      "trigger_type": "manual",
      "status": "failed",
      "started_at": "2026-03-20T02:30:36Z",
      "finished_at": "2026-03-20T02:30:56Z",
      "duration_seconds": 20,
      "created_at": "2026-03-20T02:30:36Z",
      "stages": [
        {
          "id": 85,
          "name": "Checkout",
          "order": 1,
          "status": "success",
          "started_at": "2026-03-20T02:30:36Z",
          "finished_at": "2026-03-20T02:30:41Z",
          "duration_seconds": 4
        }
      ]
    }
  ],
  "pagination": {
    "total": 17,
    "page": 1,
    "per_page": 10,
    "total_pages": 2
  }
}
```

#### Crear pipeline
```bash
curl -X POST http://localhost:8000/api/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Deploy Web App",
    "repository": "org/web-app",
    "branch": "main",
    "trigger_type": "manual",
    "template": "CI/CD Standard"
  }'
```

Templates disponibles: `CI/CD Standard`, `Quick Test`, `Full Deploy`
Trigger types: `manual`, `push`, `schedule`

#### Obtener pipeline por ID
```bash
curl http://localhost:8000/api/pipelines/19
```

#### Cancelar pipeline
```bash
curl -X POST http://localhost:8000/api/pipelines/19/cancel
# Solo funciona si status es pending o running
# Devuelve 409 si el pipeline ya terminó
```

#### Reintentar pipeline
```bash
curl -X POST http://localhost:8000/api/pipelines/19/retry
# Solo funciona si status es failed o cancelled
# Crea un nuevo pipeline con el mismo nombre, repo, branch y template
# Devuelve el nuevo PipelineResponse
```

#### Eliminar pipeline
```bash
curl -X DELETE http://localhost:8000/api/pipelines/19
# Solo funciona si status es success, failed o cancelled
# Devuelve 204 No Content
```

#### Logs de un stage
```bash
curl http://localhost:8000/api/pipelines/19/stages/85/logs
```

Respuesta:
```json
{
  "stage_id": 85,
  "stage_name": "Checkout",
  "logs": [
    {
      "id": 1,
      "timestamp": "2026-03-20T02:30:36Z",
      "level": "info",
      "message": "Cloning repository..."
    },
    {
      "id": 2,
      "timestamp": "2026-03-20T02:30:38Z",
      "level": "error",
      "message": "Checkout failed"
    }
  ]
}
```

### Dashboard

```bash
curl http://localhost:8000/api/dashboard
```

Respuesta:
```json
{
  "summary": {
    "total_pipelines": 17,
    "by_status": {
      "pending": 0,
      "running": 0,
      "success": 7,
      "failed": 7,
      "cancelled": 3
    }
  },
  "recent_pipelines": [ "...últimos 5 PipelineResponse..." ],
  "avg_duration_seconds": 33.1,
  "success_rate_percent": 43.8
}
```

> `avg_duration_seconds` y `success_rate_percent` se calculan solo sobre pipelines terminados (`success` + `failed`).

---

## Estructura del proyecto

```
pipeline-dashboard/
├── README.md
├── CLAUDE.md                          # Instrucciones para el agente
├── specs/
│   ├── shared-contracts.spec.md       # Modelos de datos (fuente de verdad)
│   ├── backend-api.spec.md            # Spec de endpoints REST + WebSocket
│   └── frontend-ui.spec.md            # Spec de componentes React
│
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini                     # asyncio_mode = auto
│   ├── app/
│   │   ├── main.py                    # FastAPI app, lifespan, CORS, WS endpoint
│   │   ├── database.py                # Engine async, AsyncSessionLocal, init_db
│   │   ├── models.py                  # Pipeline, Stage, LogEntry (SQLAlchemy 2.0)
│   │   ├── schemas.py                 # Pydantic v2 schemas (fechas con Z UTC)
│   │   ├── simulator.py               # Simulador de ejecución de pipelines
│   │   ├── websocket_manager.py       # Broadcast a todos los clientes conectados
│   │   ├── dependencies.py            # Singleton ws_manager, get_ws_manager()
│   │   └── routers/
│   │       ├── pipelines.py           # /api/pipelines (CRUD + cancel/retry/logs)
│   │       └── dashboard.py           # /api/dashboard
│   └── tests/
│       ├── conftest.py                # Fixtures: db en memoria, insert_pipeline
│       ├── test_pipelines.py          # 108 tests de endpoints REST
│       ├── test_dashboard.py          # 34 tests de dashboard
│       ├── test_simulator.py          # 10 tests del simulador (speed_multiplier=100)
│       └── test_websocket.py          # 21 tests del WebSocket manager
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js                 # Proxy /api y /ws → localhost:8000
    └── src/
        ├── main.jsx                   # Entry point, Router, PipelineProvider
        ├── App.jsx                    # Layout: header + nav + WS indicator
        ├── App.module.css
        ├── index.css                  # Reset + variables CSS custom (:root)
        ├── context/
        │   └── PipelineContext.jsx    # Estado global: REST + WS combinados
        ├── hooks/
        │   ├── useWebSocket.js        # WS con backoff exponencial (1s→2s→4s→30s)
        │   └── usePipelines.js        # Acceso al PipelineContext
        ├── components/
        │   ├── Dashboard.jsx          # Métricas + breakdown + recientes
        │   ├── PipelineList.jsx       # Lista + filtros + paginación + modal crear
        │   ├── PipelineCard.jsx       # Tarjeta individual clickeable
        │   ├── PipelineDetail.jsx     # Detalle con stages + acciones
        │   ├── StageProgress.jsx      # Barra de progreso por stage
        │   ├── LogViewer.jsx          # Terminal de logs con auto-scroll
        │   └── StatusBadge.jsx        # Badge de color por estado
        └── utils/
            ├── api.js                 # fetch helpers para cada endpoint
            └── constants.js           # STATUS_COLORS, PIPELINE_TEMPLATES, etc.
```

---

## Cómo funciona la simulación

Al crear un pipeline, el backend lanza un `asyncio.create_task` que ejecuta `simulate_pipeline()` en segundo plano. El simulador no bloquea el servidor.

### Flujo de ejecución

```
POST /api/pipelines
  │
  ├─► Crea registro Pipeline en DB (status=pending)
  ├─► Crea registros Stage en DB (todos status=pending)
  └─► asyncio.create_task(simulate_pipeline(...))
           │
           ▼
      Para cada stage (en orden):
           │
           ├─► Pipeline status → running
           ├─► Stage status → running
           ├─► WS broadcast: pipeline_update
           │
           ├─► Espera duración aleatoria del rango del template
           │   (dividida en intervalos de 1s para emitir logs)
           │
           ├─► Cada ~1s: WS broadcast log_entry
           │
           ├─► ~20% probabilidad de fallo por stage
           │   ├─► Si falla: stage → failed, pipeline → failed, fin
           │   └─► Si ok: stage → success, siguiente stage
           │
           └─► Si todos OK: pipeline → success
                    │
                    └─► WS broadcast: pipeline_completed
```

### Templates

| Template | Stages | Duración total aprox. |
|----------|--------|----------------------|
| **Quick Test** | Checkout, Test | 6–13s |
| **CI/CD Standard** | Checkout, Install Dependencies, Lint, Unit Tests, Build, Deploy | 33–93s |
| **Full Deploy** | Checkout, Install, Lint & Format, Unit Tests, Integration Tests, Build Docker Image, Push to Registry, Deploy to Staging, Smoke Tests, Deploy to Production | 71–151s |

### `speed_multiplier`

El simulador acepta un parámetro `speed_multiplier` que divide todos los tiempos de espera:

```python
# Producción (default): tiempos reales
simulate_pipeline(pipeline_id, factory, ws_manager, speed_multiplier=1.0)

# Tests: 100x más rápido
simulate_pipeline(pipeline_id, factory, ws_manager, speed_multiplier=100.0)
```

Esto permite que los tests de integración corran en segundos en lugar de minutos, sin cambiar la lógica del simulador.

---

## Mensajes WebSocket

El servidor emite mensajes JSON unidireccionales (server → client) a todos los clientes conectados en `ws://localhost:8000/ws/pipelines`.

### Conexión

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/pipelines')
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)
  console.log(msg.type, msg)
}
```

### Tipos de mensaje

#### `pipeline_update`
Se emite cuando un stage cambia de estado (pending → running, running → success/failed).

```json
{
  "type": "pipeline_update",
  "pipeline_id": 16,
  "data": {
    "status": "running",
    "current_stage": {
      "id": 75,
      "name": "Integration Tests",
      "order": 5,
      "status": "running"
    },
    "stages_summary": [
      { "id": 71, "name": "Checkout",      "order": 1, "status": "success" },
      { "id": 72, "name": "Install",       "order": 2, "status": "success" },
      { "id": 73, "name": "Lint & Format", "order": 3, "status": "success" },
      { "id": 74, "name": "Unit Tests",    "order": 4, "status": "success" },
      { "id": 75, "name": "Integration Tests", "order": 5, "status": "running" },
      { "id": 76, "name": "Build Docker Image","order": 6, "status": "pending" }
    ]
  }
}
```

#### `pipeline_completed`
Se emite cuando el pipeline termina (`success`, `failed`, o `cancelled`).

```json
{
  "type": "pipeline_completed",
  "pipeline_id": 16,
  "data": {
    "status": "failed",
    "duration_seconds": 99,
    "finished_at": "2026-03-20T02:30:56Z"
  }
}
```

#### `log_entry`
Se emite cada vez que el simulador genera una línea de log durante la ejecución de un stage.

```json
{
  "type": "log_entry",
  "pipeline_id": 16,
  "stage_id": 75,
  "data": {
    "timestamp": "2026-03-20T02:28:59Z",
    "level": "info",
    "message": "Starting integration test suite..."
  }
}
```

Niveles de log posibles: `info`, `warning`, `error`

### Reconexión automática (frontend)

El hook `useWebSocket` implementa backoff exponencial:

```
Intento 1: espera 1s
Intento 2: espera 2s
Intento 3: espera 4s
Intento 4: espera 8s
Intento 5: espera 16s
Intento 6+: espera 30s (máximo)
```

El backoff se resetea a 1s cuando la conexión se restablece exitosamente.

---

## Estados y transiciones

### Pipeline

```
pending ──► running ──► success
                │
                ├──► failed
                └──► cancelled  (via POST /cancel)
```

`failed` y `cancelled` pueden volver a `pending` via `POST /retry` (crea un nuevo pipeline).

### Stage

```
pending ──► running ──► success
                └──► failed
```

Cuando un stage falla, los stages posteriores permanecen en `pending`.
Cuando un pipeline se cancela, el stage en `running` y los `pending` no cambian de estado.

---

## Colores de estado

| Estado | Color | Hex |
|--------|-------|-----|
| pending | Gris | `#6B7280` |
| running | Azul (con animación pulse) | `#3B82F6` |
| success | Verde | `#10B981` |
| failed | Rojo | `#EF4444` |
| cancelled | Ámbar | `#F59E0B` |

Definidos como variables CSS en `:root` (`--color-pending`, `--color-running`, etc.)
y reutilizados en todos los componentes.
