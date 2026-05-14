"""
Event processor — shared persistence logic used by both write paths:
  1. Redis stream consumer (normal path)
  2. Direct PostgreSQL fallback (when Redis is unavailable)

Keeping this here means both paths exercise identical business logic,
and the logic is independently testable without spinning up Redis.
"""

import json
import uuid
from datetime import datetime

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import OperationalEvent
from app.services.batch_lifecycle import maybe_complete_batch

log = structlog.get_logger()


def build_event_from_stream(data: dict) -> OperationalEvent:
    """Parse a Redis stream entry dict into an ORM model (not yet persisted)."""
    return OperationalEvent(
        id=uuid.UUID(data["event_id"]),
        tenant_id=uuid.UUID(data["tenant_id"]),
        batch_id=uuid.UUID(data["batch_id"]),
        station_id=uuid.UUID(data["station_id"]),
        event_type=data["event_type"],
        device_id=data.get("device_id"),
        idempotency_key=uuid.UUID(data["idempotency_key"]),
        ts=datetime.fromisoformat(data["timestamp"]),
        metadata_=json.loads(data.get("metadata", "{}")),
    )


def build_event_from_request(
    *,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    station_id: uuid.UUID,
    event_type: str,
    device_id: str | None,
    idempotency_key: uuid.UUID,
    ts: datetime,
    metadata: dict,
) -> OperationalEvent:
    """Build an ORM model from a validated API request (not yet persisted)."""
    return OperationalEvent(
        id=event_id,
        tenant_id=tenant_id,
        batch_id=batch_id,
        station_id=station_id,
        event_type=event_type,
        device_id=device_id,
        idempotency_key=idempotency_key,
        ts=ts,
        metadata_=metadata,
    )


async def try_persist_event(db: AsyncSession, event: OperationalEvent) -> bool:
    """
    Flush a single event to the database within the caller's transaction.

    Returns True if newly inserted.
    Returns False if the idempotency_key already exists (duplicate — safe to ack).
    Raises on all other unexpected errors.

    Caller is responsible for db.commit() / db.rollback() at the batch boundary.
    """
    try:
        db.add(event)
        await db.flush()

        if event.event_type == "completed":
            await maybe_complete_batch(db, event.batch_id, event.tenant_id)

        return True

    except IntegrityError:
        await db.rollback()
        log.debug(
            "event_duplicate_skipped",
            idempotency_key=str(event.idempotency_key),
        )
        return False
