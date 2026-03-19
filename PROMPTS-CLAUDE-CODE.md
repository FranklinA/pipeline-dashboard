# Prompts para Claude Code — Proyecto 3

---

## Sesión 1: Backend (Fases 1-3)

```bash
cd pipeline-dashboard/backend
claude
```

### Fase 1 — Modelos + Simulador

#### Prompt 1.1: Modelos y DB
```
Lee CLAUDE.md, specs/shared-contracts.spec.md, y la Fase 1 de specs/backend-api.spec.md.
Implementa:
1. database.py con engine async SQLite
2. models.py con Pipeline, Stage, LogEntry
3. schemas.py con Pydantic schemas según shared-contracts
4. main.py con FastAPI app y lifespan que crea la DB

NO implementes endpoints ni el simulador aún.
```

#### Prompt 1.2: Simulador
```
Lee la sección 1.2 (Simulador) de specs/backend-api.spec.md y los templates
de pipeline en specs/shared-contracts.spec.md.

Implementa app/simulator.py con:
- Los 3 templates de pipeline como constantes
- La función simulate_pipeline() según la spec
- Los mensajes de log simulados por stage
- El speed_multiplier para tests

Implementa app/websocket_manager.py con la clase WebSocketManager
(connect, disconnect, broadcast). Por ahora broadcast solo imprime en consola.
```

#### Prompt 1.3: Tests del simulador
```
Crea tests para el simulador en tests/test_simulator.py.
Usa speed_multiplier=100 para que los tests corran rápido.
Verifica:
- Los stages se ejecutan en orden
- Los estados cambian correctamente
- Se generan logs por cada stage
- Un pipeline puede terminar en success o failed
Ejecuta los tests.
```

### Fase 2 — API REST

#### Prompt 2.1: Endpoints CRUD
```
Lee la Fase 2 de specs/backend-api.spec.md.
Implementa TODOS los endpoints:
- POST /api/pipelines (crea + dispara simulación en background)
- GET /api/pipelines (con paginación y filtros)
- GET /api/pipelines/{id}
- POST /api/pipelines/{id}/cancel
- POST /api/pipelines/{id}/retry
- DELETE /api/pipelines/{id}
- GET /api/pipelines/{id}/stages/{stage_id}/logs
- GET /api/dashboard

Los responses deben coincidir EXACTAMENTE con shared-contracts.spec.md.
```

#### Prompt 2.2: Verificar API
```
Inicia el servidor y prueba estos escenarios en secuencia:

1. POST /api/pipelines con template "Quick Test"
2. Inmediatamente GET /api/pipelines/1 → debe estar pending o running
3. Espera 15 segundos, GET /api/pipelines/1 → verificar progreso
4. POST otro pipeline con template "CI/CD Standard"
5. GET /api/pipelines → deben aparecer ambos
6. GET /api/pipelines?status=running → filtrar
7. POST /api/pipelines/2/cancel → cancelar el segundo
8. GET /api/pipelines/2 → verificar cancelled
9. POST /api/pipelines/2/retry → crear retry
10. GET /api/dashboard → verificar estadísticas

Muéstrame el status code y body relevante de cada paso.
```

#### Prompt 2.3: Tests API
```
Crea tests para todos los endpoints en tests/test_pipelines.py y tests/test_dashboard.py.
Usa AsyncClient con base de datos en memoria.
Para los tests que involucran simulación, usa speed_multiplier alto.
Ejecuta todos los tests.
```

### Fase 3 — WebSocket

#### Prompt 3.1: Implementar WebSocket
```
Lee la Fase 3 de specs/backend-api.spec.md y los formatos de WebSocket
en specs/shared-contracts.spec.md.

Actualiza:
1. websocket_manager.py — implementar broadcast real a clientes conectados
2. main.py — agregar endpoint ws://localhost:8000/ws/pipelines
3. simulator.py — enviar mensajes WS al cambiar stages y generar logs

Los mensajes WS deben seguir EXACTAMENTE los formatos de shared-contracts.
```

#### Prompt 3.2: Verificar WebSocket
```
Inicia el servidor. Necesito verificar el WebSocket.
Crea un script simple test_ws_client.py que:
1. Conecta al WebSocket ws://localhost:8000/ws/pipelines
2. Imprime cada mensaje que recibe
3. Se desconecta después de 60 segundos

Luego en otra terminal crea un pipeline y observa los mensajes.
```

#### Prompt 3.3: CORS
```
Configura CORS en main.py para permitir:
- Origins: http://localhost:5173 (Vite dev server)
- Methods: GET, POST, PUT, DELETE
- Headers: Content-Type
```

---

## Sesión 2: Frontend (Fases 4-5)

```bash
cd pipeline-dashboard/frontend
claude
```

#### Prompt previo: Setup Vite + React
```
Lee CLAUDE.md (la sección de estructura del frontend).
Inicializa un proyecto React con Vite:
- npm create vite@latest . -- --template react
- Instala react-router-dom
- Configura el proxy en vite.config.js para que /api y /ws apunten a localhost:8000
- Crea la estructura de carpetas según CLAUDE.md
- Crea las variables CSS en index.css con los colores de shared-contracts
```

### Fase 4 — Componentes base

#### Prompt 4.1: Layout y routing
```
Lee la Fase 4 de specs/frontend-ui.spec.md.
Implementa:
1. App.jsx con React Router (3 rutas: /, /pipelines, /pipelines/:id)
2. Header con navegación y link activo
3. Componente StatusBadge reutilizable
4. utils/constants.js con colores y estados
5. utils/api.js con funciones fetch para cada endpoint

No implementes los componentes principales aún, solo placeholders.
```

#### Prompt 4.2: PipelineList + PipelineCard
```
Lee la sección 4.3 y 4.4 de specs/frontend-ui.spec.md.
Implementa PipelineList y PipelineCard:
- Fetch de pipelines al montar
- Filtros de status (dropdown) y repository (input)
- Paginación con Previous/Next
- Modal para crear nuevo pipeline
- PipelineCard con toda la info descrita en la spec
- Click en card navega a /pipelines/:id
```

#### Prompt 4.3: PipelineDetail + StageProgress + LogViewer
```
Lee las secciones 4.6, 4.7, y 4.8 de specs/frontend-ui.spec.md.
Implementa:
- PipelineDetail con header, stages, y botones de acción
- StageProgress con barras de progreso y colores por estado
- LogViewer con estilo terminal y colores por level
- Click en un stage carga sus logs
- Botones Cancel, Retry, Delete funcionando
```

#### Prompt 4.4: Verificar Fase 4
```
Asegúrate de que el backend esté corriendo en puerto 8000.
Verifica en el browser:
1. / muestra placeholder de Dashboard
2. /pipelines muestra la lista (puede estar vacía)
3. Crear un pipeline desde el botón New Pipeline
4. Ver que aparece en la lista
5. Click en la tarjeta → ver detalle con stages
6. Click en un stage → ver logs
7. Botones Cancel/Retry/Delete funcionan

Lista cualquier problema encontrado.
```

### Fase 5 — Tiempo real + Dashboard

#### Prompt 5.1: WebSocket hooks
```
Lee la sección 5.1 y 5.2 de specs/frontend-ui.spec.md.
Implementa:
1. hooks/useWebSocket.js con auto-reconexión y backoff
2. context/PipelineContext.jsx que combina REST + WebSocket
3. Indicador de conexión en el header (verde/rojo/amarillo)
```

#### Prompt 5.2: Integración tiempo real
```
Lee la sección 5.3 de specs/frontend-ui.spec.md.
Integra el WebSocket en los componentes:
1. PipelineList se actualiza cuando llega pipeline_update
2. PipelineDetail actualiza stages en tiempo real
3. LogViewer agrega logs en tiempo real con auto-scroll
```

#### Prompt 5.3: Dashboard
```
Lee la sección 5.4 de specs/frontend-ui.spec.md.
Implementa el componente Dashboard:
- Fetch de GET /api/dashboard
- Cards de resumen (total, activos, % éxito, duración promedio)
- Barra de status breakdown
- Lista de pipelines recientes
- Refresca automáticamente cuando llega pipeline_completed via WS
```

---

## Sesión 3: Integración (Fase 6)

#### Prompt 6.1: Test end-to-end
```
Lee la Fase 6 de specs/frontend-ui.spec.md.
Con backend y frontend corriendo, ejecuta estos escenarios
y verifica cada punto:

1. Crear un pipeline "CI/CD Standard" desde la UI
2. Verificar que la lista lo muestra con status actualizado
3. Ir al detalle y ver stages progresando en tiempo real
4. Ver logs actualizándose en tiempo real
5. Crear OTRO pipeline mientras el primero corre
6. Cancelar el segundo pipeline
7. Retry el pipeline cancelado
8. Esperar a que alguno complete y verificar el Dashboard

Lista todos los problemas encontrados.
```

#### Prompt 6.2: README
```
Genera README.md en la raíz del proyecto con:
- Descripción y arquitectura del proyecto
- Screenshots de las vistas principales (descripción si no puedes generar images)
- Setup (backend + frontend)
- API endpoints con ejemplos curl
- Estructura del proyecto
- Cómo funciona la simulación
- Formato de mensajes WebSocket
```

---

## 🔑 Tips para Proyecto 3

- **Si el frontend muestra datos diferentes a lo que esperas**, revisa shared-contracts.spec.md.
  El problema casi siempre es que el contrato no fue suficientemente específico.

- **El WebSocket es donde más bugs vas a encontrar.** Típicamente:
  desconexiones no manejadas, mensajes que llegan antes de que el componente
  esté listo, o el estado se desincroniza. Refina la spec del WebSocket
  cada vez que encuentres uno de estos.

- **Trabaja en sesiones separadas (backend vs frontend)**. Eso te fuerza a
  depender de la spec compartida, no de mirar el código del otro lado.
