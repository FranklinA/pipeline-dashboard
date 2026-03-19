"""Tests para el endpoint /api/dashboard."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.dependencies import get_ws_manager
from app.main import app
from app.websocket_manager import WebSocketManager
from tests.conftest import TEST_DATABASE_URL, insert_pipeline

pytestmark = pytest.mark.asyncio


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def factory(test_engine):
    return async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def client(test_engine, factory):
    async def _override():
        async with factory() as s:
            yield s

    mock_ws = WebSocketManager()
    mock_ws.broadcast = AsyncMock()
    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws

    with patch("app.routers.pipelines.simulate_pipeline", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


async def _get_dashboard(client):
    r = await client.get("/api/dashboard")
    assert r.status_code == 200
    return r.json()


# ── Estructura de respuesta ────────────────────────────────────────────────────

async def test_dashboard_returns_200(client):
    r = await client.get("/api/dashboard")
    assert r.status_code == 200


async def test_dashboard_top_level_fields(client):
    body = await _get_dashboard(client)
    assert "summary" in body
    assert "recent_pipelines" in body
    assert "avg_duration_seconds" in body
    assert "success_rate_percent" in body


async def test_dashboard_summary_fields(client):
    body = await _get_dashboard(client)
    summary = body["summary"]
    assert "total_pipelines" in summary
    assert "by_status" in summary


async def test_dashboard_by_status_all_keys(client):
    body = await _get_dashboard(client)
    by_status = body["summary"]["by_status"]
    for key in ("pending", "running", "success", "failed", "cancelled"):
        assert key in by_status, f"Falta key '{key}' en by_status"


# ── Base de datos vacía ────────────────────────────────────────────────────────

async def test_dashboard_empty_db(client):
    body = await _get_dashboard(client)
    assert body["summary"]["total_pipelines"] == 0
    assert body["recent_pipelines"] == []
    assert body["avg_duration_seconds"] is None
    assert body["success_rate_percent"] is None


async def test_dashboard_empty_by_status_all_zero(client):
    body = await _get_dashboard(client)
    for count in body["summary"]["by_status"].values():
        assert count == 0


# ── total_pipelines ────────────────────────────────────────────────────────────

async def test_dashboard_total_counts_all_statuses(client, factory):
    for status in ("pending", "running", "success", "failed", "cancelled"):
        await insert_pipeline(factory, status=status)
    body = await _get_dashboard(client)
    assert body["summary"]["total_pipelines"] == 5


async def test_dashboard_total_increases_with_new_pipelines(client, factory):
    body1 = await _get_dashboard(client)
    await insert_pipeline(factory, status="pending")
    body2 = await _get_dashboard(client)
    assert body2["summary"]["total_pipelines"] == body1["summary"]["total_pipelines"] + 1


# ── by_status ──────────────────────────────────────────────────────────────────

async def test_dashboard_by_status_pending(client, factory):
    await insert_pipeline(factory, status="pending")
    await insert_pipeline(factory, status="pending")
    body = await _get_dashboard(client)
    assert body["summary"]["by_status"]["pending"] == 2


async def test_dashboard_by_status_running(client, factory):
    await insert_pipeline(factory, status="running")
    body = await _get_dashboard(client)
    assert body["summary"]["by_status"]["running"] == 1


async def test_dashboard_by_status_success(client, factory):
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="success")
    body = await _get_dashboard(client)
    assert body["summary"]["by_status"]["success"] == 3


async def test_dashboard_by_status_failed(client, factory):
    await insert_pipeline(factory, status="failed")
    body = await _get_dashboard(client)
    assert body["summary"]["by_status"]["failed"] == 1


async def test_dashboard_by_status_cancelled(client, factory):
    await insert_pipeline(factory, status="cancelled")
    await insert_pipeline(factory, status="cancelled")
    body = await _get_dashboard(client)
    assert body["summary"]["by_status"]["cancelled"] == 2


async def test_dashboard_by_status_mixed(client, factory):
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="failed")
    await insert_pipeline(factory, status="running")
    await insert_pipeline(factory, status="cancelled")

    by_status = (await _get_dashboard(client))["summary"]["by_status"]
    assert by_status["success"] == 2
    assert by_status["failed"] == 1
    assert by_status["running"] == 1
    assert by_status["cancelled"] == 1
    assert by_status["pending"] == 0


async def test_dashboard_by_status_missing_statuses_are_zero(client, factory):
    await insert_pipeline(factory, status="success")
    by_status = (await _get_dashboard(client))["summary"]["by_status"]
    assert by_status["pending"] == 0
    assert by_status["running"] == 0
    assert by_status["failed"] == 0
    assert by_status["cancelled"] == 0


# ── recent_pipelines ───────────────────────────────────────────────────────────

async def test_dashboard_recent_max_5(client, factory):
    for _ in range(8):
        await insert_pipeline(factory, status="success", duration=10)
    body = await _get_dashboard(client)
    assert len(body["recent_pipelines"]) == 5


async def test_dashboard_recent_less_than_5(client, factory):
    for _ in range(3):
        await insert_pipeline(factory, status="success")
    body = await _get_dashboard(client)
    assert len(body["recent_pipelines"]) == 3


async def test_dashboard_recent_pipelines_include_stages(client, factory):
    await insert_pipeline(factory, status="success", num_stages=3)
    body = await _get_dashboard(client)
    assert len(body["recent_pipelines"][0]["stages"]) == 3


async def test_dashboard_recent_pipelines_have_required_fields(client, factory):
    await insert_pipeline(factory, status="success")
    pipeline = (await _get_dashboard(client))["recent_pipelines"][0]
    for field in ("id", "name", "status", "created_at", "stages"):
        assert field in pipeline


async def test_dashboard_recent_pipelines_ordered_desc(client, factory):
    """Los pipelines recientes deben estar ordenados por created_at DESC."""
    ids = []
    for i in range(4):
        p = await insert_pipeline(factory, status="success", name=f"P{i}")
        ids.append(p.id)

    recent_ids = [(p["id"]) for p in (await _get_dashboard(client))["recent_pipelines"]]
    # Los más recientes (IDs mayores) deben aparecer primero
    assert recent_ids == sorted(recent_ids, reverse=True)


async def test_dashboard_recent_pipelines_created_at_has_z(client, factory):
    await insert_pipeline(factory, status="success")
    pipeline = (await _get_dashboard(client))["recent_pipelines"][0]
    assert pipeline["created_at"].endswith("Z")


# ── avg_duration_seconds ───────────────────────────────────────────────────────

async def test_dashboard_avg_duration_single_success(client, factory):
    await insert_pipeline(factory, status="success", duration=120)
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] == 120.0


async def test_dashboard_avg_duration_multiple_success(client, factory):
    await insert_pipeline(factory, status="success", duration=100)
    await insert_pipeline(factory, status="success", duration=200)
    await insert_pipeline(factory, status="success", duration=300)
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] == 200.0


async def test_dashboard_avg_duration_excludes_failed(client, factory):
    await insert_pipeline(factory, status="success", duration=100)
    await insert_pipeline(factory, status="success", duration=200)
    await insert_pipeline(factory, status="failed", duration=50)  # no debe contar
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] == 150.0


async def test_dashboard_avg_duration_excludes_cancelled(client, factory):
    await insert_pipeline(factory, status="success", duration=60)
    await insert_pipeline(factory, status="cancelled", duration=999)
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] == 60.0


async def test_dashboard_avg_duration_none_when_no_success(client, factory):
    await insert_pipeline(factory, status="failed", duration=30)
    await insert_pipeline(factory, status="cancelled", duration=15)
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] is None


async def test_dashboard_avg_duration_none_when_only_running(client, factory):
    await insert_pipeline(factory, status="running")
    body = await _get_dashboard(client)
    assert body["avg_duration_seconds"] is None


# ── success_rate_percent ───────────────────────────────────────────────────────

async def test_dashboard_success_rate_100(client, factory):
    """2 success / 2 finalizados = 100%"""
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="success")
    body = await _get_dashboard(client)
    assert body["success_rate_percent"] == 100.0


async def test_dashboard_success_rate_0(client, factory):
    """0 success / 2 finalizados = 0%"""
    await insert_pipeline(factory, status="failed")
    await insert_pipeline(factory, status="cancelled")
    body = await _get_dashboard(client)
    assert body["success_rate_percent"] == 0.0


async def test_dashboard_success_rate_50(client, factory):
    """2 success / 4 finalizados = 50%"""
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="failed")
    await insert_pipeline(factory, status="cancelled")
    body = await _get_dashboard(client)
    assert body["success_rate_percent"] == 50.0


async def test_dashboard_success_rate_rounded_1_decimal(client, factory):
    """1 success / 3 finalizados = 33.3%"""
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="failed")
    await insert_pipeline(factory, status="failed")
    body = await _get_dashboard(client)
    assert body["success_rate_percent"] == 33.3


async def test_dashboard_success_rate_none_when_no_finished(client, factory):
    await insert_pipeline(factory, status="pending")
    await insert_pipeline(factory, status="running")
    body = await _get_dashboard(client)
    assert body["success_rate_percent"] is None


async def test_dashboard_success_rate_excludes_active(client, factory):
    """Pipelines pending/running no cuentan para la tasa de éxito."""
    await insert_pipeline(factory, status="success")
    await insert_pipeline(factory, status="pending")
    await insert_pipeline(factory, status="running")
    body = await _get_dashboard(client)
    # 1 success / 1 finalizado = 100% (pending y running no cuentan)
    assert body["success_rate_percent"] == 100.0


# ── Via API (pipeline creado por POST) ─────────────────────────────────────────

async def test_dashboard_reflects_api_created_pipelines(client):
    """Los pipelines creados via API deben aparecer en el dashboard."""
    payload = {
        "name": "API Test",
        "repository": "org/test",
        "branch": "main",
        "trigger_type": "manual",
        "template": "Quick Test",
    }
    await client.post("/api/pipelines", json=payload)
    await client.post("/api/pipelines", json=payload)

    body = await _get_dashboard(client)
    assert body["summary"]["total_pipelines"] == 2
    assert body["summary"]["by_status"]["pending"] == 2
    assert len(body["recent_pipelines"]) == 2
