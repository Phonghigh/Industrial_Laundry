from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

log = structlog.get_logger()


class AlertEngine:
    """Derives operational state from event log. No mutations — read-only."""

    async def compute_operational_state(self) -> dict:
        async with AsyncSessionLocal() as db:
            stuck = await self._stuck_batches(db)
            inactive = await self._inactive_stations(db)
            throughput = await self._station_throughput(db)

        return {
            "stuck_batches": stuck,
            "inactive_stations": inactive,
            "station_throughput": throughput,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _stuck_batches(self, db) -> list[dict]:
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.stuck_batch_threshold_mins
        )
        result = await db.execute(
            text("""
                SELECT b.batch_code, s.name as station_name,
                       EXTRACT(EPOCH FROM (NOW() - MAX(e.ts))) / 60 AS stuck_mins
                FROM operational_events e
                JOIN batches b ON e.batch_id = b.id
                JOIN stations s ON e.station_id = s.id
                WHERE b.status = 'in_progress'
                GROUP BY b.batch_code, s.name
                HAVING MAX(e.ts) < :threshold
                ORDER BY stuck_mins DESC
            """),
            {"threshold": threshold},
        )
        return [
            {"batch_code": r.batch_code, "station": r.station_name, "stuck_mins": round(r.stuck_mins)}
            for r in result
        ]

    async def _inactive_stations(self, db) -> list[dict]:
        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.station_inactivity_threshold_mins
        )
        result = await db.execute(
            text("""
                SELECT s.name, EXTRACT(EPOCH FROM (NOW() - MAX(e.ts))) / 60 AS silent_mins
                FROM stations s
                LEFT JOIN operational_events e ON e.station_id = s.id
                GROUP BY s.name
                HAVING MAX(e.ts) < :threshold OR MAX(e.ts) IS NULL
                ORDER BY silent_mins DESC
            """),
            {"threshold": threshold},
        )
        return [
            {"station": r.name, "silent_mins": round(r.silent_mins or 9999)}
            for r in result
        ]

    async def _station_throughput(self, db) -> list[dict]:
        result = await db.execute(
            text("""
                SELECT s.name, COUNT(*) AS events_last_hour
                FROM operational_events e
                JOIN stations s ON e.station_id = s.id
                WHERE e.ts > NOW() - INTERVAL '1 hour'
                  AND e.event_type = 'completed'
                GROUP BY s.name
                ORDER BY s.name
            """)
        )
        return [{"station": r.name, "completed_last_hour": r.events_last_hour} for r in result]
