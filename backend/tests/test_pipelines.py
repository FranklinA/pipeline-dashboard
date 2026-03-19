"""Tests para los endpoints /api/pipelines."""

import asyncio
import random as stdlib_random
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.simulator as sim_module
from app.database import Base, get_session
from app.dependencies import get_ws_manager
from app.main import app
from app.websocket_manager import WebSocketManager
from tests.conftest import TEST_DATABASE_URL, insert_pipeline

pytestmark = pytest.mark.asyncio

QUICK_PAYLOAD = {
    "name": "My Pipeline",
    "repository": "org/repo",
    "branch": "main",
    "trigger_type": "manual",
    "template": "Quick Test",
}


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
    """Cliente HTTP sin simulación real (simulate_pipeline mockeado)."""
    async def _override_session():
        async with factory() as s:
            yield s

    mock_ws = WebSocketManager()
    mock_ws.broadcast = AsyncMock()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws

    with patch("app.routers.pipelines.simulate_pipeline", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sim_client(test_engine, factory):
    """Cliente con simulador real a speed_multiplier=100."""
    async def _override_session():
        async with factory() as s:
            yield s

    mock_ws = WebSocketManager()
    mock_ws.broadcast = AsyncMock()
    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_ws_manager] = lambda: mock_ws

    from app.simulator import simulate_pipeline as _real_sim

    async def _fast_sim(pipeline_id, _ignored_factory, ws_mgr):
        await _real_sim(pipeline_id, factory, ws_mgr, speed_multiplier=100)

    with patch("app.routers.pipelines.simulate_pipeline", new=_fast_sim):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield SimpleNamespace(client=ac, ws=mock_ws, factory=factory)

    app.dependency_overrides.clear()


# ── POST /api/pipelines ────────────────────────────────────────────────────────

async def test_create_returns_201(client):
    r = await client.post("/api/pipelines", json=QUICK_PAYLOAD)
    assert r.status_code == 201


async def test_create_response_fields(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    for field in ("id", "name", "repository", "branch", "trigger_type",
                  "status", "started_at", "finished_at", "duration_seconds",
                  "created_at", "stages"):
        assert field in data, f"Campo ausente: {field}"


async def test_create_initial_status_is_pending(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert data["status"] == "pending"
    assert data["started_at"] is None
    assert data["finished_at"] is None
    assert data["duration_seconds"] is None


async def test_create_stores_correct_field_values(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert data["name"] == "My Pipeline"
    assert data["repository"] == "org/repo"
    assert data["branch"] == "main"
    assert data["trigger_type"] == "manual"


async def test_create_created_at_has_z_suffix(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert data["created_at"].endswith("Z")


async def test_create_template_quick_test_gives_2_stages(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert len(data["stages"]) == 2


async def test_create_template_cicd_standard_gives_6_stages(client):
    r = await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "CI/CD Standard"})
    assert r.status_code == 201
    assert len(r.json()["stages"]) == 6


async def test_create_template_full_deploy_gives_10_stages(client):
    r = await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "Full Deploy"})
    assert r.status_code == 201
    assert len(r.json()["stages"]) == 10


async def test_create_stages_ordered_by_order(client):
    data = (await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "CI/CD Standard"})).json()
    orders = [s["order"] for s in data["stages"]]
    assert orders == sorted(orders)


async def test_create_stages_all_pending(client):
    data = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert all(s["status"] == "pending" for s in data["stages"])


async def test_create_stage_fields(client):
    stage = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()["stages"][0]
    for field in ("id", "name", "order", "status", "started_at", "finished_at", "duration_seconds"):
        assert field in stage, f"Campo de stage ausente: {field}"


async def test_create_invalid_template_returns_422(client):
    r = await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "Nonexistent"})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "INVALID_FIELD_VALUE"


async def test_create_missing_name_returns_422(client):
    payload = {k: v for k, v in QUICK_PAYLOAD.items() if k != "name"}
    r = await client.post("/api/pipelines", json=payload)
    assert r.status_code == 422


async def test_create_missing_template_returns_422(client):
    payload = {k: v for k, v in QUICK_PAYLOAD.items() if k != "template"}
    r = await client.post("/api/pipelines", json=payload)
    assert r.status_code == 422


async def test_create_trigger_type_push(client):
    data = (await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "trigger_type": "push"})).json()
    assert data["trigger_type"] == "push"


async def test_create_trigger_type_schedule(client):
    data = (await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "trigger_type": "schedule"})).json()
    assert data["trigger_type"] == "schedule"


async def test_create_multiple_get_different_ids(client):
    r1 = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r2 = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    assert r1["id"] != r2["id"]


# ── GET /api/pipelines ─────────────────────────────────────────────────────────

async def test_list_empty_db(client):
    r = await client.get("/api/pipelines")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["pagination"]["total"] == 0
    assert body["pagination"]["page"] == 1


async def test_list_pagination_structure(client):
    r = await client.get("/api/pipelines")
    p = r.json()["pagination"]
    assert all(k in p for k in ("total", "page", "per_page", "total_pages"))


async def test_list_single_pipeline(client):
    await client.post("/api/pipelines", json=QUICK_PAYLOAD)
    body = (await client.get("/api/pipelines")).json()
    assert len(body["data"]) == 1
    assert body["pagination"]["total"] == 1


async def test_list_pipelines_include_stages(client):
    await client.post("/api/pipelines", json=QUICK_PAYLOAD)
    pipeline = (await client.get("/api/pipelines")).json()["data"][0]
    assert "stages" in pipeline
    assert len(pipeline["stages"]) == 2


async def test_list_per_page_limits_results(client):
    for i in range(5):
        await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "name": f"P{i}"})

    r = await client.get("/api/pipelines?per_page=3&page=1")
    body = r.json()
    assert len(body["data"]) == 3
    assert body["pagination"]["total"] == 5
    assert body["pagination"]["total_pages"] == 2
    assert body["pagination"]["per_page"] == 3


async def test_list_page2_returns_remaining(client):
    for i in range(5):
        await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "name": f"P{i}"})

    r = await client.get("/api/pipelines?per_page=3&page=2")
    body = r.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["page"] == 2


async def test_list_filter_by_status_pending(client):
    await client.post("/api/pipelines", json=QUICK_PAYLOAD)
    body = (await client.get("/api/pipelines?status=pending")).json()
    assert body["pagination"]["total"] == 1
    assert all(p["status"] == "pending" for p in body["data"])


async def test_list_filter_by_status_no_match(client):
    await client.post("/api/pipelines", json=QUICK_PAYLOAD)
    body = (await client.get("/api/pipelines?status=running")).json()
    assert body["pagination"]["total"] == 0


async def test_list_filter_by_repository(client):
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/a"})
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/b"})
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/b"})

    body = (await client.get("/api/pipelines?repository=org/a")).json()
    assert body["pagination"]["total"] == 1

    body = (await client.get("/api/pipelines?repository=org/b")).json()
    assert body["pagination"]["total"] == 2


async def test_list_filter_by_branch(client):
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "branch": "main"})
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "branch": "develop"})

    body = (await client.get("/api/pipelines?branch=main")).json()
    assert body["pagination"]["total"] == 1


async def test_list_filter_combined(client):
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/a", "branch": "main"})
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/a", "branch": "dev"})
    await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "repository": "org/b", "branch": "main"})

    body = (await client.get("/api/pipelines?repository=org/a&branch=main")).json()
    assert body["pagination"]["total"] == 1


async def test_list_sort_order_desc_default(client):
    for i in range(3):
        await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "name": f"P{i}"})

    ids = [(p["id"]) for p in (await client.get("/api/pipelines")).json()["data"]]
    assert ids == sorted(ids, reverse=True)


async def test_list_sort_order_asc(client):
    for i in range(3):
        await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "name": f"P{i}"})

    ids = [(p["id"]) for p in (await client.get("/api/pipelines?sort_order=asc")).json()["data"]]
    assert ids == sorted(ids)


async def test_list_sort_by_name(client):
    for name in ["Zorro", "Alpha", "Mango"]:
        await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "name": name})

    names = [(p["name"]) for p in (await client.get("/api/pipelines?sort_by=name&sort_order=asc")).json()["data"]]
    assert names == sorted(names)


async def test_list_per_page_max_100(client, factory):
    # Insertar 105 pipelines directamente en DB (rápido)
    for _ in range(105):
        await insert_pipeline(factory)

    body = (await client.get("/api/pipelines?per_page=200")).json()
    assert len(body["data"]) == 100


# ── GET /api/pipelines/{id} ────────────────────────────────────────────────────

async def test_get_by_id_200(client):
    created = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r = await client.get(f"/api/pipelines/{created['id']}")
    assert r.status_code == 200


async def test_get_by_id_returns_correct_pipeline(client):
    created = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.get(f"/api/pipelines/{created['id']}")).json()
    assert data["id"] == created["id"]
    assert data["name"] == "My Pipeline"


async def test_get_by_id_includes_stages(client):
    created = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.get(f"/api/pipelines/{created['id']}")).json()
    assert len(data["stages"]) == 2


async def test_get_by_id_stages_ordered(client):
    created = (await client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "CI/CD Standard"})).json()
    data = (await client.get(f"/api/pipelines/{created['id']}")).json()
    orders = [s["order"] for s in data["stages"]]
    assert orders == sorted(orders)


async def test_get_by_id_all_fields_present(client):
    created = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.get(f"/api/pipelines/{created['id']}")).json()
    for field in ("id", "name", "repository", "branch", "trigger_type",
                  "status", "started_at", "finished_at", "duration_seconds",
                  "created_at", "stages"):
        assert field in data


async def test_get_by_id_not_found(client):
    r = await client.get("/api/pipelines/9999")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


# ── POST /api/pipelines/{id}/cancel ───────────────────────────────────────────

async def test_cancel_pending_returns_200(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r = await client.post(f"/api/pipelines/{p['id']}/cancel")
    assert r.status_code == 200


async def test_cancel_sets_status_cancelled(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.post(f"/api/pipelines/{p['id']}/cancel")).json()
    assert data["status"] == "cancelled"


async def test_cancel_sets_finished_at(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.post(f"/api/pipelines/{p['id']}/cancel")).json()
    assert data["finished_at"] is not None
    assert data["finished_at"].endswith("Z")


async def test_cancel_returns_full_pipeline_response(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    data = (await client.post(f"/api/pipelines/{p['id']}/cancel")).json()
    for field in ("id", "name", "status", "stages"):
        assert field in data


async def test_cancel_success_pipeline_returns_409(client, factory):
    p = await insert_pipeline(factory, status="success")
    r = await client.post(f"/api/pipelines/{p.id}/cancel")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_cancel_failed_pipeline_returns_409(client, factory):
    p = await insert_pipeline(factory, status="failed")
    r = await client.post(f"/api/pipelines/{p.id}/cancel")
    assert r.status_code == 409


async def test_cancel_already_cancelled_returns_409(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    r = await client.post(f"/api/pipelines/{p['id']}/cancel")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_cancel_not_found_returns_404(client):
    r = await client.post("/api/pipelines/9999/cancel")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


async def test_cancel_reflected_in_get(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    data = (await client.get(f"/api/pipelines/{p['id']}")).json()
    assert data["status"] == "cancelled"


# ── POST /api/pipelines/{id}/retry ────────────────────────────────────────────

async def test_retry_cancelled_returns_201(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    r = await client.post(f"/api/pipelines/{p['id']}/retry")
    assert r.status_code == 201


async def test_retry_failed_returns_201(client, factory):
    p = await insert_pipeline(factory, status="failed", template="Quick Test")
    r = await client.post(f"/api/pipelines/{p.id}/retry")
    assert r.status_code == 201


async def test_retry_creates_new_pipeline(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    assert new["id"] != p["id"]


async def test_retry_new_pipeline_is_pending(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    assert new["status"] == "pending"
    assert new["started_at"] is None


async def test_retry_preserves_name_repo_branch(client):
    payload = {**QUICK_PAYLOAD, "name": "Spec Pipeline", "repository": "org/special", "branch": "hotfix"}
    p = (await client.post("/api/pipelines", json=payload)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    assert new["name"] == "Spec Pipeline"
    assert new["repository"] == "org/special"
    assert new["branch"] == "hotfix"


async def test_retry_new_pipeline_has_same_stage_count(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    assert len(new["stages"]) == len(p["stages"])


async def test_retry_new_stages_are_pending(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    assert all(s["status"] == "pending" for s in new["stages"])


async def test_retry_original_pipeline_unchanged(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    await client.post(f"/api/pipelines/{p['id']}/retry")
    original = (await client.get(f"/api/pipelines/{p['id']}")).json()
    assert original["status"] == "cancelled"


async def test_retry_pending_returns_409(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r = await client.post(f"/api/pipelines/{p['id']}/retry")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_retry_success_returns_409(client, factory):
    p = await insert_pipeline(factory, status="success")
    r = await client.post(f"/api/pipelines/{p.id}/retry")
    assert r.status_code == 409


async def test_retry_not_found_returns_404(client):
    r = await client.post("/api/pipelines/9999/retry")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


async def test_retry_appears_in_list(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    new = (await client.post(f"/api/pipelines/{p['id']}/retry")).json()
    ids = [x["id"] for x in (await client.get("/api/pipelines")).json()["data"]]
    assert new["id"] in ids


# ── DELETE /api/pipelines/{id} ────────────────────────────────────────────────

async def test_delete_cancelled_returns_204(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    r = await client.delete(f"/api/pipelines/{p['id']}")
    assert r.status_code == 204


async def test_delete_success_returns_204(client, factory):
    p = await insert_pipeline(factory, status="success")
    r = await client.delete(f"/api/pipelines/{p.id}")
    assert r.status_code == 204


async def test_delete_failed_returns_204(client, factory):
    p = await insert_pipeline(factory, status="failed")
    r = await client.delete(f"/api/pipelines/{p.id}")
    assert r.status_code == 204


async def test_delete_pending_returns_409(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r = await client.delete(f"/api/pipelines/{p['id']}")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATE_TRANSITION"


async def test_delete_running_returns_409(client, factory):
    p = await insert_pipeline(factory, status="running")
    r = await client.delete(f"/api/pipelines/{p.id}")
    assert r.status_code == 409


async def test_delete_removes_from_db(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    await client.delete(f"/api/pipelines/{p['id']}")
    r = await client.get(f"/api/pipelines/{p['id']}")
    assert r.status_code == 404


async def test_delete_removed_from_list(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    await client.post(f"/api/pipelines/{p['id']}/cancel")
    await client.delete(f"/api/pipelines/{p['id']}")
    ids = [x["id"] for x in (await client.get("/api/pipelines")).json()["data"]]
    assert p["id"] not in ids


async def test_delete_not_found_returns_404(client):
    r = await client.delete("/api/pipelines/9999")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


# ── GET /api/pipelines/{id}/stages/{stage_id}/logs ────────────────────────────

async def test_logs_empty_before_simulation(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    stage = p["stages"][0]
    r = await client.get(f"/api/pipelines/{p['id']}/stages/{stage['id']}/logs")
    assert r.status_code == 200
    body = r.json()
    assert body["stage_id"] == stage["id"]
    assert body["stage_name"] == stage["name"]
    assert body["logs"] == []


async def test_logs_response_structure(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    stage = p["stages"][0]
    body = (await client.get(f"/api/pipelines/{p['id']}/stages/{stage['id']}/logs")).json()
    assert "stage_id" in body
    assert "stage_name" in body
    assert "logs" in body


async def test_logs_pipeline_not_found(client):
    r = await client.get("/api/pipelines/9999/stages/1/logs")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


async def test_logs_stage_not_found(client):
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    r = await client.get(f"/api/pipelines/{p['id']}/stages/9999/logs")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "RESOURCE_NOT_FOUND"


async def test_logs_stage_wrong_pipeline(client):
    """Stage perteneciente a otro pipeline debe dar 404."""
    p1 = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    p2 = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    stage_p2 = p2["stages"][0]["id"]
    r = await client.get(f"/api/pipelines/{p1['id']}/stages/{stage_p2}/logs")
    assert r.status_code == 404


async def test_logs_second_stage(client):
    """Verificar que también funciona con el segundo stage."""
    p = (await client.post("/api/pipelines", json=QUICK_PAYLOAD)).json()
    stage = p["stages"][1]
    r = await client.get(f"/api/pipelines/{p['id']}/stages/{stage['id']}/logs")
    assert r.status_code == 200
    assert r.json()["stage_name"] == stage["name"]


# ── Tests con simulación real (speed_multiplier=100) ──────────────────────────

async def test_sim_pipeline_reaches_success(sim_client):
    """Pipeline completo debe terminar en success."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0  # nunca falla
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        assert data["status"] == "success"
        assert data["finished_at"] is not None
        assert data["duration_seconds"] is not None
    finally:
        sim_module.random.random = orig


async def test_sim_all_stages_success(sim_client):
    """Todos los stages deben quedar en success al completar."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        assert all(s["status"] == "success" for s in data["stages"])
    finally:
        sim_module.random.random = orig


async def test_sim_pipeline_can_fail(sim_client):
    """Con random=0, el primer stage siempre falla."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 0.0  # siempre falla
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        assert data["status"] == "failed"
        assert data["stages"][0]["status"] == "failed"
        assert data["stages"][1]["status"] == "pending"
    finally:
        sim_module.random.random = orig


async def test_sim_logs_populated_after_run(sim_client):
    """Los logs deben existir en la DB después de la simulación."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        p = r.json()
        pid = p["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        for stage in data["stages"]:
            logs_r = await sim_client.client.get(
                f"/api/pipelines/{pid}/stages/{stage['id']}/logs"
            )
            assert logs_r.status_code == 200
            logs = logs_r.json()["logs"]
            assert len(logs) >= 1, f"Stage '{stage['name']}' sin logs"
    finally:
        sim_module.random.random = orig


async def test_sim_log_entries_have_correct_fields(sim_client):
    """Cada log debe tener id, timestamp, level y message."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        stage_id = data["stages"][0]["id"]
        logs = (await sim_client.client.get(
            f"/api/pipelines/{pid}/stages/{stage_id}/logs"
        )).json()["logs"]
        for log in logs:
            assert "id" in log
            assert "timestamp" in log
            assert "level" in log
            assert "message" in log
            assert log["timestamp"].endswith("Z")
    finally:
        sim_module.random.random = orig


async def test_sim_log_timestamps_have_z(sim_client):
    """Los timestamps de logs deben terminar en Z."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        stage_id = data["stages"][0]["id"]
        logs = (await sim_client.client.get(
            f"/api/pipelines/{pid}/stages/{stage_id}/logs"
        )).json()["logs"]
        assert all(log["timestamp"].endswith("Z") for log in logs)
    finally:
        sim_module.random.random = orig


async def test_sim_websocket_broadcasts_sent(sim_client):
    """El simulador debe emitir mensajes WebSocket."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        await asyncio.sleep(0.8)
        call_types = {c.args[0]["type"] for c in sim_client.ws.broadcast.call_args_list}
        assert "pipeline_update" in call_types
        assert "pipeline_completed" in call_types
        assert "log_entry" in call_types
    finally:
        sim_module.random.random = orig


async def test_sim_pipeline_completed_ws_message(sim_client):
    """El mensaje pipeline_completed debe tener status success."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        await asyncio.sleep(0.8)
        calls = [c.args[0] for c in sim_client.ws.broadcast.call_args_list]
        completed = next(c for c in calls if c["type"] == "pipeline_completed")
        assert completed["data"]["status"] == "success"
        assert completed["data"]["duration_seconds"] is not None
        assert completed["data"]["finished_at"] is not None
    finally:
        sim_module.random.random = orig


async def test_sim_stages_run_sequentially(sim_client):
    """Los stages deben ejecutarse en orden: stage N termina antes de que N+1 empiece."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        r = await sim_client.client.post("/api/pipelines", json={**QUICK_PAYLOAD, "template": "CI/CD Standard"})
        pid = r.json()["id"]
        await asyncio.sleep(2.0)
        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        stages = sorted(data["stages"], key=lambda s: s["order"])
        for i in range(len(stages) - 1):
            assert stages[i]["finished_at"] is not None
            assert stages[i + 1]["started_at"] is not None
            assert stages[i]["finished_at"] <= stages[i + 1]["started_at"]
    finally:
        sim_module.random.random = orig


async def test_sim_cancel_stops_future_stages(sim_client):
    """Cancelar durante la ejecución deja los stages futuros en pending."""
    orig = sim_module.random.random
    sim_module.random.random = lambda: 1.0
    try:
        # Full Deploy tiene 10 stages — hay tiempo de cancelar
        r = await sim_client.client.post("/api/pipelines",
                                         json={**QUICK_PAYLOAD, "template": "Full Deploy"})
        pid = r.json()["id"]
        await asyncio.sleep(0.05)  # Dejar arrancar
        await sim_client.client.post(f"/api/pipelines/{pid}/cancel")
        await asyncio.sleep(0.3)

        data = (await sim_client.client.get(f"/api/pipelines/{pid}")).json()
        assert data["status"] == "cancelled"
        # Al menos algunos stages deben seguir pending
        pending = [s for s in data["stages"] if s["status"] == "pending"]
        assert len(pending) > 0
    finally:
        sim_module.random.random = orig


async def test_sim_retry_reruns_pipeline(sim_client):
    """Retry de un pipeline fallido debe crear uno nuevo que complete."""
    orig = sim_module.random.random
    # Primera ejecución: falla
    sim_module.random.random = lambda: 0.0
    try:
        r = await sim_client.client.post("/api/pipelines", json=QUICK_PAYLOAD)
        pid = r.json()["id"]
        await asyncio.sleep(0.8)
        assert (await sim_client.client.get(f"/api/pipelines/{pid}")).json()["status"] == "failed"

        # Segunda ejecución (retry): éxito
        sim_module.random.random = lambda: 1.0
        new_r = await sim_client.client.post(f"/api/pipelines/{pid}/retry")
        new_pid = new_r.json()["id"]
        await asyncio.sleep(0.8)
        new_data = (await sim_client.client.get(f"/api/pipelines/{new_pid}")).json()
        assert new_data["status"] == "success"
    finally:
        sim_module.random.random = orig
