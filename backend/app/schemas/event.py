import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EventIngest(BaseModel):
    batch_id: uuid.UUID
    station_id: uuid.UUID
    event_type: str = Field(pattern="^(started|completed|issue_flagged|skipped)$")
    device_id: str
    idempotency_key: uuid.UUID
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)


class EventIngestResponse(BaseModel):
    event_id: uuid.UUID
    queued: bool = True


class EventRead(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    station_id: uuid.UUID
    event_type: str
    device_id: str | None
    ts: datetime
    metadata: dict

    model_config = {"from_attributes": True}
