"""Pydantic schemas para el Pipeline Dashboard."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer


# ── Tipos con serialización UTC+Z ─────────────────────────────────────────────

def _fmt_utc(v: datetime | None) -> str | None:
    if v is None:
        return None
    return v.strftime("%Y-%m-%dT%H:%M:%SZ")


UTCDatetime = Annotated[datetime, PlainSerializer(_fmt_utc, return_type=str)]
OptUTCDatetime = Annotated[
    datetime | None, PlainSerializer(_fmt_utc, return_type=str | None)
]


# ── Stage schemas ──────────────────────────────────────────────────────────────

class StageResponse(BaseModel):
    """Schema de respuesta para un stage."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    order: int
    status: str
    started_at: OptUTCDatetime
    finished_at: OptUTCDatetime
    duration_seconds: int | None


# ── Pipeline schemas ───────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    """Schema para crear un pipeline."""

    name: str
    repository: str
    branch: str
    trigger_type: str
    template: str


class PipelineResponse(BaseModel):
    """Schema de respuesta completa de un pipeline con sus stages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repository: str
    branch: str
    trigger_type: str
    status: str
    started_at: OptUTCDatetime
    finished_at: OptUTCDatetime
    duration_seconds: int | None
    created_at: UTCDatetime
    stages: list[StageResponse]


class PaginationInfo(BaseModel):
    """Información de paginación."""

    total: int
    page: int
    per_page: int
    total_pages: int


class PipelineListResponse(BaseModel):
    """Schema de respuesta para lista paginada de pipelines."""

    data: list[PipelineResponse]
    pagination: PaginationInfo


# ── Dashboard schemas ──────────────────────────────────────────────────────────

class StatusSummary(BaseModel):
    """Conteo de pipelines por status."""

    pending: int
    running: int
    success: int
    failed: int
    cancelled: int


class DashboardSummary(BaseModel):
    """Resumen general del dashboard."""

    total_pipelines: int
    by_status: StatusSummary


class DashboardResponse(BaseModel):
    """Schema de respuesta del dashboard."""

    summary: DashboardSummary
    recent_pipelines: list[PipelineResponse]
    avg_duration_seconds: float | None
    success_rate_percent: float | None


# ── LogEntry schemas ───────────────────────────────────────────────────────────

class LogEntryResponse(BaseModel):
    """Schema de respuesta para una entrada de log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: UTCDatetime
    level: str
    message: str


class StageLogsResponse(BaseModel):
    """Schema de respuesta para los logs de un stage."""

    stage_id: int
    stage_name: str
    logs: list[LogEntryResponse]


# ── WebSocket message schemas ──────────────────────────────────────────────────

class StageSummary(BaseModel):
    """Resumen de un stage para mensajes WebSocket."""

    id: int
    name: str
    order: int
    status: str


class WsPipelineUpdateData(BaseModel):
    """Datos del mensaje pipeline_update."""

    status: str
    current_stage: StageSummary | None
    stages_summary: list[StageSummary]


class WsPipelineCompletedData(BaseModel):
    """Datos del mensaje pipeline_completed."""

    status: str
    duration_seconds: int | None
    finished_at: UTCDatetime


class WsLogEntryData(BaseModel):
    """Datos del mensaje log_entry."""

    timestamp: UTCDatetime
    level: str
    message: str
