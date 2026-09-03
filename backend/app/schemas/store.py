from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoreBase(BaseModel):
    s7Code: str
    s7Name: str
    s7Type: str
    s7Addr: str | None = None
    s7Phone: str | None = None
    s7TaxID: str | None = None
    s7Status: bool = True


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    s7Code: str | None = None
    s7Name: str | None = None
    s7Type: str | None = None
    s7Addr: str | None = None
    s7Phone: str | None = None
    s7TaxID: str | None = None
    s7Status: bool | None = None


class StoreOut(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    s7Sid: int
    s7CreatedAt: datetime
    s7UpdatedAt: datetime | None = None
