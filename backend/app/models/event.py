import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin


class OperationalEvent(Base, TenantMixin):
    __tablename__ = "operational_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"))
    station_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stations.id"))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sync_status: Mapped[str] = mapped_column(String(20), default="synced")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    batch = relationship("Batch", back_populates="events")
    station = relationship("Station", back_populates="events")

    __table_args__ = (
        Index("idx_events_batch_ts", "batch_id", "ts"),
        Index("idx_events_station_ts", "station_id", "ts"),
    )
