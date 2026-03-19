"""Tests para WebSocketManager y el endpoint /ws/pipelines."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
import pytest_asyncio
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.database import Base, get_session
from app.dependencies import get_ws_manager
from app.main import app
from app.websocket_manager import WebSocketManager
from tests.conftest import TEST_DATABASE_URL

# asyncio_mode=auto en pytest.ini cubre los tests async; los sync no necesitan mark.

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_ws(state: WebSocketState = WebSocketState.CONNECTED) -> AsyncMock:
    """Crea un WebSocket mock con el estado dado."""
    ws = AsyncMock(spec=WebSocket)
    type(ws).client_state = PropertyMock(return_value=state)
    ws.send_text = AsyncMock()
    return ws


# ── Unit tests: WebSocketManager ──────────────────────────────────────────────

async def test_manager_connect_registers_client():
    """connect() debe aceptar y almacenar el WebSocket."""
    manager = WebSocketManager()
    ws = _make_mock_ws()

    await manager.connect(ws)

    ws.accept.assert_awaited_once()
    assert ws in manager._connections


async def test_manager_disconnect_removes_client():
    """disconnect() debe remover el WebSocket de la lista."""
    manager = WebSocketManager()
    ws = _make_mock_ws()

    await manager.connect(ws)
    assert ws in manager._connections

    await manager.disconnect(ws)
    assert ws not in manager._connections


async def test_manager_disconnect_unknown_client_is_noop():
    """disconnect() de un WS no registrado no debe lanzar excepción."""
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.disconnect(ws)  # no explota


async def test_manager_broadcast_sends_to_all_clients():
    """broadcast() debe enviar el mensaje JSON a todos los clientes."""
    manager = WebSocketManager()
    ws1 = _make_mock_ws()
    ws2 = _make_mock_ws()
    ws3 = _make_mock_ws()

    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.connect(ws3)

    msg = {"type": "pipeline_update", "pipeline_id": 1, "data": {"status": "running"}}
    await manager.broadcast(msg)

    expected = json.dumps(msg, default=str)
    ws1.send_text.assert_awaited_once_with(expected)
    ws2.send_text.assert_awaited_once_with(expected)
    ws3.send_text.assert_awaited_once_with(expected)


async def test_manager_broadcast_empty_connections_is_noop():
    """broadcast() sin clientes no debe lanzar excepción."""
    manager = WebSocketManager()
    await manager.broadcast({"type": "test"})  # no explota


async def test_manager_broadcast_removes_dead_connections():
    """broadcast() debe eliminar clientes que lanzaron excepción al enviar."""
    manager = WebSocketManager()
    ws_ok = _make_mock_ws()
    ws_dead = _make_mock_ws()
    ws_dead.send_text.side_effect = RuntimeError("client gone")

    await manager.connect(ws_ok)
    await manager.connect(ws_dead)

    await manager.broadcast({"type": "test"})

    assert ws_ok in manager._connections
    assert ws_dead not in manager._connections


async def test_manager_broadcast_removes_disconnected_state():
    """Clientes en estado DISCONNECTED deben eliminarse en el broadcast."""
    manager = WebSocketManager()
    ws_live = _make_mock_ws(WebSocketState.CONNECTED)
    ws_closed = _make_mock_ws(WebSocketState.DISCONNECTED)

    manager._connections.append(ws_live)
    manager._connections.append(ws_closed)

    await manager.broadcast({"type": "ping"})

    assert ws_live in manager._connections
    assert ws_closed not in manager._connections
    ws_live.send_text.assert_awaited_once()
    ws_closed.send_text.assert_not_awaited()


async def test_manager_broadcast_serializes_with_default_str():
    """broadcast() debe serializar valores no-JSON (como datetime) via str()."""
    from datetime import datetime
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.connect(ws)

    dt = datetime(2026, 3, 17, 10, 30, 0)
    msg = {"type": "test", "ts": dt}
    await manager.broadcast(msg)

    sent = ws.send_text.call_args[0][0]
    parsed = json.loads(sent)
    assert "ts" in parsed  # datetime serializado como string


async def test_manager_multiple_broadcasts_accumulate():
    """broadcast() múltiple debe enviar cada vez."""
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.connect(ws)

    for i in range(3):
        await manager.broadcast({"n": i})

    assert ws.send_text.await_count == 3


async def test_manager_connect_multiple_then_disconnect_one():
    """Desconectar uno no debe afectar al resto."""
    manager = WebSocketManager()
    ws1 = _make_mock_ws()
    ws2 = _make_mock_ws()

    await manager.connect(ws1)
    await manager.connect(ws2)
    await manager.disconnect(ws1)

    await manager.broadcast({"type": "ping"})

    ws1.send_text.assert_not_awaited()
    ws2.send_text.assert_awaited_once()


# ── Verificación de formatos de mensaje (spec compliance) ─────────────────────

async def test_ws_message_format_pipeline_update():
    """pipeline_update debe cumplir exactamente el formato de shared-contracts."""
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.connect(ws)

    msg = {
        "type": "pipeline_update",
        "pipeline_id": 1,
        "data": {
            "status": "running",
            "current_stage": {"id": 2, "name": "Build", "order": 2, "status": "running"},
            "stages_summary": [
                {"id": 1, "name": "Checkout", "order": 1, "status": "success"},
                {"id": 2, "name": "Build", "order": 2, "status": "running"},
                {"id": 3, "name": "Deploy", "order": 3, "status": "pending"},
            ],
        },
    }
    await manager.broadcast(msg)

    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "pipeline_update"
    assert sent["pipeline_id"] == 1
    assert sent["data"]["status"] == "running"
    assert sent["data"]["current_stage"]["name"] == "Build"
    assert len(sent["data"]["stages_summary"]) == 3
    for stage in sent["data"]["stages_summary"]:
        assert all(k in stage for k in ("id", "name", "order", "status"))


async def test_ws_message_format_pipeline_completed():
    """pipeline_completed debe cumplir exactamente el formato de shared-contracts."""
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.connect(ws)

    msg = {
        "type": "pipeline_completed",
        "pipeline_id": 1,
        "data": {
            "status": "success",
            "duration_seconds": 45,
            "finished_at": "2026-03-17T10:30:45Z",
        },
    }
    await manager.broadcast(msg)

    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "pipeline_completed"
    assert sent["pipeline_id"] == 1
    assert sent["data"]["status"] == "success"
    assert sent["data"]["duration_seconds"] == 45
    assert sent["data"]["finished_at"].endswith("Z")


async def test_ws_message_format_log_entry():
    """log_entry debe cumplir exactamente el formato de shared-contracts."""
    manager = WebSocketManager()
    ws = _make_mock_ws()
    await manager.connect(ws)

    msg = {
        "type": "log_entry",
        "pipeline_id": 1,
        "stage_id": 2,
        "data": {
            "timestamp": "2026-03-17T10:30:15Z",
            "level": "info",
            "message": "Building Docker image...",
        },
    }
    await manager.broadcast(msg)

    sent = json.loads(ws.send_text.call_args[0][0])
    assert sent["type"] == "log_entry"
    assert sent["pipeline_id"] == 1
    assert sent["stage_id"] == 2
    assert sent["data"]["timestamp"].endswith("Z")
    assert sent["data"]["level"] in ("info", "warning", "error")
    assert isinstance(sent["data"]["message"], str)


# ── Tests del endpoint /ws/pipelines (integración con TestClient sync) ────────

@pytest.fixture
def test_engine_sync():
    """Engine síncrono para TestClient (no async)."""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_setup())
    yield engine
    asyncio.get_event_loop().run_until_complete(_teardown())


@pytest.fixture
def tc(test_engine_sync):
    """TestClient con DB en memoria para tests de WS síncronos."""
    factory = async_sessionmaker(
        bind=test_engine_sync, class_=AsyncSession, expire_on_commit=False
    )
    mock_ws_mgr = WebSocketManager()

    async def _override():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws_mgr

    with patch("app.routers.pipelines.simulate_pipeline", new_callable=AsyncMock):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client

    app.dependency_overrides.clear()


def test_ws_endpoint_accepts_connection(tc):
    """El endpoint /ws/pipelines debe aceptar conexiones WebSocket."""
    with tc.websocket_connect("/ws/pipelines"):
        pass  # Conexión establecida y cerrada sin error


def test_ws_endpoint_multiple_clients(tc):
    """El endpoint debe aceptar múltiples conexiones simultáneas."""
    with tc.websocket_connect("/ws/pipelines"):
        with tc.websocket_connect("/ws/pipelines"):
            pass  # Ambas conexiones establecidas sin error


def test_ws_endpoint_disconnect_is_silent(tc):
    """Desconectar un cliente no debe lanzar excepción en el servidor."""
    with tc.websocket_connect("/ws/pipelines"):
        pass  # Al salir del context manager se desconecta silenciosamente
    # Hacer más requests para confirmar que el servidor sigue activo
    r = tc.get("/health")
    assert r.status_code == 200


def test_ws_endpoint_url_does_not_exist_for_http(tc):
    """GET /ws/pipelines debe retornar 400/403/404 (no es un endpoint HTTP)."""
    r = tc.get("/ws/pipelines")
    assert r.status_code in (400, 403, 404, 426)


def test_ws_health_still_works_after_ws_connections(tc):
    """El servidor debe seguir respondiendo HTTP después de conexiones WS."""
    with tc.websocket_connect("/ws/pipelines"):
        r = tc.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── Tests de integración WS + simulador ───────────────────────────────────────

async def test_simulator_sends_pipeline_update_on_stage_start():
    """El simulador debe emitir pipeline_update cuando un stage pasa a running."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.simulator import simulate_pipeline
    import app.simulator as sim_mod
    from tests.conftest import insert_pipeline

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    manager = WebSocketManager()
    manager.broadcast = AsyncMock()

    orig = sim_mod.random.random
    sim_mod.random.random = lambda: 1.0
    try:
        p = await insert_pipeline(factory, template="Quick Test", status="pending", num_stages=0)
        # Crear stages manualmente para Quick Test
        from app.models import Stage
        async with factory() as db:
            db.add(Stage(pipeline_id=p.id, name="Checkout", order=1, status="pending"))
            db.add(Stage(pipeline_id=p.id, name="Test", order=2, status="pending"))
            await db.commit()

        await simulate_pipeline(p.id, factory, manager, speed_multiplier=100)

        call_types = {c.args[0]["type"] for c in manager.broadcast.call_args_list}
        assert "pipeline_update" in call_types
    finally:
        sim_mod.random.random = orig
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_simulator_sends_log_entry_for_each_log():
    """El simulador debe emitir log_entry por cada mensaje de log generado."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.simulator import simulate_pipeline
    import app.simulator as sim_mod
    from app.models import Stage

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    manager = WebSocketManager()
    manager.broadcast = AsyncMock()

    orig = sim_mod.random.random
    sim_mod.random.random = lambda: 1.0
    try:
        from tests.conftest import insert_pipeline
        p = await insert_pipeline(factory, template="Quick Test", status="pending", num_stages=0)
        async with factory() as db:
            db.add(Stage(pipeline_id=p.id, name="Checkout", order=1, status="pending"))
            db.add(Stage(pipeline_id=p.id, name="Test", order=2, status="pending"))
            await db.commit()

        await simulate_pipeline(p.id, factory, manager, speed_multiplier=100)

        log_calls = [c for c in manager.broadcast.call_args_list
                     if c.args[0]["type"] == "log_entry"]
        assert len(log_calls) > 0

        for call in log_calls:
            msg = call.args[0]
            assert "pipeline_id" in msg
            assert "stage_id" in msg
            assert "timestamp" in msg["data"]
            assert "level" in msg["data"]
            assert "message" in msg["data"]
            assert msg["data"]["timestamp"].endswith("Z")
    finally:
        sim_mod.random.random = orig
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def test_simulator_sends_pipeline_completed_at_end():
    """El simulador debe emitir pipeline_completed exactamente una vez al terminar."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.simulator import simulate_pipeline
    import app.simulator as sim_mod
    from app.models import Stage

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    manager = WebSocketManager()
    manager.broadcast = AsyncMock()

    orig = sim_mod.random.random
    sim_mod.random.random = lambda: 1.0
    try:
        from tests.conftest import insert_pipeline
        p = await insert_pipeline(factory, template="Quick Test", status="pending", num_stages=0)
        async with factory() as db:
            db.add(Stage(pipeline_id=p.id, name="Checkout", order=1, status="pending"))
            db.add(Stage(pipeline_id=p.id, name="Test", order=2, status="pending"))
            await db.commit()

        await simulate_pipeline(p.id, factory, manager, speed_multiplier=100)

        completed_calls = [c for c in manager.broadcast.call_args_list
                           if c.args[0]["type"] == "pipeline_completed"]
        assert len(completed_calls) == 1

        msg = completed_calls[0].args[0]
        assert msg["pipeline_id"] == p.id
        assert msg["data"]["status"] == "success"
        assert msg["data"]["duration_seconds"] is not None
        assert msg["data"]["finished_at"].endswith("Z")
    finally:
        sim_mod.random.random = orig
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
