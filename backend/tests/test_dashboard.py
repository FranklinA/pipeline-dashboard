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
from app.models import Pipeline, Stage
from app.websocket_manager import WebSocketManager

pytestmark = pytest.mark.asyncio

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def client(test_engine, db_factory):
    async def override_session():
        async with db_factory() as session:
            yield session

    mock_ws = WebSocketManager()
    mock_ws.broadcast = AsyncMock()
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws

    with patch("app.routers.pipelines.simulate_pipeline", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


async def _insert_pipeline(db_factory, status: str, duration: int | None = None) -> Pipeline:
    """Inserta un pipeline con status dado directamente en la DB."""
    async with db_factory() as db:
        p = Pipeline(
            name="P",
            repository="org/r",
            branch="main",
            trigger_type="manual",
            template="Quick Test",
            status=status,
            created_at=_now(),
            duration_seconds=duration,
            started_at=_now() if status != "pending" else None,
            finished_at=_now() if status in ("success", "failed", "cancelled") else None,
        )
        db.add(p)
        await db.flush()
        db.add(Stage(pipeline_id=p.id, name="Checkout", order=1, status="pending"))
        db.add(Stage(pipeline_id=p.id, name="Test", order=2, status="pending"))
        await db.commit()
        return p


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_dashboard_empty(client):
    r = await client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total_pipelines"] == 0
    assert body["recent_pipelines"] == []
    assert body["avg_duration_seconds"] is None
    assert body["success_rate_percent"] is None


async def test_dashboard_total_count(client, db_factory):
    for status in ("pending", "running", "success"):
        await _insert_pipeline(db_factory, status)
    r = await client.get("/api/dashboard")
    assert r.json()["summary"]["total_pipelines"] == 3


async def test_dashboard_by_status_counts(client, db_factory):
    await _insert_pipeline(db_factory, "success")
    await _insert_pipeline(db_factory, "success")
    await _insert_pipeline(db_factory, "failed")
    await _insert_pipeline(db_factory, "running")

    body = (await client.get("/api/dashboard")).json()
    by_status = body["summary"]["by_status"]
    assert by_status["success"] == 2
    assert by_status["failed"] == 1
    assert by_status["running"] == 1
    assert by_status["pending"] == 0
    assert by_status["cancelled"] == 0


async def test_dashboard_recent_pipelines_max_5(client, db_factory):
    for _ in range(7):
        await _insert_pipeline(db_factory, "success", duration=60)
    body = (await client.get("/api/dashboard")).json()
    assert len(body["recent_pipelines"]) == 5


async def test_dashboard_recent_pipelines_have_stages(client, db_factory):
    await _insert_pipeline(db_factory, "success", duration=60)
    body = (await client.get("/api/dashboard")).json()
    assert len(body["recent_pipelines"][0]["stages"]) == 2


async def test_dashboard_avg_duration_only_success(client, db_factory):
    await _insert_pipeline(db_factory, "success", duration=100)
    await _insert_pipeline(db_factory, "success", duration=200)
    await _insert_pipeline(db_factory, "failed", duration=50)  # no debe contar

    body = (await client.get("/api/dashboard")).json()
    assert body["avg_duration_seconds"] == 150.0


async def test_dashboard_success_rate(client, db_factory):
    await _insert_pipeline(db_factory, "success")
    await _insert_pipeline(db_factory, "success")
    await _insert_pipeline(db_factory, "failed")
    await _insert_pipeline(db_factory, "cancelled")
    # 2 success / 4 finalizados = 50%
    body = (await client.get("/api/dashboard")).json()
    assert body["success_rate_percent"] == 50.0


async def test_dashboard_success_rate_none_when_no_finished(client, db_factory):
    await _insert_pipeline(db_factory, "running")
    body = (await client.get("/api/dashboard")).json()
    assert body["success_rate_percent"] is None


async def test_dashboard_response_structure(client):
    r = await client.get("/api/dashboard")
    body = r.json()
    assert "summary" in body
    assert "recent_pipelines" in body
    assert "avg_duration_seconds" in body
    assert "success_rate_percent" in body
    assert "total_pipelines" in body["summary"]
    assert "by_status" in body["summary"]
