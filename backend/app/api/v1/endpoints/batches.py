import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_id
from app.core.database import get_db
from app.models.batch import Batch
from app.schemas.batch import BatchCreate, BatchRead

log = structlog.get_logger()
router = APIRouter()


@router.get("", response_model=list[BatchRead])
async def list_batches(
    batch_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[BatchRead]:
    stmt = select(Batch).where(Batch.tenant_id == tenant_id)
    if batch_status:
        stmt = stmt.where(Batch.status == batch_status)
    stmt = stmt.order_by(Batch.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return [BatchRead.model_validate(b) for b in result.scalars()]


@router.post("", response_model=BatchRead, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchCreate,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BatchRead:
    existing = await db.execute(
        select(Batch).where(
            Batch.batch_code == payload.batch_code,
            Batch.tenant_id == tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"batch_code '{payload.batch_code}' already exists",
        )

    batch = Batch(
        tenant_id=tenant_id,
        batch_code=payload.batch_code,
        customer_id=payload.customer_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    log.info("batch_created", batch_code=payload.batch_code, tenant_id=str(tenant_id))
    return BatchRead.model_validate(batch)


@router.get("/{batch_id}", response_model=BatchRead)
async def get_batch(
    batch_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BatchRead:
    result = await db.execute(
        select(Batch).where(Batch.id == batch_id, Batch.tenant_id == tenant_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return BatchRead.model_validate(batch)
