# Especificación: Frontend UI

**Versión:** 1.0  
**Estado:** Draft  
**Modelos:** Ver `shared-contracts.spec.md`  
**API:** Ver `backend-api.spec.md`

---

## Fase 4 — Componentes base y navegación

### 4.1 Routing

| Ruta | Componente | Descripción |
|------|-----------|-------------|
| `/` | Dashboard | Vista principal con resumen |
| `/pipelines` | PipelineList | Lista de pipelines con filtros |
| `/pipelines/:id` | PipelineDetail | Detalle con stages y logs |

### 4.2 Layout general

```
┌──────────────────────────────────────────┐
│  🔵 Pipeline Dashboard     [Dashboard]  │
│                             [Pipelines]  │
├──────────────────────────────────────────┤
│                                          │
│            Contenido de la ruta          │
│                                          │
└──────────────────────────────────────────┘
```

- Header fijo con nombre de la app y navegación
- Navegación: links a Dashboard y Pipelines
- El link activo se resalta visualmente
- Layout responsive (mobile-friendly no es prioridad, pero no debe romperse)

### 4.3 Componente: PipelineList

**Ubicación:** `/pipelines`

**Comportamiento:**
1. Al montar, fetch GET /api/pipelines
2. Mostrar cada pipeline como PipelineCard
3. Botón "New Pipeline" en la parte superior
4. Filtros en la parte superior (debajo del botón)

**Filtros:**
- Dropdown de status: All, Pending, Running, Success, Failed, Cancelled
- Input de texto para repository
- Los filtros hacen fetch con query params al cambiar

**Paginación:**
- Mostrar botones Previous / Next
- Mostrar "Page X of Y"
- Deshabilitados cuando no aplica

**Botón "New Pipeline":**
Al hacer clic, muestra un modal/formulario con:
- Input: name (requerido)
- Input: repository (requerido)
- Input: branch (requerido, default "main")
- Select: trigger_type (manual, push, schedule)
- Select: template (CI/CD Standard, Quick Test, Full Deploy)
- Botón "Create" → POST /api/pipelines
- Al crear exitosamente, cierra el modal y agrega el pipeline a la lista

**Vista:**
```
┌──────────────────────────────────────────┐
│ [+ New Pipeline]                         │
│                                          │
│ Status: [All ▼]  Repository: [________]  │
│                                          │
│ ┌────────────────────────────────────┐   │
│ │ 🟢 Deploy Web App    #12          │   │
│ │ org/web-app @ main                │   │
│ │ success • 45s • 2 min ago         │   │
│ └────────────────────────────────────┘   │
│ ┌────────────────────────────────────┐   │
│ │ 🔵 Run Tests          #11         │   │
│ │ org/api @ develop                  │   │
│ │ running • Stage 3/6 • Build       │   │
│ └────────────────────────────────────┘   │
│ ┌────────────────────────────────────┐   │
│ │ 🔴 Deploy Backend     #10         │   │
│ │ org/backend @ main                 │   │
│ │ failed • Stage 4/6 • Unit Tests   │   │
│ └────────────────────────────────────┘   │
│                                          │
│        [← Previous]  Page 1 of 5  [Next →]│
└──────────────────────────────────────────┘
```

### 4.4 Componente: PipelineCard

Tarjeta individual de un pipeline en la lista.

**Props:** `{ pipeline }` (PipelineResponse)

**Muestra:**
- StatusBadge con color según status
- Nombre del pipeline + ID (#12)
- Repository @ branch
- Status text + duración (si terminó) + tiempo relativo ("2 min ago")
- Si running: mostrar stage actual ("Stage 3/6 • Build")
- Click en la tarjeta → navegar a `/pipelines/{id}`

### 4.5 Componente: StatusBadge

Badge reutilizable que muestra el status con color.

**Props:** `{ status }`

**Comportamiento:**
- Muestra texto del status capitalizado
- Color de fondo según la tabla de colores en shared-contracts
- Si status es `running`: agregar animación de pulso CSS

### 4.6 Componente: PipelineDetail

**Ubicación:** `/pipelines/:id`

**Comportamiento:**
1. Al montar, fetch GET /api/pipelines/{id}
2. Mostrar info del pipeline en el header
3. Mostrar lista de stages como StageProgress
4. Botones de acción según status

**Acciones por status:**
| Pipeline status | Acciones disponibles |
|----------------|---------------------|
| pending | Cancel |
| running | Cancel |
| success | Delete |
| failed | Retry, Delete |
| cancelled | Retry, Delete |

**Vista:**
```
┌──────────────────────────────────────────────┐
│ ← Back to Pipelines                          │
│                                               │
│ Deploy Web App #12              [Cancel]      │
│ org/web-app @ main                            │
│ Triggered: manual • Started: 10:30 AM         │
│                                               │
│ ┌───────────────────────────────────────────┐ │
│ │ ✅ 1. Checkout                    3s      │ │
│ │ ████████████████████████████████ 100%     │ │
│ ├───────────────────────────────────────────┤ │
│ │ ✅ 2. Install Dependencies       12s      │ │
│ │ ████████████████████████████████ 100%     │ │
│ ├───────────────────────────────────────────┤ │
│ │ 🔵 3. Build                      running  │ │
│ │ ████████████████░░░░░░░░░░░░░░░  55%     │ │
│ ├───────────────────────────────────────────┤ │
│ │ ⏳ 4. Deploy                     pending  │ │
│ │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%      │ │
│ └───────────────────────────────────────────┘ │
│                                               │
│ 📋 Logs: Build                                │
│ ┌───────────────────────────────────────────┐ │
│ │ 10:30:15 [INFO] Compiling TypeScript...   │ │
│ │ 10:30:18 [INFO] Bundling with webpack...  │ │
│ │ 10:30:22 [INFO] Build output: 2.4MB      │ │
│ └───────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

### 4.7 Componente: StageProgress

Muestra una barra de progreso para un stage individual.

**Props:** `{ stage }`

**Comportamiento:**
- Muestra: icono de status + orden + nombre + duración/status text
- Barra de progreso:
  - `pending`: 0%, gris
  - `running`: animación de progreso indeterminado (barberpole), color azul
  - `success`: 100%, verde
  - `failed`: porcentaje donde falló, rojo
- Click en un stage → cargar y mostrar sus logs en LogViewer

### 4.8 Componente: LogViewer

Muestra los logs de un stage seleccionado.

**Props:** `{ pipelineId, stageId }`

**Comportamiento:**
1. Cuando cambia stageId, fetch GET /api/pipelines/{pipelineId}/stages/{stageId}/logs
2. Mostrar logs en formato monospace, estilo terminal
3. Cada línea: `{timestamp} [{level}] {message}`
4. Color por level: info = blanco/gris, warning = amarillo, error = rojo
5. Auto-scroll al fondo cuando llegan nuevos logs (via WebSocket)

**Criterios de aceptación Fase 4:**
- [ ] Navegación funciona entre las 3 rutas
- [ ] PipelineList muestra pipelines con PipelineCards
- [ ] Filtros de status y repository funcionan
- [ ] Paginación funciona
- [ ] Botón New Pipeline crea un pipeline via POST
- [ ] PipelineDetail muestra stages con StageProgress
- [ ] LogViewer muestra logs de un stage seleccionado
- [ ] Botones de acción (Cancel, Retry, Delete) funcionan
- [ ] StatusBadge muestra colores correctos

---

## Fase 5 — Tiempo real y Dashboard

### 5.1 Hook: useWebSocket

**Archivo:** `src/hooks/useWebSocket.js`

```javascript
function useWebSocket(url) {
  // Retorna:
  // - isConnected: boolean
  // - lastMessage: object (último mensaje parseado)
  // - error: string | null
}
```

**Comportamiento:**
1. Conectar al WebSocket al montar
2. Parsear mensajes JSON entrantes
3. Auto-reconectar si se desconecta (con backoff: 1s, 2s, 4s, max 30s)
4. Limpiar conexión al desmontar
5. Exponer estado de conexión

### 5.2 Hook: usePipelines (o Context)

**Archivo:** `src/context/PipelineContext.jsx`

Estado global que combina datos de REST y WebSocket:

1. Carga inicial via REST (GET /api/pipelines)
2. Escucha updates via WebSocket
3. Cuando llega un `pipeline_update`: actualizar el pipeline en el estado local
4. Cuando llega un `pipeline_completed`: actualizar status + refrescar dashboard
5. Cuando llega un `log_entry`: agregar al log del stage si está visible

### 5.3 Integración WebSocket en componentes

**PipelineList:**
- Cuando un pipeline cambia de status via WS, la tarjeta se actualiza sin recargar
- Si un pipeline pasa a `running`, el stage actual se muestra en la tarjeta
- Si un pipeline se completa, el status y duración se actualizan

**PipelineDetail:**
- Las barras de StageProgress se actualizan en tiempo real
- El stage `running` actual muestra la animación
- Los logs se agregan en tiempo real (auto-scroll)

**Indicador de conexión:**
- Mostrar un pequeño indicador en el header:
  - 🟢 "Connected" cuando WebSocket está conectado
  - 🔴 "Disconnected" cuando se pierde la conexión
  - 🟡 "Reconnecting..." durante el backoff

### 5.4 Componente: Dashboard

**Ubicación:** `/` (ruta raíz)

**Comportamiento:**
1. Al montar, fetch GET /api/dashboard
2. Mostrar cards de resumen
3. Mostrar lista de pipelines recientes
4. Refrescar automáticamente cuando llega un `pipeline_completed` via WS

**Vista:**
```
┌──────────────────────────────────────────────┐
│                  Dashboard                    │
│                                               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │
│  │  50  │ │   3  │ │  80% │ │ 2m   │        │
│  │Total │ │Active│ │Pass  │ │ Avg  │        │
│  └──────┘ └──────┘ └──────┘ └──────┘        │
│                                               │
│  Status Breakdown                             │
│  ████████████████████████░░░░░░░░ 80% success │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░  8% failed  │
│  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  6% running │
│                                               │
│  Recent Pipelines                             │
│  ┌────────────────────────────────────────┐   │
│  │ 🟢 Deploy Web App #12 — 45s ago       │   │
│  │ 🔵 Run Tests #11 — running            │   │
│  │ 🔴 Deploy Backend #10 — 2 min ago     │   │
│  │ 🟢 Quick Check #9 — 5 min ago         │   │
│  │ 🟢 Full Deploy #8 — 12 min ago        │   │
│  └────────────────────────────────────────┘   │
└───────────────────────────────────────────────┘
```

**Criterios de aceptación Fase 5:**
- [ ] WebSocket se conecta al cargar la app
- [ ] Indicador de conexión visible en el header
- [ ] PipelineList se actualiza en tiempo real sin recargar
- [ ] PipelineDetail actualiza stages en tiempo real
- [ ] Logs se agregan en tiempo real con auto-scroll
- [ ] Auto-reconexión funciona tras desconexión
- [ ] Dashboard muestra estadísticas correctas
- [ ] Dashboard se refresca al completarse un pipeline

---

## Fase 6 — Tests e integración

### Tests del frontend (vitest o manual)

**Dado que el frontend usa Vite, los tests se pueden hacer con vitest si quieres, o validación manual. La prioridad es la integración end-to-end.**

### Verificación de integración

1. Iniciar backend: `uvicorn app.main:app --reload`
2. Iniciar frontend: `npm run dev`
3. Abrir el dashboard en el browser
4. Crear un pipeline "CI/CD Standard"
5. Verificar que:
   - La lista muestra el pipeline nuevo
   - El detalle muestra los stages progresando en tiempo real
   - Los logs se actualizan mientras el stage ejecuta
   - Al completarse, el dashboard se refresca
   - Si falla un stage, el pipeline muestra como failed
6. Crear otro pipeline mientras el primero corre → ambos se ven en la lista
7. Cancelar un pipeline running → status cambia inmediatamente
8. Retry un pipeline failed → nuevo pipeline aparece en la lista

**Criterios de aceptación Fase 6:**
- [ ] Backend tests pasan (pytest)
- [ ] La integración frontend-backend funciona end-to-end
- [ ] Crear → ver progreso → completar fluye sin errores
- [ ] Múltiples pipelines simultáneos funcionan
- [ ] Cancel y Retry funcionan desde la UI
- [ ] WebSocket mantiene conexión estable durante 5+ minutos
- [ ] README.md documenta setup, arquitectura, y uso
