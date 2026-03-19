"""Fixtures compartidos para los tests del backend."""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Pipeline, Stage

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest_asyncio.fixture
async def db_engine():
    """Engine SQLite en memoria para tests de simulador."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    """Session factory que usa el engine de tests (para test_simulator)."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return factory


async def insert_pipeline(
    factory,
    *,
    name: str = "Test P",
    repository: str = "org/repo",
    branch: str = "main",
    trigger_type: str = "manual",
    template: str = "Quick Test",
    status: str = "pending",
    duration: int | None = None,
    num_stages: int = 2,
) -> Pipeline:
    """Inserta un pipeline directamente en la DB (sin pasar por la API)."""
    async with factory() as db:
        p = Pipeline(
            name=name,
            repository=repository,
            branch=branch,
            trigger_type=trigger_type,
            template=template,
            status=status,
            created_at=_now(),
            duration_seconds=duration,
            started_at=_now() if status != "pending" else None,
            finished_at=_now() if status in ("success", "failed", "cancelled") else None,
        )
        db.add(p)
        await db.flush()
        for i in range(1, num_stages + 1):
            db.add(Stage(pipeline_id=p.id, name=f"Stage {i}", order=i, status="pending"))
        await db.commit()
        return p
