"""FastAPI application principal con lifespan, CORS, routers y WebSocket."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.dependencies import ws_manager
from app.routers import dashboard, pipelines


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la aplicación."""
    await init_db()
    yield


app = FastAPI(
    title="Pipeline Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(pipelines.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health_check() -> dict:
    """Verifica que el servidor está activo."""
    return {"status": "ok"}


@app.websocket("/ws/pipelines")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Acepta conexiones WebSocket y envía updates de pipelines en tiempo real."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Mantener la conexión abierta; el servidor es el único que envía mensajes.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)
