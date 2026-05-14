import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class BatchCreate(BaseModel):
    batch_code: str = Field(max_length=50)
    customer_id: uuid.UUID | None = None


class BatchRead(BaseModel):
    id: uuid.UUID
    batch_code: str
    customer_id: uuid.UUID | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
