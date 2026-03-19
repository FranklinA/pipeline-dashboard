"""Dependencias compartidas de la aplicación."""

from app.websocket_manager import WebSocketManager

# Instancia singleton del manager de WebSocket
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Retorna el singleton del WebSocketManager."""
    return ws_manager
