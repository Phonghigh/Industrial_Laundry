import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import publish_event
from app.schemas.event import EventIngest, EventIngestResponse

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
    db: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    event_id = uuid.uuid4()

    # Publish to Redis Stream for async processing
    stream_data = {
        "event_id": str(event_id),
        "batch_id": str(payload.batch_id),
        "station_id": str(payload.station_id),
        "event_type": payload.event_type,
        "device_id": payload.device_id,
        "idempotency_key": str(payload.idempotency_key),
        "timestamp": payload.timestamp.isoformat(),
        "metadata": json.dumps(payload.metadata),
    }

    try:
        await publish_event(stream_data)
    except Exception as exc:
        log.error("redis_publish_failed", error=str(exc), event_id=str(event_id))
        raise HTTPException(status_code=503, detail="Event queue unavailable") from exc

    log.info(
        "event_ingested",
        event_id=str(event_id),
        batch_id=str(payload.batch_id),
        station_id=str(payload.station_id),
        event_type=payload.event_type,
    )

    return EventIngestResponse(event_id=event_id, queued=True)
