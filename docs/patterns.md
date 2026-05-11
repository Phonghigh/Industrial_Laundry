# Code Patterns

Canonical implementations for recurring patterns. Copy these exactly — don't invent variations.

---

## Pattern: New API Endpoint

```python
# backend/app/api/v1/endpoints/batches.py

import uuid
import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.batch import Batch
from app.schemas.batch import BatchCreate, BatchRead

log = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=list[BatchRead])
async def list_batches(
    tenant_id: uuid.UUID,   # extract from middleware in production
    db: AsyncSession = Depends(get_db),
) -> list[BatchRead]:
    result = await db.execute(
        select(Batch)
        .where(Batch.tenant_id == tenant_id)
        .order_by(Batch.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()
```

Register in `router.py`:
```python
from app.api.v1.endpoints import batches
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
```

---

## Pattern: New SQLAlchemy Model

```python
# backend/app/models/worker.py

import uuid
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin


class Worker(Base, TenantMixin, TimestampMixin):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    station_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
```

Always: `TenantMixin` first, `TimestampMixin` second, own fields last.

---

## Pattern: New Pydantic Schema Pair

```python
# backend/app/schemas/batch.py

import uuid
from datetime import datetime
from pydantic import BaseModel


class BatchCreate(BaseModel):
    batch_code: str
    customer_id: uuid.UUID | None = None


class BatchRead(BaseModel):
    id: uuid.UUID
    batch_code: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}   # always on Read schemas
```

Rule: `Create` schema = input fields only. `Read` schema = `from_attributes = True`.

---

## Pattern: Alembic Migration

```python
# backend/alembic/versions/002_add_workers_table.py

"""add workers table

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),   # always include
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("station_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_workers_tenant", "workers", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("idx_workers_tenant")
    op.drop_table("workers")
```

---

## Pattern: Station App — Adding a New Event Type

1. Add to `event_type` union in `station-app/src/services/localQueue.ts`:
```typescript
event_type: "started" | "completed" | "issue_flagged" | "skipped" | "YOUR_NEW_TYPE";
```

2. Add to backend Pydantic schema regex in `backend/app/schemas/event.py`:
```python
event_type: str = Field(pattern="^(started|completed|issue_flagged|skipped|your_new_type)$")
```

3. Add a `BigButton` variant in the station app UI.

4. Document in `docs/event-schema.md`.

---

## Pattern: New Alert in AlertEngine

```python
# Add method to backend/app/services/alert_engine.py

async def _your_new_alert(self, db) -> list[dict]:
    result = await db.execute(
        text("""
            SELECT ... FROM operational_events e
            WHERE ...
        """),
        {"param": value},
    )
    return [{"field": r.field} for r in result]
```

Add to `compute_operational_state()`:
```python
your_alerts = await self._your_new_alert(db)
return {
    ...,
    "your_alerts": your_alerts,
}
```

Update SSE consumer in dashboard `sseClient.ts` to handle the new field.

---

## Pattern: New Prometheus Metric

```python
# backend/app/middleware/observability.py

from prometheus_client import Counter, Histogram, Gauge

events_ingested = Counter(
    "laundry_events_ingested_total",
    "Total operational events ingested",
    ["event_type", "station_id"],
)

event_ingest_latency = Histogram(
    "laundry_event_ingest_latency_seconds",
    "Event ingest latency",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

stuck_batch_count = Gauge(
    "laundry_stuck_batches",
    "Number of currently stuck batches",
)
```

Rule: All metric names prefixed with `laundry_`. Include unit in name (`_seconds`, `_total`, `_count`).

---

## Pattern: New Custom Claude Command

Create `.claude/commands/your-command.md`. The file IS the prompt — write it as if telling Claude what to do:

```markdown
# /your-command

[Description of what this command does]

## What to do

1. [Step one]
2. [Step two]

## Constraints

- Must follow pattern from `docs/patterns.md`
- Must include tenant_id
```
