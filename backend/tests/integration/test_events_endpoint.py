"""
Integration tests for POST /api/v1/events.

Requires a running PostgreSQL instance (see conftest.py for TEST_DATABASE_URL).
Tests are skipped automatically if the database is unavailable.

Redis is mocked in all tests — these tests focus on the HTTP contract and the
PostgreSQL fallback path, not Redis internals.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import TEST_TENANT_ID


def _event_payload(**overrides) -> dict:
    base = {
        "batch_id": str(uuid.uuid4()),
        "station_id": str(uuid.uuid4()),
        "event_type": "started",
        "device_id": "device_test_001",
        "idempotency_key": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {},
    }
    return {**base, **overrides}


# ── Redis path (normal) ────────────────────────────────────────────────────────


async def test_post_event_redis_path_returns_202(test_client):
    """Normal path: Redis available → 202 with queued=True."""
    with patch("app.api.v1.endpoints.events.publish_event", new_callable=AsyncMock):
        resp = await test_client.post("/api/v1/events", json=_event_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert body["queued"] is True
    assert "event_id" in body


async def test_post_event_redis_path_response_schema(test_client):
    with patch("app.api.v1.endpoints.events.publish_event", new_callable=AsyncMock):
        resp = await test_client.post("/api/v1/events", json=_event_payload())
    body = resp.json()
    uuid.UUID(body["event_id"])  # must be a valid UUID


# ── Fallback path (Redis down) ─────────────────────────────────────────────────


async def test_post_event_fallback_path_returns_202(test_client, seeded_station, seeded_batch):
    """Fallback path: Redis down → writes directly to PostgreSQL → 202 queued=False."""
    payload = _event_payload(
        batch_id=str(seeded_batch.id),
        station_id=str(seeded_station.id),
    )
    with patch(
        "app.api.v1.endpoints.events.publish_event",
        side_effect=ConnectionError("Redis down"),
    ):
        resp = await test_client.post("/api/v1/events", json=payload)

    assert resp.status_code == 202
    body = resp.json()
    assert body["queued"] is False


async def test_post_event_fallback_idempotent(test_client, seeded_station, seeded_batch):
    """Sending the same idempotency_key twice on the fallback path must return 202 both times."""
    idempotency_key = str(uuid.uuid4())
    payload = _event_payload(
        batch_id=str(seeded_batch.id),
        station_id=str(seeded_station.id),
        idempotency_key=idempotency_key,
    )
    redis_fail = patch(
        "app.api.v1.endpoints.events.publish_event",
        side_effect=ConnectionError("Redis down"),
    )

    with redis_fail:
        resp1 = await test_client.post("/api/v1/events", json=payload)
    with redis_fail:
        resp2 = await test_client.post("/api/v1/events", json=payload)

    assert resp1.status_code == 202
    assert resp2.status_code == 202  # duplicate — still 202, not 409


# ── Validation ─────────────────────────────────────────────────────────────────


async def test_post_event_invalid_event_type(test_client):
    resp = await test_client.post("/api/v1/events", json=_event_payload(event_type="destroyed"))
    assert resp.status_code == 422


async def test_post_event_missing_batch_id(test_client):
    payload = {k: v for k, v in _event_payload().items() if k != "batch_id"}
    resp = await test_client.post("/api/v1/events", json=payload)
    assert resp.status_code == 422


async def test_post_event_missing_idempotency_key(test_client):
    payload = {k: v for k, v in _event_payload().items() if k != "idempotency_key"}
    resp = await test_client.post("/api/v1/events", json=payload)
    assert resp.status_code == 422


# ── Tenant isolation ───────────────────────────────────────────────────────────


async def test_post_event_tenant_id_from_header(test_client):
    """
    If a different tenant header is provided, the event must be tagged with that tenant.
    We verify this indirectly — the request must still return 202 (no crash).
    """
    other_tenant = str(uuid.uuid4())
    with patch("app.api.v1.endpoints.events.publish_event", new_callable=AsyncMock):
        resp = await test_client.post(
            "/api/v1/events",
            json=_event_payload(),
            headers={"X-Tenant-ID": other_tenant},
        )
    assert resp.status_code == 202
