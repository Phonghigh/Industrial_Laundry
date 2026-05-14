import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_id
from app.core.database import get_db
from app.models.station import Station
from app.schemas.station import StationRead

router = APIRouter()


@router.get("", response_model=list[StationRead])
async def list_stations(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[StationRead]:
    result = await db.execute(
        select(Station)
        .where(Station.tenant_id == tenant_id)
        .order_by(Station.sequence_order)
    )
    return [StationRead.model_validate(s) for s in result.scalars()]
