import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import close_redis
from app.workers.stream_consumer import run_consumer

log = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten per environment
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup():
        log.info("app_starting", environment=settings.environment)
        asyncio.create_task(run_consumer())

    @app.on_event("shutdown")
    async def shutdown():
        await close_redis()
        log.info("app_stopped")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
