"""Gestión de conexiones WebSocket activas."""

import json
import logging

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Gestiona conexiones WebSocket activas."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Acepta y registra una nueva conexión."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("Cliente WebSocket conectado. Total: %d", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remueve una conexión desconectada."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("Cliente WebSocket desconectado. Total: %d", len(self._connections))

    async def broadcast(self, message: dict) -> None:
        """Envía un mensaje JSON a TODOS los clientes conectados."""
        if not self._connections:
            return

        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []

        for ws in self._connections:
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            else:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)
