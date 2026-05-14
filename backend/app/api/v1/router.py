from fastapi import APIRouter

from app.api.v1.endpoints import alerts, batches, events, manager, stations

api_router = APIRouter()

api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(stations.router, prefix="/stations", tags=["stations"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(manager.router, prefix="/manager", tags=["manager"])
