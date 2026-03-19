"""Tests para los endpoints /api/pipelines."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_session
from app.main import app
from app.dependencies import get_ws_manager
from app.websocket_manager import WebSocketManager

pytestmark = pytest.mark.asyncio

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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
async def client(test_engine):
    """Cliente HTTP con DB en memoria y simulación deshabilitada."""
    factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_session():
        async with factory() as session:
            yield session

    mock_ws = WebSocketManager()
    mock_ws.broadcast = AsyncMock()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws

    # Parchear simulate_pipeline para no lanzar simulaciones reales en tests
    with patch("app.routers.pipelines.simulate_pipeline", new_callable=AsyncMock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


VALID_PAYLOAD = {
    "name": "My Pipeline",
    "repository": "org/repo",
    "branch": "main",
    "trigger_type": "manual",
    "template": "Quick Test",
}


# ── POST /api/pipelines ────────────────────────────────────────────────────────

async def test_create_pipeline_returns_201(client):
    r = await client.post("/api/pipelines", json=VALID_PAYLOAD)
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Pipeline"
    assert data["status"] == "pending"
    assert data["started_at"] is None
    assert len(data["stages"]) == 2  # Quick Test tiene 2 stages


async def test_create_pipeline_stages_are_pending(client):
    r = await client.post("/api/pipelines", json=VALID_PAYLOAD)
    for stage in r.json()["stages"]:
        assert stage["status"] == "pending"


async def test_create_pipeline_invalid_template(client):
    payload = {**VALID_PAYLOAD, "template": "Nonexistent"}
    r = await client.post("/api/pipelines", json=payload)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "INVALID_FIELD_VALUE"


async def test_create_pipeline_cicd_standard_has_6_stages(client):
    payload = {**VALID_PAYLOAD, "template": "CI/CD Standard"}
    r = await client.post("/api/pipelines", json=payload)
    assert r.status_code == 201
    assert len(r.json()["stages"]) == 6


async def test_create_pipeline_full_deploy_has_10_stages(client):
    payload = {**VALID_PAYLOAD, "template": "Full Deploy"}
    r = await client.post("/api/pipelines", json=payload)
    assert r.status_code == 201
    assert len(r.json()["stages"]) == 10


async def test_create_pipeline_datetime_format_has_z(client):
    r = await client.post("/api/pipelines", json=VALID_PAYLOAD)
    created_at = r.json()["created_at"]
    assert created_at.endswith("Z"), f"created_at no termina en Z: {created_at}"


# ── GET /api/pipelines ─────────────────────────────────────────────────────────

async def test_list_pipelines_empty(client):
    r = await client.get("/api/pipelines")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


async def test_list_pipelines_pagination(client):
    for i in range(3):
        await client.post("/api/pipelines", json={**VALID_PAYLOAD, "name": f"P{i}"})

    r = await client.get("/api/pipelines?per_page=2&page=1")
    body = r.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["total"] == 3
    assert body["pagination"]["total_pages"] == 2
    assert body["pagination"]["per_page"] == 2


async def test_list_pipelines_filter_by_status(client):
    await client.post("/api/pipelines", json=VALID_PAYLOAD)

    r = await client.get("/api/pipelines?status=pending")
    assert r.json()["pagination"]["total"] == 1

    r = await client.get("/api/pipelines?status=running")
    assert r.json()["pagination"]["total"] == 0


async def test_list_pipelines_filter_by_repository(client):
    await client.post("/api/pipelines", json={**VALID_PAYLOAD, "repository": "org/a"})
    await client.post("/api/pipelines", json={**VALID_PAYLOAD, "repository": "org/b"})

    r = await client.get("/api/pipelines?repository=org/a")
    assert r.json()["pagination"]["total"] == 1


async def test_list_pipelines_filter_by_branch(client):
    await client.post("/api/pipelines", json={**VALID_PAYLOAD, "branch": "main"})
    await client.post("/api/pipelines", json={**VALID_PAYLOAD, "branch": "develop"})

    r = await client.get("/api/pipelines?branch=main")
    assert r.json()["pagination"]["total"] == 1


async def test_list_pipelines_pagination_structure(client):
    r = await client.get("/api/pipelines")
    body = r.json()
    assert "data" in body
    assert "pagination" in body
    pagination = body["pagination"]
    assert all(k in pagination for k in ("total", "page", "per_page", "total_pages"))


# ── GET /api/pipelines/{id} ────────────────────────────────────────────────────

async def test_get_pipeline_by_id(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    r = await client.get(f"/api/pipelines/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert len(r.json()["stages"]) == 2


async def test_get_pipeline_not_found(client):
    r = await client.get("/api/pipelines/9999")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


# ── POST /api/pipelines/{id}/cancel ───────────────────────────────────────────

async def test_cancel_pending_pipeline(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    r = await client.post(f"/api/pipelines/{created['id']}/cancel")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "cancelled"
    assert data["finished_at"] is not None


async def test_cancel_already_cancelled_pipeline(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{created['id']}/cancel")
    r = await client.post(f"/api/pipelines/{created['id']}/cancel")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_cancel_not_found(client):
    r = await client.post("/api/pipelines/9999/cancel")
    assert r.status_code == 404


# ── POST /api/pipelines/{id}/retry ────────────────────────────────────────────

async def test_retry_cancelled_pipeline(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{created['id']}/cancel")
    r = await client.post(f"/api/pipelines/{created['id']}/retry")
    assert r.status_code == 201
    new_pipeline = r.json()
    assert new_pipeline["id"] != created["id"]
    assert new_pipeline["status"] == "pending"
    assert new_pipeline["name"] == created["name"]
    assert len(new_pipeline["stages"]) == len(created["stages"])


async def test_retry_pending_pipeline_fails(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    r = await client.post(f"/api/pipelines/{created['id']}/retry")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_retry_not_found(client):
    r = await client.post("/api/pipelines/9999/retry")
    assert r.status_code == 404


# ── DELETE /api/pipelines/{id} ────────────────────────────────────────────────

async def test_delete_cancelled_pipeline(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{created['id']}/cancel")
    r = await client.delete(f"/api/pipelines/{created['id']}")
    assert r.status_code == 204


async def test_delete_pending_pipeline_fails(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    r = await client.delete(f"/api/pipelines/{created['id']}")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_delete_removes_from_list(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{created['id']}/cancel")
    await client.delete(f"/api/pipelines/{created['id']}")
    r = await client.get(f"/api/pipelines/{created['id']}")
    assert r.status_code == 404


async def test_delete_not_found(client):
    r = await client.delete("/api/pipelines/9999")
    assert r.status_code == 404


# ── GET /api/pipelines/{id}/stages/{stage_id}/logs ────────────────────────────

async def test_get_stage_logs_empty(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    stage_id = created["stages"][0]["id"]
    r = await client.get(f"/api/pipelines/{created['id']}/stages/{stage_id}/logs")
    assert r.status_code == 200
    body = r.json()
    assert body["stage_id"] == stage_id
    assert body["stage_name"] == created["stages"][0]["name"]
    assert body["logs"] == []


async def test_get_stage_logs_pipeline_not_found(client):
    r = await client.get("/api/pipelines/9999/stages/1/logs")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


async def test_get_stage_logs_stage_not_found(client):
    created = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    r = await client.get(f"/api/pipelines/{created['id']}/stages/9999/logs")
    assert r.status_code == 404


async def test_get_stage_logs_wrong_pipeline(client):
    """Stage que pertenece a otro pipeline debe dar 404."""
    p1 = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    p2 = (await client.post("/api/pipelines", json=VALID_PAYLOAD)).json()
    stage_from_p2 = p2["stages"][0]["id"]
    r = await client.get(f"/api/pipelines/{p1['id']}/stages/{stage_from_p2}/logs")
    assert r.status_code == 404
