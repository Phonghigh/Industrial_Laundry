"""Dev data seeder — inserts stations and sample batches.

Run AFTER migrations:
    alembic upgrade head
    python scripts/seed.py
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure the backend root (/app inside the container, backend/ locally) is on sys.path
# so that `from app.xxx import ...` works regardless of how the script is invoked.
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.batch import Batch
from app.models.event import OperationalEvent
from app.models.station import Station

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

STATIONS = [
    ("Intake", 1),
    ("Sorting", 2),
    ("Washing", 3),
    ("Drying", 4),
    ("Ironing", 5),
    ("Packing", 6),
    ("Dispatch", 7),
]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Stations (skip if already exist) ──────────────────────────────────
        existing_stations = (await db.execute(
            select(Station).where(Station.tenant_id == TENANT_ID)
        )).scalars().all()
        existing_names = {s.name for s in existing_stations}

        station_ids = [s.id for s in sorted(existing_stations, key=lambda s: s.sequence_order)]

        for name, order in STATIONS:
            if name not in existing_names:
                s = Station(id=uuid.uuid4(), tenant_id=TENANT_ID, name=name, sequence_order=order)
                db.add(s)
                station_ids.append(s.id)
                print(f"  + Station: {name}")

        await db.flush()  # get IDs before creating events

        # ── Batches (skip if already exist) ───────────────────────────────────
        existing_codes = {
            r for (r,) in (await db.execute(
                select(Batch.batch_code).where(Batch.tenant_id == TENANT_ID)
            )).all()
        }

        added = 0
        for i in range(1, 6):
            code = f"BATCH_{2040 + i:04d}"
            if code in existing_codes:
                continue

            b = Batch(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                batch_code=code,
                status="in_progress",
            )
            db.add(b)

            e = OperationalEvent(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                batch_id=b.id,
                station_id=station_ids[i % len(station_ids)],
                event_type="started",
                device_id="seed-device",
                idempotency_key=uuid.uuid4(),
                ts=datetime.now(timezone.utc),
            )
            db.add(e)
            added += 1
            print(f"  + Batch: {code}")

        await db.commit()
        print(f"Done — {added} new batches, tenant {TENANT_ID}")


asyncio.run(seed())
