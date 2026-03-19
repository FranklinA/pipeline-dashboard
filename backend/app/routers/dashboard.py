"""Router para el endpoint /api/dashboard."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Pipeline
from app.schemas import (
    DashboardResponse,
    DashboardSummary,
    StatusSummary,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_ALL_STATUSES = ("pending", "running", "success", "failed", "cancelled")


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_session)) -> DashboardResponse:
    """Retorna estadísticas globales del dashboard."""

    # Total de pipelines
    total: int = await db.scalar(select(func.count(Pipeline.id))) or 0

    # Conteo por status
    rows = (await db.execute(
        select(Pipeline.status, func.count(Pipeline.id)).group_by(Pipeline.status)
    )).all()
    counts = {row[0]: row[1] for row in rows}
    by_status = StatusSummary(**{s: counts.get(s, 0) for s in _ALL_STATUSES})

    # Últimos 5 pipelines (con stages para el response completo)
    recent_result = await db.execute(
        select(Pipeline)
        .options(selectinload(Pipeline.stages))
        .order_by(Pipeline.created_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()

    # Duración promedio de pipelines exitosos
    avg_dur: float | None = await db.scalar(
        select(func.avg(Pipeline.duration_seconds)).where(Pipeline.status == "success")
    )

    # Tasa de éxito: success / (success + failed + cancelled)
    total_finished: int = await db.scalar(
        select(func.count(Pipeline.id)).where(
            Pipeline.status.in_(["success", "failed", "cancelled"])
        )
    ) or 0
    success_count: int = counts.get("success", 0)
    success_rate: float | None = (
        round(success_count / total_finished * 100, 1) if total_finished > 0 else None
    )

    return DashboardResponse(
        summary=DashboardSummary(total_pipelines=total, by_status=by_status),
        recent_pipelines=recent,
        avg_duration_seconds=round(avg_dur, 1) if avg_dur is not None else None,
        success_rate_percent=success_rate,
    )
