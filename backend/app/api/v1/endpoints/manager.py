import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.services.alert_engine import AlertEngine

router = APIRouter()


@router.get(
    "/overview",
    summary="SSE stream of real-time operational state for manager dashboard",
)
async def operational_overview() -> StreamingResponse:
    async def event_stream():
        alert_engine = AlertEngine()
        while True:
            state = await alert_engine.compute_operational_state()
            payload = json.dumps({"type": "operational_state", **state})
            yield f"data: {payload}\n\n"
            await asyncio.sleep(settings.sse_ping_interval)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
