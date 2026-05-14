import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.redis import close_redis
from app.middleware.tenant import TenantMiddleware

log = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    # ── Tenant resolution (must be first middleware) ────────────────────────
    # Resolves tenant_id from X-Tenant-ID header → TENANT_ID env → default.
    # Stores result in request.state.tenant_id for all downstream handlers.
    app.add_middleware(TenantMiddleware)

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Tenant-ID"],
    )

    # ── API routes ──────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── Prometheus /metrics ─────────────────────────────────────────────────
    app.mount("/metrics", make_asgi_app())

    # ── Lifecycle ───────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup():
        log.info(
            "app_starting",
            environment=settings.environment,
            consumer_in_process=settings.run_consumer_in_process,
        )
        # Consumer runs in-process only when explicitly enabled.
        # In production, it runs as an isolated `worker` Docker service.
        if settings.run_consumer_in_process:
            from app.workers.stream_consumer import run_consumer
            asyncio.create_task(run_consumer())
            log.info("consumer_started_in_process")

    @app.on_event("shutdown")
    async def shutdown():
        await close_redis()
        log.info("app_stopped")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
