import uuid

from pydantic import BaseModel


class StationRead(BaseModel):
    id: uuid.UUID
    name: str
    sequence_order: int

    model_config = {"from_attributes": True}
