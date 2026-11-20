from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SupplierOut(ORMModel):
    id: int
    name: str
    contact_email: str | None
    created_at: datetime
