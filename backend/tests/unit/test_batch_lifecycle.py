"""
Unit tests for maybe_complete_batch.

The DB session is mocked — no real database required.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.batch_lifecycle import maybe_complete_batch

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
BATCH = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _mock_db_with_row(row) -> AsyncMock:
    result = MagicMock()
    result.fetchone.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


# ── Not found / already completed ─────────────────────────────────────────────


async def test_returns_false_when_batch_not_found():
    db = _mock_db_with_row(None)
    assert await maybe_complete_batch(db, BATCH, TENANT) is False
    db.execute.assert_not_awaited()  # only the SELECT ran — no UPDATE


async def test_returns_false_when_batch_not_finished():
    row = MagicMock()
    row.is_finished = False
    db = _mock_db_with_row(row)
    result = await maybe_complete_batch(db, BATCH, TENANT)
    assert result is False
    # Only one execute call (the SELECT) — no UPDATE
    assert db.execute.call_count == 1


# ── Completion ─────────────────────────────────────────────────────────────────


async def test_returns_true_and_updates_when_finished():
    row = MagicMock()
    row.is_finished = True
    db = _mock_db_with_row(row)
    result = await maybe_complete_batch(db, BATCH, TENANT)
    assert result is True
    # Two execute calls: SELECT + UPDATE
    assert db.execute.call_count == 2


async def test_update_includes_tenant_id():
    """The UPDATE statement must filter by tenant_id (multi-tenant safety check)."""
    row = MagicMock()
    row.is_finished = True
    db = _mock_db_with_row(row)
    await maybe_complete_batch(db, BATCH, TENANT)

    # Inspect the second call (UPDATE) — it should bind tenant_id somewhere
    # We verify this by checking the compiled WHERE clause contains the tenant
    update_call = db.execute.call_args_list[1]
    stmt = update_call.args[0]
    # SQLAlchemy Update objects include whereclause
    where_str = str(stmt.whereclause)
    assert "tenant_id" in where_str
