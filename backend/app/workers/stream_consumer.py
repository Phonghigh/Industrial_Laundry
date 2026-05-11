"""
Redis Streams consumer. Reads from operational_events stream,
writes confirmed events to PostgreSQL. Runs as a background task.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.models.event import OperationalEvent

log = structlog.get_logger()

BLOCK_MS = 5000
BATCH_SIZE = 50


async def run_consumer() -> None:
    r = await get_redis()

    # Ensure consumer group exists
    try:
        await r.xgroup_create(settings.redis_stream_key, settings.redis_consumer_group, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists

    consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
    log.info("stream_consumer_started", consumer=consumer_name)

    while True:
        try:
            messages = await r.xreadgroup(
                settings.redis_consumer_group,
                consumer_name,
                {settings.redis_stream_key: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )

            if not messages:
                continue

            for _, entries in messages:
                await _process_batch(r, entries)

        except Exception as exc:
            log.error("consumer_error", error=str(exc))
            await asyncio.sleep(1)


async def _process_batch(r, entries: list) -> None:
    async with AsyncSessionLocal() as db:
        acked = []
        for entry_id, data in entries:
            try:
                event = OperationalEvent(
                    id=uuid.UUID(data["event_id"]),
                    tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),  # default tenant
                    batch_id=uuid.UUID(data["batch_id"]),
                    station_id=uuid.UUID(data["station_id"]),
                    event_type=data["event_type"],
                    device_id=data.get("device_id"),
                    idempotency_key=uuid.UUID(data["idempotency_key"]),
                    ts=datetime.fromisoformat(data["timestamp"]),
                    metadata_=json.loads(data.get("metadata", "{}")),
                )
                db.add(event)
                acked.append(entry_id)
            except Exception as exc:
                log.error("event_process_failed", entry_id=entry_id, error=str(exc))

        await db.commit()

    if acked:
        await r.xack(settings.redis_stream_key, settings.redis_consumer_group, *acked)
        log.info("events_persisted", count=len(acked))
