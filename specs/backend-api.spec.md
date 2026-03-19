# Especificación: Backend API

**Versión:** 1.0  
**Estado:** Draft  
**Base URL:** `http://localhost:8000`  
**Modelos:** Ver `shared-contracts.spec.md`

---

## Fase 1 — Modelos, DB, y simulador de pipelines

### 1.1 Modelos y base de datos

Implementar los modelos SQLAlchemy según `shared-contracts.spec.md`:
- Pipeline, Stage, LogEntry
- Relaciones 1:N con CASCADE
- Base de datos SQLite async

### 1.2 Simulador de pipelines

El simulador es una función async que simula la ejecución de un pipeline.
NO ejecuta código real — solo cambia estados y genera logs con delays.

**Archivo:** `app/simulator.py`

**Función principal:**
```python
async def simulate_pipeline(
    pipeline_id: int,
    db_session_factory,
    ws_manager,
    speed_multiplier: float = 1.0
) -> None:
```

**Comportamiento del simulador:**

1. Cambiar pipeline.status a `running`, setear `started_at`
2. Para cada stage en orden:
   a. Cambiar stage.status a `running`, setear `started_at`
   b. Enviar WebSocket message `pipeline_update`
   c. Generar logs simulados durante la ejecución:
      - Log al inicio: `"Starting {stage.name}..."`
      - 1-3 logs durante la ejecución con mensajes realistas
      - Log al final: `"{stage.name} completed"` o `"{stage.name} failed"`
   d. Esperar un tiempo aleatorio dentro del `simulated_duration_range` del template
      (dividido por `speed_multiplier` para tests)
   e. Decidir si el stage tiene éxito o falla:
      - **Probabilidad de fallo: 10%** (configurable)
      - Si falla: stage.status = `failed`, pipeline.status = `failed`, DETENER
      - Si éxito: stage.status = `success`, siguiente stage
   f. Enviar WebSocket message `pipeline_update`
3. Si todos los stages completaron: pipeline.status = `success`
4. Setear `finished_at` y `duration_seconds` en pipeline
5. Enviar WebSocket message `pipeline_completed`

**Mensajes de log simulados por stage:**

```python
SIMULATED_LOGS = {
    "Checkout": [
        "Cloning repository...",
        "Fetching branch {branch}...",
        "Checkout complete. HEAD at {commit_hash}"
    ],
    "Install Dependencies": [
        "Reading package.json...",
        "Installing 142 packages...",
        "Dependencies installed successfully"
    ],
    "Lint": [
        "Running ESLint on 85 files...",
        "No linting errors found"
    ],
    "Unit Tests": [
        "Discovering test suites...",
        "Running 234 tests across 12 suites...",
        "All tests passed (234/234)"
    ],
    "Build": [
        "Compiling TypeScript...",
        "Bundling with webpack...",
        "Build output: 2.4MB (gzipped: 680KB)"
    ],
    "Deploy": [
        "Connecting to cluster...",
        "Applying Kubernetes manifests...",
        "Deployment rolled out successfully"
    ]
}
```

(Para stages no listados, usar logs genéricos: "Starting...", "Processing...", "Done.")

**Criterios de aceptación Fase 1:**
- [ ] Modelos se crean correctamente en la DB
- [ ] Simulador ejecuta stages secuencialmente
- [ ] Simulador genera logs por cada stage
- [ ] Simulador respeta probabilidad de fallo (10%)
- [ ] `speed_multiplier` acelera la simulación para tests
- [ ] Tests para el simulador con tiempos acelerados

---

## Fase 2 — API REST

### Endpoints

#### POST /api/pipelines

Crea un pipeline y dispara la simulación en background.

**Request:**
```json
{
  "name": "Deploy Web App",
  "repository": "org/web-app",
  "branch": "main",
  "trigger_type": "manual",
  "template": "CI/CD Standard"
}
```

**`template`** debe ser uno de: `"CI/CD Standard"`, `"Quick Test"`, `"Full Deploy"`

**Comportamiento:**
1. Crear el pipeline con status `pending`
2. Crear los stages según el template elegido, todos en status `pending`
3. Disparar `simulate_pipeline()` como background task
4. Retornar inmediatamente el pipeline creado (con status `pending`)

**Response: 201 Created**
```json
{
  "id": 1,
  "name": "Deploy Web App",
  "repository": "org/web-app",
  "branch": "main",
  "trigger_type": "manual",
  "status": "pending",
  "started_at": null,
  "finished_at": null,
  "duration_seconds": null,
  "created_at": "2026-03-17T10:30:00Z",
  "stages": [
    { "id": 1, "name": "Checkout", "order": 1, "status": "pending", ... },
    { "id": 2, "name": "Install Dependencies", "order": 2, "status": "pending", ... },
    ...
  ]
}
```

**Errores:**
| Caso | Status | code |
|------|--------|------|
| template inválido | 422 | INVALID_FIELD_VALUE |
| campos requeridos faltantes | 422 | MISSING_REQUIRED_FIELD |

---

#### GET /api/pipelines

Lista pipelines con paginación y filtros.

**Query parameters:**
| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| page | integer | 1 | Página |
| per_page | integer | 10 | Items por página (max 100) |
| status | string | — | Filtrar por status |
| repository | string | — | Filtrar por repositorio (match exacto) |
| branch | string | — | Filtrar por branch |
| sort_by | string | created_at | `created_at`, `started_at`, `name` |
| sort_order | string | desc | `asc` o `desc` |

**Response: 200 OK** → `PipelineListResponse` (ver shared-contracts)

---

#### GET /api/pipelines/{id}

Obtiene un pipeline con todos sus stages y detalle completo.

**Response: 200 OK** → `PipelineResponse` (ver shared-contracts)

**Errores:**
| Caso | Status | code |
|------|--------|------|
| ID no existe | 404 | RESOURCE_NOT_FOUND |

---

#### POST /api/pipelines/{id}/cancel

Cancela un pipeline en ejecución.

**Request:** Sin body

**Comportamiento:**
1. Si pipeline.status es `running` o `pending`: cambiar a `cancelled`, setear `finished_at`
2. Si pipeline.status es `success`, `failed`, o `cancelled`: error 409

**Response: 200 OK** → PipelineResponse actualizado

**Errores:**
| Caso | Status | code |
|------|--------|------|
| ID no existe | 404 | RESOURCE_NOT_FOUND |
| Ya terminó | 409 | INVALID_STATE_TRANSITION |

---

#### POST /api/pipelines/{id}/retry

Re-ejecuta un pipeline fallido o cancelado.

**Request:** Sin body

**Comportamiento:**
1. Si pipeline.status es `failed` o `cancelled`:
   - Crear un NUEVO pipeline con los mismos datos (name, repo, branch, template)
   - El pipeline original no se modifica
   - Retornar el nuevo pipeline
2. Si pipeline.status es `pending`, `running`, o `success`: error 409

**Response: 201 Created** → PipelineResponse del nuevo pipeline

**Errores:**
| Caso | Status | code |
|------|--------|------|
| ID no existe | 404 | RESOURCE_NOT_FOUND |
| No se puede re-ejecutar | 409 | INVALID_STATE_TRANSITION |

---

#### DELETE /api/pipelines/{id}

Elimina un pipeline.

**Comportamiento:**
- Solo permite eliminar pipelines con status `success`, `failed`, o `cancelled`
- No se puede eliminar un pipeline `running` o `pending`

**Response: 204 No Content**

**Errores:**
| Caso | Status | code |
|------|--------|------|
| ID no existe | 404 | RESOURCE_NOT_FOUND |
| Pipeline activo | 409 | INVALID_STATE_TRANSITION |

---

#### GET /api/pipelines/{id}/stages/{stage_id}/logs

Obtiene los logs de un stage específico.

**Response: 200 OK**
```json
{
  "stage_id": 2,
  "stage_name": "Build",
  "logs": [
    {
      "id": 1,
      "timestamp": "2026-03-17T10:30:03Z",
      "level": "info",
      "message": "Compiling TypeScript..."
    },
    {
      "id": 2,
      "timestamp": "2026-03-17T10:30:08Z",
      "level": "info",
      "message": "Bundling with webpack..."
    }
  ]
}
```

**Errores:**
| Caso | Status | code |
|------|--------|------|
| Pipeline no existe | 404 | RESOURCE_NOT_FOUND |
| Stage no existe | 404 | RESOURCE_NOT_FOUND |
| Stage no pertenece al pipeline | 404 | RESOURCE_NOT_FOUND |

---

#### GET /api/dashboard

Retorna estadísticas del dashboard.

**Response: 200 OK** → `DashboardResponse` (ver shared-contracts)

**Cálculos:**
- `total_pipelines`: COUNT total
- `by_status`: COUNT agrupado por status
- `recent_pipelines`: últimos 5 por created_at DESC
- `avg_duration_seconds`: promedio de duration_seconds donde status = success
- `success_rate_percent`: (success / total finalizados) * 100, redondeado a 1 decimal

**Criterios de aceptación Fase 2:**
- [ ] POST crea pipeline + stages y retorna inmediatamente
- [ ] La simulación corre en background (el POST no bloquea)
- [ ] GET lista con paginación y filtros
- [ ] GET /{id} devuelve pipeline con stages
- [ ] Cancel funciona solo en running/pending
- [ ] Retry crea nuevo pipeline
- [ ] Delete solo en pipelines terminados
- [ ] Logs se obtienen por stage
- [ ] Dashboard calcula estadísticas correctamente
- [ ] Tests para cada endpoint

---

## Fase 3 — WebSocket

### Endpoint: ws://localhost:8000/ws/pipelines

**Conexión:**
El frontend abre UNA conexión WebSocket que recibe updates de TODOS los pipelines activos.

**Archivo:** `app/websocket_manager.py`

```python
class WebSocketManager:
    """Gestiona conexiones WebSocket activas."""

    async def connect(self, websocket: WebSocket) -> None:
        """Acepta y registra una nueva conexión."""

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remueve una conexión desconectada."""

    async def broadcast(self, message: dict) -> None:
        """Envía un mensaje JSON a TODOS los clientes conectados."""
```

**Mensajes que el servidor envía (ver formatos en shared-contracts):**
1. `pipeline_update` → cuando un stage cambia de estado
2. `pipeline_completed` → cuando el pipeline termina (success o failed)
3. `log_entry` → cuando se genera una nueva línea de log

**Mensajes que el cliente envía:**
Ninguno. La conexión es unidireccional (server → client).

**Manejo de desconexión:**
- Si un cliente se desconecta, removerlo silenciosamente
- No afectar la simulación — los pipelines siguen ejecutándose aunque nadie mire

**Criterios de aceptación Fase 3:**
- [ ] El WebSocket acepta conexiones en /ws/pipelines
- [ ] El simulador envía pipeline_update al cambiar cada stage
- [ ] El simulador envía pipeline_completed al terminar
- [ ] El simulador envía log_entry por cada log generado
- [ ] Desconexiones no causan errores en el servidor
- [ ] Múltiples clientes reciben los mismos broadcasts
- [ ] Tests verifican que el WebSocket envía mensajes correctos
