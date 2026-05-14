"""
Redis Streams consumer. Reads from operational_events stream,
writes confirmed events to PostgreSQL. Runs as a background task.

Resilience guarantees:
- UniqueViolation on idempotency_key → treated as success (acked, not retried)
- PEL recovery on startup → entries left by a previous crashed consumer are reclaimed
- Consumer error → logged, 1s sleep, loop continues
"""

import asyncio
import uuid

import structlog

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis
from app.models.batch import Batch  # noqa: F401 — SQLAlchemy mapper resolution
from app.models.station import Station  # noqa: F401 — SQLAlchemy mapper resolution
from app.services.event_processor import build_event_from_stream, try_persist_event

log = structlog.get_logger()

BLOCK_MS = 5_000       # long-poll when stream is idle
BATCH_SIZE = 50        # entries per xreadgroup call
PEL_RECLAIM_MIN_IDLE_MS = 60_000   # reclaim PEL entries idle > 60s


async def run_consumer() -> None:
    r = await get_redis()

    # Ensure consumer group exists (silently ignore if already present)
    try:
        await r.xgroup_create(
            settings.redis_stream_key,
            settings.redis_consumer_group,
            id="0",
            mkstream=True,
        )
        log.info("consumer_group_created", group=settings.redis_consumer_group)
    except Exception:
        pass  # Group already exists — normal on restart

    consumer_name = f"consumer-{uuid.uuid4().hex[:8]}"
    log.info("stream_consumer_started", consumer=consumer_name)

    # ── PEL recovery ───────────────────────────────────────────────────────
    # Reclaim entries that were delivered to a previous consumer but never
    # acked (e.g. the process crashed between db.commit() and xack).
    # xautoclaim transfers ownership to this consumer so the main loop picks
    # them up via ">".
    await _recover_pel(r, consumer_name)

    # ── Main consume loop ──────────────────────────────────────────────────
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
            log.error("consumer_loop_error", error=str(exc))
            await asyncio.sleep(1)


async def _recover_pel(r, consumer_name: str) -> None:
    """Reclaim PEL entries idle longer than PEL_RECLAIM_MIN_IDLE_MS."""
    try:
        # xautoclaim: claim up to 100 entries idle > 60s, transfer to us
        result = await r.xautoclaim(
            settings.redis_stream_key,
            settings.redis_consumer_group,
            consumer_name,
            min_idle_time=PEL_RECLAIM_MIN_IDLE_MS,
            start_id="0-0",
            count=100,
        )
        # result = (next_start_id, entries, deleted_ids)
        reclaimed_entries = result[1] if isinstance(result, (list, tuple)) else []
        if reclaimed_entries:
            log.info("pel_recovery", count=len(reclaimed_entries))
            await _process_batch(r, reclaimed_entries)
    except Exception as exc:
        # xautoclaim requires Redis 6.2+ — log and continue if unavailable
        log.warning("pel_recovery_skipped", reason=str(exc))


async def _process_batch(r, entries: list) -> None:
    """
    Persist a batch of stream entries to PostgreSQL, then ack them.

    Idempotency is handled inside try_persist_event — duplicates are acked,
    not retried. Entries that fail unexpectedly remain in the PEL for recovery.
    """
    async with AsyncSessionLocal() as db:
        acked: list[str] = []

        for entry_id, data in entries:
            try:
                # Ensure tenant_id falls back to the configured default
                data_with_tenant = {
                    **data,
                    "tenant_id": data.get("tenant_id", str(settings.tenant_id)),
                }
                event = build_event_from_stream(data_with_tenant)
                inserted = await try_persist_event(db, event)
                acked.append(entry_id)
                if not inserted:
                    log.debug("stream_event_duplicate", entry_id=entry_id)

            except Exception as exc:
                # Unexpected error — leave in PEL for retry on next restart.
                log.error("event_process_failed", entry_id=entry_id, error=str(exc))
                await db.rollback()

        await db.commit()

    if acked:
        await r.xack(settings.redis_stream_key, settings.redis_consumer_group, *acked)
        log.info("events_persisted", count=len(acked))
