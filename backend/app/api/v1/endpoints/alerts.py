import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_tenant_id
from app.services.alert_engine import AlertEngine

router = APIRouter()


@router.get("")
async def get_alerts(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> dict:
    """
    Snapshot of current operational state: stuck batches, inactive stations,
    station throughput. Same data as the SSE stream but as a single HTTP response.
    """
    engine = AlertEngine(tenant_id=tenant_id)
    return await engine.compute_operational_state()
