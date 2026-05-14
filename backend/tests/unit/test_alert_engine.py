"""
Unit tests for AlertEngine.

The DB session is mocked — no real database required.
Each private method is tested directly to keep assertions focused.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_engine import AlertEngine

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _mock_db(rows: list) -> AsyncMock:
    """Return a mock AsyncSession whose execute() yields the given rows."""
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(rows))
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


# ── _stuck_batches ─────────────────────────────────────────────────────────────


async def test_stuck_batches_empty():
    engine = AlertEngine(tenant_id=TENANT)
    db = _mock_db([])
    assert await engine._stuck_batches(db) == []


async def test_stuck_batches_single():
    engine = AlertEngine(tenant_id=TENANT)
    row = SimpleNamespace(batch_code="BATCH_001", station_name="DRYING", stuck_mins=42.6)
    db = _mock_db([row])
    result = await engine._stuck_batches(db)
    assert len(result) == 1
    assert result[0] == {"batch_code": "BATCH_001", "station": "DRYING", "stuck_mins": 43}


async def test_stuck_batches_rounds_minutes():
    engine = AlertEngine(tenant_id=TENANT)
    row = SimpleNamespace(batch_code="B", station_name="IRONING", stuck_mins=31.1)
    db = _mock_db([row])
    result = await engine._stuck_batches(db)
    assert result[0]["stuck_mins"] == 31


async def test_stuck_batches_multiple_ordered():
    engine = AlertEngine(tenant_id=TENANT)
    rows = [
        SimpleNamespace(batch_code="B1", station_name="WASHING", stuck_mins=90.0),
        SimpleNamespace(batch_code="B2", station_name="DRYING", stuck_mins=45.0),
    ]
    db = _mock_db(rows)
    result = await engine._stuck_batches(db)
    assert [r["batch_code"] for r in result] == ["B1", "B2"]


# ── _inactive_stations ─────────────────────────────────────────────────────────


async def test_inactive_stations_empty():
    engine = AlertEngine(tenant_id=TENANT)
    db = _mock_db([])
    assert await engine._inactive_stations(db) == []


async def test_inactive_stations_never_active():
    """Stations with no events ever should have never_active=True and silent_mins=None."""
    engine = AlertEngine(tenant_id=TENANT)
    row = SimpleNamespace(name="INTAKE", silent_mins=None)
    db = _mock_db([row])
    result = await engine._inactive_stations(db)
    assert result[0]["station"] == "INTAKE"
    assert result[0]["never_active"] is True
    assert result[0]["silent_mins"] is None


async def test_inactive_stations_long_silence():
    engine = AlertEngine(tenant_id=TENANT)
    row = SimpleNamespace(name="PACKING", silent_mins=22.3)
    db = _mock_db([row])
    result = await engine._inactive_stations(db)
    assert result[0]["silent_mins"] == 22
    assert result[0]["never_active"] is False


# ── _station_throughput ────────────────────────────────────────────────────────


async def test_station_throughput_empty():
    engine = AlertEngine(tenant_id=TENANT)
    db = _mock_db([])
    assert await engine._station_throughput(db) == []


async def test_station_throughput_counts():
    engine = AlertEngine(tenant_id=TENANT)
    rows = [
        SimpleNamespace(name="SORTING", completed_last_hour=320),
        SimpleNamespace(name="DRYING", completed_last_hour=120),
    ]
    db = _mock_db(rows)
    result = await engine._station_throughput(db)
    assert result == [
        {"station": "SORTING", "completed_last_hour": 320},
        {"station": "DRYING", "completed_last_hour": 120},
    ]


# ── compute_operational_state ─────────────────────────────────────────────────


async def test_compute_operational_state_shape():
    """compute_operational_state returns the expected top-level keys."""
    engine = AlertEngine(tenant_id=TENANT)

    mock_db = _mock_db([])

    # Patch AsyncSessionLocal to return our mock db
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.alert_engine.AsyncSessionLocal", return_value=mock_cm):
        state = await engine.compute_operational_state()

    assert set(state.keys()) == {
        "stuck_batches",
        "inactive_stations",
        "station_throughput",
        "computed_at",
    }


async def test_compute_operational_state_updates_prometheus():
    """Prometheus gauges are updated even on empty results."""
    engine = AlertEngine(tenant_id=TENANT)

    mock_db = _mock_db([])
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.alert_engine.AsyncSessionLocal", return_value=mock_cm):
        with patch("app.services.alert_engine.stuck_batches_gauge") as mock_stuck:
            with patch("app.services.alert_engine.inactive_stations_gauge") as mock_inactive:
                await engine.compute_operational_state()
                mock_stuck.set.assert_called_once_with(0)
                mock_inactive.set.assert_called_once_with(0)
