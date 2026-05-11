from fastapi import APIRouter

from app.api.v1.endpoints import events, manager

api_router = APIRouter()

api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(manager.router, prefix="/manager", tags=["manager"])
