"""Dev data seeder — inserts stations and sample batches.

Run AFTER migrations:
    alembic upgrade head
    python scripts/seed.py
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

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
        station_ids = []
        for name, order in STATIONS:
            s = Station(id=uuid.uuid4(), tenant_id=TENANT_ID, name=name, sequence_order=order)
            db.add(s)
            station_ids.append(s.id)

        for i in range(1, 6):
            b = Batch(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                batch_code=f"BATCH_{2040 + i:04d}",
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

        await db.commit()
        print(f"Seeded {len(STATIONS)} stations and 5 batches for tenant {TENANT_ID}")


asyncio.run(seed())
