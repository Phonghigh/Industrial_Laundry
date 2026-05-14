"""
Shared test fixtures for unit and integration tests.

Integration tests require a running PostgreSQL instance.
Set TEST_DATABASE_URL in your environment or they will be skipped:

    export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/industrial_laundry_test"
"""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/industrial_laundry_test",
)

# ── Shared constants ───────────────────────────────────────────────────────────

TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Integration test fixtures (require real PostgreSQL) ───────────────────────


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create tables once per test session; drop them after."""
    from app.models.base import Base
    from app.models.batch import Batch  # noqa: F401
    from app.models.event import OperationalEvent  # noqa: F401
    from app.models.station import Station  # noqa: F401

    try:
        engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    except Exception:
        pytest.skip("PostgreSQL not available — skipping integration tests")


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide a transactional DB session that is rolled back after each test."""
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client(test_engine):
    """
    FastAPI test client with database dependency overridden to use the test engine.
    Redis calls are NOT mocked here — tests that need Redis must handle that themselves.
    """
    from app.api.deps import get_tenant_id
    from app.core.database import get_db
    from app.main import app

    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    async def override_get_tenant_id():
        return TEST_TENANT_ID

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_id] = override_get_tenant_id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ── Seed helpers ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seeded_station(db_session: AsyncSession):
    """Insert one station and return it."""
    from app.models.station import Station

    station = Station(
        tenant_id=TEST_TENANT_ID,
        name="TEST_WASHING",
        sequence_order=1,
    )
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    return station


@pytest_asyncio.fixture
async def seeded_batch(db_session: AsyncSession):
    """Insert one in-progress batch and return it."""
    from app.models.batch import Batch

    batch = Batch(
        tenant_id=TEST_TENANT_ID,
        batch_code=f"TEST_{uuid.uuid4().hex[:6].upper()}",
        status="in_progress",
    )
    db_session.add(batch)
    await db_session.commit()
    await db_session.refresh(batch)
    return batch
