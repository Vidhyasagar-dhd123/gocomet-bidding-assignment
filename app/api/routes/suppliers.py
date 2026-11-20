from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.core.errors import ConflictError, NotFoundError
from app.models import Supplier
from app.schemas.supplier import SupplierCreate, SupplierOut

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(payload: SupplierCreate, db: DbSession) -> Supplier:
    supplier = Supplier(name=payload.name.strip(), contact_email=payload.contact_email)
    db.add(supplier)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"Supplier '{payload.name}' already exists") from exc
    await db.refresh(supplier)
    return supplier


@router.get("", response_model=list[SupplierOut])
async def list_suppliers(db: DbSession) -> list[Supplier]:
    return list(await db.scalars(select(Supplier).order_by(Supplier.name)))


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(supplier_id: int, db: DbSession) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return supplier
