"""Tests para el simulador de pipelines."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import LogEntry, Pipeline, Stage
from app.simulator import PIPELINE_TEMPLATES, simulate_pipeline
from app.websocket_manager import WebSocketManager

pytestmark = pytest.mark.asyncio


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _create_pipeline(db_session_factory, template_name: str = "Quick Test") -> Pipeline:
    """Crea un pipeline con sus stages en la DB usando el template indicado."""
    template = PIPELINE_TEMPLATES[template_name]
    async with db_session_factory() as db:
        pipeline = Pipeline(
            name="Test Pipeline",
            repository="org/test-repo",
            branch="main",
            trigger_type="manual",
            status="pending",
            created_at=_now_utc(),
        )
        db.add(pipeline)
        await db.flush()

        for stage_def in template["stages"]:
            stage = Stage(
                pipeline_id=pipeline.id,
                name=stage_def["name"],
                order=stage_def["order"],
                status="pending",
            )
            db.add(stage)

        await db.commit()
        await db.refresh(pipeline)
        return pipeline


async def _load_pipeline(db_session_factory, pipeline_id: int) -> Pipeline:
    """Carga el pipeline con stages y logs desde la DB."""
    async with db_session_factory() as db:
        result = await db.execute(
            select(Pipeline)
            .where(Pipeline.id == pipeline_id)
            .options(
                selectinload(Pipeline.stages).selectinload(Stage.log_entries)
            )
        )
        return result.scalar_one()


def _make_ws_manager() -> WebSocketManager:
    """WebSocketManager con broadcast mockeado (no hay clientes reales)."""
    manager = WebSocketManager()
    manager.broadcast = AsyncMock()
    return manager


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_stages_execute_in_order(db_session_factory):
    """Los stages deben completarse en orden ascendente por `order`."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    # Forzar siempre éxito
    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0  # 1.0 > 0.10 → nunca falla

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    stages = sorted(loaded.stages, key=lambda s: s.order)

    assert stages[0].order == 1
    assert stages[1].order == 2
    # El segundo stage no puede haber empezado antes que el primero terminara
    assert stages[0].finished_at is not None
    assert stages[1].started_at is not None
    assert stages[0].finished_at <= stages[1].started_at


async def test_pipeline_success_all_stages(db_session_factory):
    """Cuando ningún stage falla, el pipeline termina en success."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)

    assert loaded.status == "success"
    assert loaded.started_at is not None
    assert loaded.finished_at is not None
    assert loaded.duration_seconds is not None and loaded.duration_seconds >= 1

    for stage in loaded.stages:
        assert stage.status == "success"
        assert stage.started_at is not None
        assert stage.finished_at is not None
        assert stage.duration_seconds is not None and stage.duration_seconds >= 1


async def test_pipeline_fails_on_first_stage(db_session_factory):
    """Cuando el primer stage falla, el pipeline termina en failed y los demás quedan pending."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 0.0  # 0.0 < 0.10 → siempre falla

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    stages = sorted(loaded.stages, key=lambda s: s.order)

    assert loaded.status == "failed"
    assert loaded.finished_at is not None
    assert stages[0].status == "failed"
    assert stages[1].status == "pending"


async def test_logs_generated_per_stage(db_session_factory):
    """Cada stage debe generar al menos un log durante su ejecución."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    for stage in loaded.stages:
        assert len(stage.log_entries) >= 1, (
            f"Stage '{stage.name}' no generó logs"
        )


async def test_log_levels_are_valid(db_session_factory):
    """Los logs deben tener level info o error."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    valid_levels = {"info", "warning", "error"}
    for stage in loaded.stages:
        for log in stage.log_entries:
            assert log.level in valid_levels


async def test_websocket_broadcasts_pipeline_update(db_session_factory):
    """El simulador debe emitir mensajes pipeline_update por cada cambio de stage."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    calls = [call.args[0] for call in ws.broadcast.call_args_list]
    update_types = [c["type"] for c in calls]

    assert "pipeline_update" in update_types
    assert "pipeline_completed" in update_types
    assert "log_entry" in update_types


async def test_websocket_pipeline_completed_message(db_session_factory):
    """El mensaje pipeline_completed debe contener status, duration_seconds y finished_at."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    calls = [call.args[0] for call in ws.broadcast.call_args_list]
    completed = next(c for c in calls if c["type"] == "pipeline_completed")

    assert completed["pipeline_id"] == pipeline.id
    assert completed["data"]["status"] == "success"
    assert completed["data"]["duration_seconds"] is not None
    assert completed["data"]["finished_at"] is not None


async def test_pipeline_started_at_set(db_session_factory):
    """El pipeline debe tener started_at seteado al arrancar."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    assert loaded.started_at is not None
    assert loaded.status == "success"


async def test_speed_multiplier_accelerates_execution(db_session_factory):
    """Con speed_multiplier alto, el pipeline completo debe terminar en menos de 2 segundos."""
    import time

    pipeline = await _create_pipeline(db_session_factory, "CI/CD Standard")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 1.0

    start = time.monotonic()
    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"El simulador tardó {elapsed:.2f}s con speed_multiplier=100"


async def test_failed_stage_generates_error_log(db_session_factory):
    """Un stage fallido debe tener al menos un log con level='error'."""
    pipeline = await _create_pipeline(db_session_factory, "Quick Test")
    ws = _make_ws_manager()

    import app.simulator as sim_module
    original_random = sim_module.random.random
    sim_module.random.random = lambda: 0.0

    try:
        await simulate_pipeline(
            pipeline.id, db_session_factory, ws, speed_multiplier=100.0
        )
    finally:
        sim_module.random.random = original_random

    loaded = await _load_pipeline(db_session_factory, pipeline.id)
    failed_stage = next(s for s in loaded.stages if s.status == "failed")
    error_logs = [l for l in failed_stage.log_entries if l.level == "error"]
    assert len(error_logs) >= 1
