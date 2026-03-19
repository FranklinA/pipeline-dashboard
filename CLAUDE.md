# CLAUDE.md — Pipeline Dashboard

## Descripción del proyecto

Aplicación full-stack que muestra el estado de pipelines CI/CD en tiempo real.
El backend simula la ejecución de pipelines (build → test → deploy) y notifica
al frontend vía WebSocket cuando hay cambios. El frontend muestra una lista
de pipelines, su progreso por etapas, logs, y un dashboard resumen.

## Stack tecnológico

### Backend
- Lenguaje: Python 3.11+
- Framework: FastAPI
- ORM: SQLAlchemy 2.0 (async)
- Base de datos: SQLite (vía aiosqlite)
- WebSocket: FastAPI WebSocket nativo
- Background tasks: asyncio (tareas en segundo plano)
- Testing: pytest + pytest-asyncio + httpx

### Frontend
- Framework: React 18
- Build tool: Vite
- Lenguaje: JavaScript (JSX)
- Estilos: CSS Modules (un .module.css por componente)
- HTTP client: fetch nativo
- WebSocket: WebSocket nativo del browser
- Estado: React hooks (useState, useEffect, useReducer, useContext)
- Routing: React Router v6

### Comunicación
- REST para CRUD y queries
- WebSocket para updates en tiempo real
- JSON como formato de intercambio

## Estructura del proyecto

```
pipeline-dashboard/
├── CLAUDE.md
├── specs/
│   ├── shared-contracts.spec.md       # Modelos compartidos (backend + frontend)
│   ├── backend-api.spec.md            # Endpoints REST + WebSocket
│   └── frontend-ui.spec.md            # Componentes React y comportamiento
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app, lifespan, CORS, WS
│   │   ├── database.py                # Engine, session, init_db
│   │   ├── models.py                  # SQLAlchemy models
│   │   ├── schemas.py                 # Pydantic schemas
│   │   ├── simulator.py               # Simulador de ejecución de pipelines
│   │   ├── websocket_manager.py       # Manejo de conexiones WebSocket
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── pipelines.py           # /api/pipelines
│   │   │   └── dashboard.py           # /api/dashboard
│   │   └── dependencies.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_pipelines.py
│   │   ├── test_simulator.py
│   │   └── test_dashboard.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx                   # Entry point
│       ├── App.jsx                    # Router principal
│       ├── App.module.css
│       ├── hooks/
│       │   ├── useWebSocket.js        # Hook para conexión WebSocket
│       │   └── usePipelines.js        # Hook para estado de pipelines
│       ├── context/
│       │   └── PipelineContext.jsx     # Context global de pipelines
│       ├── components/
│       │   ├── PipelineList.jsx        # Lista de pipelines
│       │   ├── PipelineList.module.css
│       │   ├── PipelineCard.jsx        # Tarjeta individual
│       │   ├── PipelineCard.module.css
│       │   ├── PipelineDetail.jsx      # Vista detalle con stages
│       │   ├── PipelineDetail.module.css
│       │   ├── StageProgress.jsx       # Barra de progreso por stage
│       │   ├── StageProgress.module.css
│       │   ├── LogViewer.jsx           # Visor de logs
│       │   ├── LogViewer.module.css
│       │   ├── Dashboard.jsx           # Dashboard resumen
│       │   ├── Dashboard.module.css
│       │   ├── StatusBadge.jsx         # Badge de estado reutilizable
│       │   └── StatusBadge.module.css
│       └── utils/
│           ├── api.js                  # Funciones fetch al backend
│           └── constants.js            # Colores, estados, config
└── README.md
```

## Convenciones de código

### Backend (Python)
- Mismas convenciones del Proyecto 2
- Type hints en todas las funciones
- Async/await para todo
- Docstrings en español

### Frontend (React)
- Componentes funcionales con hooks (no clases)
- Un archivo JSX + un archivo CSS Module por componente
- Props destructuradas en la firma de la función
- Nombres de componentes en PascalCase
- Nombres de hooks en camelCase con prefijo "use"
- Nombres de funciones handler con prefijo "handle" (handleClick, handleSubmit)
- No usar CSS global excepto en index.css para reset/variables
- Variables CSS custom para colores y spacing en :root

### Compartido
- Todos los campos de fecha en ISO 8601 con Z (UTC)
- IDs como integers
- Status/state como strings lowercase

## Reglas de implementación

1. **Spec-first**: No implementes nada fuera de la spec.
2. **Contratos compartidos primero**: Siempre referir a shared-contracts.spec.md para modelos.
3. **Backend antes que frontend**: El backend debe funcionar completo con tests antes de tocar el frontend.
4. **Sin dependencias innecesarias**: No instalar axios, styled-components, Material UI, etc.
5. **WebSocket simple**: No usar socket.io — usar WebSocket nativo en ambos lados.
6. **Simulador determinista en tests**: El simulador debe poder ejecutarse con tiempos fijos para testing.

## Comandos del proyecto

```bash
# ── Backend ──
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest tests/ -v

# ── Frontend ──
cd frontend
npm install
npm run dev          # Inicia en http://localhost:5173

# ── Ambos (en terminales separadas) ──
# Terminal 1: cd backend && uvicorn app.main:app --reload --port 8000
# Terminal 2: cd frontend && npm run dev
```

## Puertos

- Backend: `http://localhost:8000`
- Frontend dev: `http://localhost:5173`
- WebSocket: `ws://localhost:8000/ws/pipelines`
