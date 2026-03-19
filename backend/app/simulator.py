"""Simulador de ejecución de pipelines CI/CD."""

import asyncio
import logging
import random
import string
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import LogEntry, Pipeline, Stage
from app.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# ── Templates de pipeline ──────────────────────────────────────────────────────

PIPELINE_TEMPLATES: dict[str, dict] = {
    "CI/CD Standard": {
        "name": "CI/CD Standard",
        "stages": [
            {"name": "Checkout", "order": 1, "simulated_duration_range": [2, 5]},
            {"name": "Install Dependencies", "order": 2, "simulated_duration_range": [5, 15]},
            {"name": "Lint", "order": 3, "simulated_duration_range": [3, 8]},
            {"name": "Unit Tests", "order": 4, "simulated_duration_range": [10, 30]},
            {"name": "Build", "order": 5, "simulated_duration_range": [8, 20]},
            {"name": "Deploy", "order": 6, "simulated_duration_range": [5, 15]},
        ],
    },
    "Quick Test": {
        "name": "Quick Test",
        "stages": [
            {"name": "Checkout", "order": 1, "simulated_duration_range": [1, 3]},
            {"name": "Test", "order": 2, "simulated_duration_range": [5, 10]},
        ],
    },
    "Full Deploy": {
        "name": "Full Deploy",
        "stages": [
            {"name": "Checkout", "order": 1, "simulated_duration_range": [2, 4]},
            {"name": "Install", "order": 2, "simulated_duration_range": [5, 12]},
            {"name": "Lint & Format", "order": 3, "simulated_duration_range": [3, 6]},
            {"name": "Unit Tests", "order": 4, "simulated_duration_range": [10, 25]},
            {"name": "Integration Tests", "order": 5, "simulated_duration_range": [15, 40]},
            {"name": "Build Docker Image", "order": 6, "simulated_duration_range": [10, 20]},
            {"name": "Push to Registry", "order": 7, "simulated_duration_range": [5, 10]},
            {"name": "Deploy to Staging", "order": 8, "simulated_duration_range": [8, 15]},
            {"name": "Smoke Tests", "order": 9, "simulated_duration_range": [5, 10]},
            {"name": "Deploy to Production", "order": 10, "simulated_duration_range": [8, 15]},
        ],
    },
}

# ── Mensajes de log simulados por stage ───────────────────────────────────────

SIMULATED_LOGS: dict[str, list[str]] = {
    "Checkout": [
        "Cloning repository...",
        "Fetching branch {branch}...",
        "Checkout complete. HEAD at {commit_hash}",
    ],
    "Install Dependencies": [
        "Reading package.json...",
        "Installing 142 packages...",
        "Dependencies installed successfully",
    ],
    "Lint": [
        "Running ESLint on 85 files...",
        "No linting errors found",
    ],
    "Unit Tests": [
        "Discovering test suites...",
        "Running 234 tests across 12 suites...",
        "All tests passed (234/234)",
    ],
    "Build": [
        "Compiling TypeScript...",
        "Bundling with webpack...",
        "Build output: 2.4MB (gzipped: 680KB)",
    ],
    "Deploy": [
        "Connecting to cluster...",
        "Applying Kubernetes manifests...",
        "Deployment rolled out successfully",
    ],
}

_GENERIC_LOGS = ["Starting...", "Processing...", "Done."]

FAILURE_PROBABILITY = 0.10


# ── Helpers ────────────────────────────────────────────────────────────────────

def _random_commit_hash() -> str:
    """Genera un hash de commit simulado de 7 caracteres."""
    return "".join(random.choices(string.hexdigits[:16], k=7))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_stage_logs(stage_name: str, branch: str) -> list[str]:
    """Retorna los mensajes de log para un stage dado."""
    templates = SIMULATED_LOGS.get(stage_name, _GENERIC_LOGS)
    return [
        msg.format(branch=branch, commit_hash=_random_commit_hash())
        for msg in templates
    ]


def _build_stages_summary(stages: list[Stage]) -> list[dict]:
    return [
        {"id": s.id, "name": s.name, "order": s.order, "status": s.status}
        for s in stages
    ]


# ── Simulador principal ────────────────────────────────────────────────────────

async def simulate_pipeline(
    pipeline_id: int,
    db_session_factory,
    ws_manager: WebSocketManager,
    speed_multiplier: float = 1.0,
) -> None:
    """Simula la ejecución completa de un pipeline, stage por stage.

    Cambia estados en la DB, genera logs y emite mensajes WebSocket
    según la spec. El parámetro speed_multiplier divide los tiempos
    de espera para acelerar la simulación en tests.
    """
    async with db_session_factory() as db:
        # Cargar pipeline con stages
        result = await db.execute(
            select(Pipeline)
            .where(Pipeline.id == pipeline_id)
            .options(selectinload(Pipeline.stages))
        )
        pipeline = result.scalar_one_or_none()
        if pipeline is None:
            logger.error("Pipeline %d no encontrado en el simulador.", pipeline_id)
            return

        # Verificar que no fue cancelado antes de arrancar
        if pipeline.status == "cancelled":
            return

        # 1. Pipeline → running
        pipeline.status = "running"
        pipeline.started_at = _now_utc()
        await db.commit()
        await db.refresh(pipeline)

        stages = sorted(pipeline.stages, key=lambda s: s.order)

        for stage in stages:
            # Verificar cancelación entre stages
            await db.refresh(pipeline)
            if pipeline.status == "cancelled":
                logger.info("Pipeline %d cancelado; deteniendo simulación.", pipeline_id)
                return

            # 2a. Stage → running
            stage.status = "running"
            stage.started_at = _now_utc()
            await db.commit()

            # 2b. Enviar pipeline_update (stage iniciando)
            await ws_manager.broadcast({
                "type": "pipeline_update",
                "pipeline_id": pipeline_id,
                "data": {
                    "status": pipeline.status,
                    "current_stage": {
                        "id": stage.id,
                        "name": stage.name,
                        "order": stage.order,
                        "status": stage.status,
                    },
                    "stages_summary": _build_stages_summary(stages),
                },
            })

            # 2c. Generar y emitir logs durante la ejecución
            log_messages = _get_stage_logs(stage.name, pipeline.branch)
            duration_range = _get_stage_duration_range(pipeline, stage)
            total_duration = random.uniform(*duration_range) / speed_multiplier
            delay_per_log = total_duration / max(len(log_messages), 1)

            for msg in log_messages:
                await asyncio.sleep(delay_per_log)

                # Verificar cancelación durante la ejecución del stage
                await db.refresh(pipeline)
                if pipeline.status == "cancelled":
                    return

                log_ts = _now_utc()
                log_entry = LogEntry(
                    stage_id=stage.id,
                    timestamp=log_ts,
                    level="info",
                    message=msg,
                )
                db.add(log_entry)
                await db.commit()

                await ws_manager.broadcast({
                    "type": "log_entry",
                    "pipeline_id": pipeline_id,
                    "stage_id": stage.id,
                    "data": {
                        "timestamp": log_ts.isoformat() + "Z",
                        "level": "info",
                        "message": msg,
                    },
                })

            # 2e. Decidir éxito o fallo
            failed = random.random() < FAILURE_PROBABILITY
            finished_ts = _now_utc()
            stage.finished_at = finished_ts
            stage.duration_seconds = max(
                1, int((finished_ts - stage.started_at).total_seconds())
            )

            if failed:
                stage.status = "failed"
                pipeline.status = "failed"
                pipeline.finished_at = finished_ts
                pipeline.duration_seconds = max(
                    1, int((finished_ts - pipeline.started_at).total_seconds())
                )

                # Log de fallo
                fail_log = LogEntry(
                    stage_id=stage.id,
                    timestamp=finished_ts,
                    level="error",
                    message=f"{stage.name} failed",
                )
                db.add(fail_log)
                await db.commit()

                await ws_manager.broadcast({
                    "type": "log_entry",
                    "pipeline_id": pipeline_id,
                    "stage_id": stage.id,
                    "data": {
                        "timestamp": finished_ts.isoformat() + "Z",
                        "level": "error",
                        "message": f"{stage.name} failed",
                    },
                })

                # 2f. pipeline_update con estado fallido
                await ws_manager.broadcast({
                    "type": "pipeline_update",
                    "pipeline_id": pipeline_id,
                    "data": {
                        "status": pipeline.status,
                        "current_stage": {
                            "id": stage.id,
                            "name": stage.name,
                            "order": stage.order,
                            "status": stage.status,
                        },
                        "stages_summary": _build_stages_summary(stages),
                    },
                })

                # 5. pipeline_completed
                await ws_manager.broadcast({
                    "type": "pipeline_completed",
                    "pipeline_id": pipeline_id,
                    "data": {
                        "status": pipeline.status,
                        "duration_seconds": pipeline.duration_seconds,
                        "finished_at": pipeline.finished_at.isoformat() + "Z",
                    },
                })
                return

            # Stage completado con éxito
            stage.status = "success"
            await db.commit()

            # Log de completado
            success_log = LogEntry(
                stage_id=stage.id,
                timestamp=finished_ts,
                level="info",
                message=f"{stage.name} completed",
            )
            db.add(success_log)
            await db.commit()

            await ws_manager.broadcast({
                "type": "log_entry",
                "pipeline_id": pipeline_id,
                "stage_id": stage.id,
                "data": {
                    "timestamp": finished_ts.isoformat() + "Z",
                    "level": "info",
                    "message": f"{stage.name} completed",
                },
            })

            # 2f. pipeline_update con stage completado
            await ws_manager.broadcast({
                "type": "pipeline_update",
                "pipeline_id": pipeline_id,
                "data": {
                    "status": pipeline.status,
                    "current_stage": {
                        "id": stage.id,
                        "name": stage.name,
                        "order": stage.order,
                        "status": stage.status,
                    },
                    "stages_summary": _build_stages_summary(stages),
                },
            })

        # 3. Todos los stages completaron con éxito
        finished_ts = _now_utc()
        pipeline.status = "success"
        pipeline.finished_at = finished_ts
        pipeline.duration_seconds = max(
            1, int((finished_ts - pipeline.started_at).total_seconds())
        )
        await db.commit()

        # 5. pipeline_completed
        await ws_manager.broadcast({
            "type": "pipeline_completed",
            "pipeline_id": pipeline_id,
            "data": {
                "status": pipeline.status,
                "duration_seconds": pipeline.duration_seconds,
                "finished_at": pipeline.finished_at.isoformat() + "Z",
            },
        })


def _get_stage_duration_range(pipeline: Pipeline, stage: Stage) -> tuple[float, float]:
    """Obtiene el rango de duración del stage según el template del pipeline.

    Si no se puede determinar el template, usa un rango genérico de [2, 5].
    """
    for template in PIPELINE_TEMPLATES.values():
        for stage_def in template["stages"]:
            if stage_def["name"] == stage.name and stage_def["order"] == stage.order:
                low, high = stage_def["simulated_duration_range"]
                return float(low), float(high)
    return 2.0, 5.0
