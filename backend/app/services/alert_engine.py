"""
AlertEngine — derives operational state from the event log.

All queries are read-only (no mutations ever).
All queries filter by tenant_id — required for multi-tenant correctness (ADR-006).
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.middleware.observability import inactive_stations_gauge, stuck_batches_gauge

log = structlog.get_logger()


class AlertEngine:
    """
    Derives operational state from the event log for a single tenant.

    Usage:
        engine = AlertEngine(tenant_id=uuid.UUID("..."))
        state = await engine.compute_operational_state()
    """

    def __init__(self, tenant_id: uuid.UUID | None = None) -> None:
        # Use passed tenant_id, else fall back to TENANT_ID env var / default
        self.tenant_id = tenant_id if tenant_id is not None else settings.tenant_id

    async def compute_operational_state(self) -> dict:
        async with AsyncSessionLocal() as db:
            stuck = await self._stuck_batches(db)
            inactive = await self._inactive_stations(db)
            throughput = await self._station_throughput(db)

        # Update Prometheus gauges on every SSE cycle
        stuck_batches_gauge.set(len(stuck))
        inactive_stations_gauge.set(len(inactive))

        return {
            "stuck_batches": stuck,
            "inactive_stations": inactive,
            "station_throughput": throughput,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _stuck_batches(self, db) -> list[dict]:
        """
        Batches whose most recent event (across ALL stations) is older than
        stuck_batch_threshold_mins. Only considers batches with status='in_progress'.

        Uses DISTINCT ON to find the single latest event per batch, then reports
        the station where that last event occurred.
        """
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.stuck_batch_threshold_mins
        )
        result = await db.execute(
            text("""
                WITH latest_event AS (
                    SELECT DISTINCT ON (e.batch_id)
                        e.batch_id,
                        e.station_id,
                        e.ts
                    FROM operational_events e
                    WHERE e.tenant_id = :tenant_id
                    ORDER BY e.batch_id, e.ts DESC
                )
                SELECT
                    b.batch_code,
                    s.name                                          AS station_name,
                    EXTRACT(EPOCH FROM (NOW() - le.ts)) / 60       AS stuck_mins
                FROM latest_event le
                JOIN batches  b ON le.batch_id  = b.id
                JOIN stations s ON le.station_id = s.id
                WHERE b.status    = 'in_progress'
                  AND b.tenant_id = :tenant_id
                  AND le.ts       < :threshold
                ORDER BY stuck_mins DESC
            """),
            {"threshold": threshold, "tenant_id": self.tenant_id},
        )
        return [
            {
                "batch_code": r.batch_code,
                "station": r.station_name,
                "stuck_mins": round(r.stuck_mins),
            }
            for r in result
        ]

    async def _inactive_stations(self, db) -> list[dict]:
        """
        Stations with no event activity for longer than station_inactivity_threshold_mins.
        Stations that have never had any events are also included (silent_mins = 9999).
        """
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.station_inactivity_threshold_mins
        )
        result = await db.execute(
            text("""
                SELECT
                    s.name,
                    EXTRACT(EPOCH FROM (NOW() - MAX(e.ts))) / 60 AS silent_mins
                FROM stations s
                LEFT JOIN operational_events e
                       ON e.station_id = s.id
                      AND e.tenant_id  = :tenant_id
                WHERE s.tenant_id = :tenant_id
                GROUP BY s.name
                HAVING MAX(e.ts) < :threshold
                    OR MAX(e.ts) IS NULL
                ORDER BY silent_mins DESC
            """),
            {"threshold": threshold, "tenant_id": self.tenant_id},
        )
        return [
            {
                "station": r.name,
                "silent_mins": round(r.silent_mins) if r.silent_mins is not None else None,
                "never_active": r.silent_mins is None,
            }
            for r in result
        ]

    async def _station_throughput(self, db) -> list[dict]:
        """
        Count of 'completed' events per station in the last hour.
        """
        result = await db.execute(
            text("""
                SELECT
                    s.name,
                    COUNT(*) AS completed_last_hour
                FROM operational_events e
                JOIN stations s ON e.station_id = s.id
                WHERE e.ts          > NOW() - INTERVAL '1 hour'
                  AND e.event_type  = 'completed'
                  AND e.tenant_id   = :tenant_id
                  AND s.tenant_id   = :tenant_id
                GROUP BY s.name
                ORDER BY s.name
            """),
            {"tenant_id": self.tenant_id},
        )
        return [
            {"station": r.name, "completed_last_hour": r.completed_last_hour}
            for r in result
        ]
