"""
Event ingest endpoint.

Write path (normal):
  POST /api/v1/events → Redis XADD → 202 Accepted
  Background consumer persists to PostgreSQL.

Write path (Redis unavailable):
  POST /api/v1/events → direct PostgreSQL INSERT → 202 Accepted
  Slower but guarantees events are never lost when Redis is down.
"""

import time
import uuid

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_id
from app.core.database import get_db
from app.core.redis import publish_event
from app.middleware.observability import (
    asr_confidence_histogram,
    event_ingest_latency_seconds,
    events_ingested_total,
)
from app.schemas.event import EventIngest, EventIngestResponse
from app.services.event_processor import build_event_from_request, try_persist_event

log = structlog.get_logger()
router = APIRouter()


@router.post(
    "",
    response_model=EventIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest operational event from station device",
)
async def ingest_event(
    payload: EventIngest,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    event_id = uuid.uuid4()
    _t0 = time.perf_counter()

    # Track ASR confidence for voice-triggered events
    asr_conf = payload.metadata.get("asr_confidence")
    if isinstance(asr_conf, (int, float)):
        asr_confidence_histogram.observe(float(asr_conf))

    stream_data = {
        "event_id": str(event_id),
        "tenant_id": str(tenant_id),
        "batch_id": str(payload.batch_id),
        "station_id": str(payload.station_id),
        "event_type": payload.event_type,
        "device_id": payload.device_id,
        "idempotency_key": str(payload.idempotency_key),
        "timestamp": payload.timestamp.isoformat(),
        "metadata": json.dumps(payload.metadata),
    }

    # ── Primary path: Redis Stream ─────────────────────────────────────────
    try:
        await publish_event(stream_data)
        events_ingested_total.labels(event_type=payload.event_type, path="redis").inc()
        event_ingest_latency_seconds.observe(time.perf_counter() - _t0)
        log.info(
            "event_queued",
            event_id=str(event_id),
            batch_id=str(payload.batch_id),
            event_type=payload.event_type,
            tenant_id=str(tenant_id),
        )
        return EventIngestResponse(event_id=event_id, queued=True)

    except Exception as redis_exc:
        log.warning(
            "redis_unavailable_fallback",
            error=str(redis_exc),
            event_id=str(event_id),
        )

    # ── Fallback path: direct PostgreSQL write ─────────────────────────────
    event = build_event_from_request(
        event_id=event_id,
        tenant_id=tenant_id,
        batch_id=payload.batch_id,
        station_id=payload.station_id,
        event_type=payload.event_type,
        device_id=payload.device_id,
        idempotency_key=payload.idempotency_key,
        ts=payload.timestamp,
        metadata=payload.metadata,
    )
    inserted = await try_persist_event(db, event)
    await db.commit()

    path_label = "direct_db" if inserted else "duplicate"
    events_ingested_total.labels(event_type=payload.event_type, path=path_label).inc()
    event_ingest_latency_seconds.observe(time.perf_counter() - _t0)
    log.info(
        "event_persisted_direct",
        event_id=str(event_id),
        batch_id=str(payload.batch_id),
        event_type=payload.event_type,
        path=path_label,
        tenant_id=str(tenant_id),
    )
    return EventIngestResponse(event_id=event_id, queued=False)
