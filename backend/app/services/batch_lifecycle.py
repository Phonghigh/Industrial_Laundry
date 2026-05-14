"""
Batch lifecycle service.

Detects when a batch has completed all stations and updates its status.

Rules:
- A batch is 'completed' when it has a 'completed' event at the station
  with the highest sequence_order for its tenant.
- A batch is 'stuck' when its most recent event is older than the threshold
  (this status is used by AlertEngine — not set here, AlertEngine queries it live).
- Status transitions are one-way: in_progress → completed.
  We never go backwards.
"""

import uuid

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import Batch

log = structlog.get_logger()


async def maybe_complete_batch(
    db: AsyncSession,
    batch_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    """
    Check if the given batch has a 'completed' event at the last station
    (max sequence_order for this tenant). If so, update batch.status to
    'completed'.

    Returns True if the batch was just marked completed.
    """
    result = await db.execute(
        text("""
            SELECT
                b.id,
                b.status,
                (
                    -- Does this batch have a 'completed' event at the final station?
                    SELECT COUNT(*) > 0
                    FROM operational_events e
                    JOIN stations s ON e.station_id = s.id
                    WHERE e.batch_id   = b.id
                      AND e.tenant_id  = :tenant_id
                      AND e.event_type = 'completed'
                      AND s.sequence_order = (
                          SELECT MAX(sequence_order)
                          FROM stations
                          WHERE tenant_id = :tenant_id
                      )
                ) AS is_finished
            FROM batches b
            WHERE b.id        = :batch_id
              AND b.tenant_id = :tenant_id
              AND b.status    = 'in_progress'
        """),
        {"batch_id": batch_id, "tenant_id": tenant_id},
    )
    row = result.fetchone()

    if row is None:
        # Batch not found or already completed — nothing to do
        return False

    if not row.is_finished:
        return False

    # Mark completed
    await db.execute(
        update(Batch)
        .where(Batch.id == batch_id)
        .where(Batch.tenant_id == tenant_id)
        .where(Batch.status == "in_progress")
        .values(status="completed")
    )
    log.info("batch_completed", batch_id=str(batch_id))
    return True
