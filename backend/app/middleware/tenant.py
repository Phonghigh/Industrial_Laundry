"""
TenantMiddleware — resolves tenant_id for every request.

Resolution priority (first match wins):
  1. X-Tenant-ID request header    — multi-tenant SaaS routing via nginx/gateway
  2. TENANT_ID environment variable — per-factory deployment config (settings.tenant_id)
  3. DEFAULT_TENANT_ID              — hardcoded fallback for dev / first boot

Resolved UUID is stored in request.state.tenant_id.
All endpoints read from there via the get_tenant_id() FastAPI dependency.

Security note:
  Header-based resolution is unverified at this layer.
  Injection is prevented by network controls (nginx subnet filter / VPN).
  If the API is ever publicly exposed, add JWT-based tenant claims instead.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

log = structlog.get_logger()

TENANT_HEADER = "X-Tenant-ID"


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.tenant_id = _resolve_tenant(request)
        return await call_next(request)


def _resolve_tenant(request: Request) -> uuid.UUID:
    """
    Return the tenant UUID for this request.

    Priority: header → env-configured TENANT_ID → DEFAULT_TENANT_ID.
    """
    # 1. X-Tenant-ID header (multi-tenant routing)
    raw_header = request.headers.get(TENANT_HEADER)
    if raw_header:
        try:
            tenant_id = uuid.UUID(raw_header)
            log.debug("tenant_resolved_from_header", tenant_id=str(tenant_id))
            return tenant_id
        except ValueError:
            # Invalid UUID in header — warn and fall through to env/default
            log.warning("tenant_header_invalid_uuid", raw=raw_header)

    # 2. TENANT_ID env var (set in .env or Docker environment)
    #    settings.tenant_id already merges env → default via pydantic-settings
    log.debug("tenant_resolved_from_config", tenant_id=str(settings.tenant_id))
    return settings.tenant_id
