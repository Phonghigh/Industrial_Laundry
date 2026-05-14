"""
Shared FastAPI dependencies.

Import these via Depends() in any route handler:

    from app.api.deps import get_tenant_id
    from app.core.database import get_db

    @router.get("/batches")
    async def list_batches(
        tenant_id: uuid.UUID = Depends(get_tenant_id),
        db: AsyncSession = Depends(get_db),
    ):
        ...
"""

import uuid

from fastapi import Request


def get_tenant_id(request: Request) -> uuid.UUID:
    """
    Extract the resolved tenant_id from request.state.

    Populated by TenantMiddleware on every request.
    Never raises — middleware guarantees the attribute is always set.
    """
    return request.state.tenant_id
