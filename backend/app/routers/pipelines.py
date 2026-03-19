"""Router para los endpoints /api/pipelines."""

import asyncio
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_session
from app.dependencies import get_ws_manager
from app.models import LogEntry, Pipeline, Stage
from app.schemas import (
    PaginationInfo,
    PipelineCreate,
    PipelineListResponse,
    PipelineResponse,
    StageLogsResponse,
    LogEntryResponse,
)
from app.simulator import PIPELINE_TEMPLATES, simulate_pipeline
from app.websocket_manager import WebSocketManager

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

VALID_TEMPLATES = set(PIPELINE_TEMPLATES.keys())
SORT_COLUMNS = {"created_at", "started_at", "name"}
TERMINAL_STATUSES = {"success", "failed", "cancelled"}
ACTIVE_STATUSES = {"pending", "running"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _not_found(msg: str = "Pipeline no encontrado") -> HTTPException:
    return HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": msg})


def _conflict(msg: str = "Transición de estado inválida") -> HTTPException:
    return HTTPException(
        status_code=409, detail={"code": "INVALID_STATE_TRANSITION", "message": msg}
    )


async def _get_pipeline_with_stages(db: AsyncSession, pipeline_id: int) -> Pipeline:
    """Carga un pipeline con sus stages o lanza 404."""
    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.stages))
    )
    pipeline = result.scalar_one_or_none()
    if pipeline is None:
        raise _not_found()
    return pipeline


# ── POST /api/pipelines ────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=PipelineResponse)
async def create_pipeline(
    data: PipelineCreate,
    db: AsyncSession = Depends(get_session),
    ws_manager: WebSocketManager = Depends(get_ws_manager),
) -> Pipeline:
    """Crea un pipeline y dispara la simulación en background."""
    if data.template not in VALID_TEMPLATES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_FIELD_VALUE",
                "field": "template",
                "message": f"template debe ser uno de: {sorted(VALID_TEMPLATES)}",
            },
        )

    pipeline = Pipeline(
        name=data.name,
        repository=data.repository,
        branch=data.branch,
        trigger_type=data.trigger_type,
        template=data.template,
        status="pending",
        created_at=_now(),
    )
    db.add(pipeline)
    await db.flush()

    for stage_def in PIPELINE_TEMPLATES[data.template]["stages"]:
        db.add(Stage(
            pipeline_id=pipeline.id,
            name=stage_def["name"],
            order=stage_def["order"],
            status="pending",
        ))

    await db.commit()

    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline.id)
        .options(selectinload(Pipeline.stages))
    )
    pipeline = result.scalar_one()

    asyncio.create_task(
        simulate_pipeline(pipeline.id, AsyncSessionLocal, ws_manager)
    )

    return pipeline


# ── GET /api/pipelines ─────────────────────────────────────────────────────────

@router.get("", response_model=PipelineListResponse)
async def list_pipelines(
    page: int = 1,
    per_page: int = 10,
    status: str | None = None,
    repository: str | None = None,
    branch: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_session),
) -> PipelineListResponse:
    """Lista pipelines con paginación y filtros opcionales."""
    if per_page > 100:
        per_page = 100
    if per_page < 1:
        per_page = 1
    if page < 1:
        page = 1
    if sort_by not in SORT_COLUMNS:
        sort_by = "created_at"

    query = select(Pipeline).options(selectinload(Pipeline.stages))

    if status:
        query = query.where(Pipeline.status == status)
    if repository:
        query = query.where(Pipeline.repository == repository)
    if branch:
        query = query.where(Pipeline.branch == branch)

    col = getattr(Pipeline, sort_by)
    query = query.order_by(col.desc() if sort_order == "desc" else col.asc())

    total: int = await db.scalar(
        select(func.count(Pipeline.id)).where(
            *([Pipeline.status == status] if status else []),
            *([Pipeline.repository == repository] if repository else []),
            *([Pipeline.branch == branch] if branch else []),
        )
    ) or 0

    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    pipelines = result.scalars().all()

    return PipelineListResponse(
        data=pipelines,
        pagination=PaginationInfo(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total > 0 else 1,
        ),
    )


# ── GET /api/pipelines/{id} ────────────────────────────────────────────────────

@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: int,
    db: AsyncSession = Depends(get_session),
) -> Pipeline:
    """Obtiene un pipeline con todos sus stages."""
    return await _get_pipeline_with_stages(db, pipeline_id)


# ── POST /api/pipelines/{id}/cancel ───────────────────────────────────────────

@router.post("/{pipeline_id}/cancel", response_model=PipelineResponse)
async def cancel_pipeline(
    pipeline_id: int,
    db: AsyncSession = Depends(get_session),
) -> Pipeline:
    """Cancela un pipeline en ejecución o pendiente."""
    pipeline = await _get_pipeline_with_stages(db, pipeline_id)

    if pipeline.status in TERMINAL_STATUSES:
        raise _conflict(f"No se puede cancelar un pipeline con status '{pipeline.status}'")

    pipeline.status = "cancelled"
    pipeline.finished_at = _now()
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


# ── POST /api/pipelines/{id}/retry ────────────────────────────────────────────

@router.post("/{pipeline_id}/retry", status_code=201, response_model=PipelineResponse)
async def retry_pipeline(
    pipeline_id: int,
    db: AsyncSession = Depends(get_session),
    ws_manager: WebSocketManager = Depends(get_ws_manager),
) -> Pipeline:
    """Re-ejecuta un pipeline fallido o cancelado creando uno nuevo."""
    original = await _get_pipeline_with_stages(db, pipeline_id)

    if original.status not in {"failed", "cancelled"}:
        raise _conflict(
            f"Solo se puede reintentar un pipeline con status 'failed' o 'cancelled', "
            f"no '{original.status}'"
        )

    new_pipeline = Pipeline(
        name=original.name,
        repository=original.repository,
        branch=original.branch,
        trigger_type=original.trigger_type,
        template=original.template,
        status="pending",
        created_at=_now(),
    )
    db.add(new_pipeline)
    await db.flush()

    template = PIPELINE_TEMPLATES.get(original.template, {})
    for stage_def in template.get("stages", []):
        db.add(Stage(
            pipeline_id=new_pipeline.id,
            name=stage_def["name"],
            order=stage_def["order"],
            status="pending",
        ))

    await db.commit()

    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == new_pipeline.id)
        .options(selectinload(Pipeline.stages))
    )
    new_pipeline = result.scalar_one()

    asyncio.create_task(
        simulate_pipeline(new_pipeline.id, AsyncSessionLocal, ws_manager)
    )

    return new_pipeline


# ── DELETE /api/pipelines/{id} ────────────────────────────────────────────────

@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: int,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Elimina un pipeline terminado (success, failed o cancelled)."""
    pipeline = await _get_pipeline_with_stages(db, pipeline_id)

    if pipeline.status in ACTIVE_STATUSES:
        raise _conflict(
            f"No se puede eliminar un pipeline con status '{pipeline.status}'"
        )

    await db.delete(pipeline)
    await db.commit()


# ── GET /api/pipelines/{id}/stages/{stage_id}/logs ────────────────────────────

@router.get(
    "/{pipeline_id}/stages/{stage_id}/logs",
    response_model=StageLogsResponse,
)
async def get_stage_logs(
    pipeline_id: int,
    stage_id: int,
    db: AsyncSession = Depends(get_session),
) -> StageLogsResponse:
    """Obtiene los logs de un stage específico."""
    # Verificar que el pipeline existe
    pipeline_exists = await db.scalar(
        select(func.count(Pipeline.id)).where(Pipeline.id == pipeline_id)
    )
    if not pipeline_exists:
        raise _not_found("Pipeline no encontrado")

    # Verificar que el stage existe y pertenece al pipeline
    result = await db.execute(
        select(Stage)
        .where(Stage.id == stage_id, Stage.pipeline_id == pipeline_id)
        .options(selectinload(Stage.log_entries))
    )
    stage = result.scalar_one_or_none()
    if stage is None:
        raise _not_found("Stage no encontrado o no pertenece a este pipeline")

    return StageLogsResponse(
        stage_id=stage.id,
        stage_name=stage.name,
        logs=[
            LogEntryResponse.model_validate(log)
            for log in sorted(stage.log_entries, key=lambda l: l.timestamp)
        ],
    )
