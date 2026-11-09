from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StoreBase(BaseModel):
    s7Code: str = Field(min_length=1, max_length=20)
    s7Name: str = Field(min_length=1, max_length=100)
    s7Type: str = "retail"
    s7Addr: str | None = None
    s7Phone: str | None = None
    s7TaxID: str | None = None
    s7Status: bool = True


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    s7Code: str | None = Field(None, min_length=1, max_length=20)
    s7Name: str | None = Field(None, min_length=1, max_length=100)
    s7Type: str | None = None
    s7Addr: str | None = None
    s7Phone: str | None = None
    s7TaxID: str | None = None
    s7Status: bool | None = None


class StoreOut(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    s7Sid: int
    s7QrVer: int
    s7CreatedAt: datetime
    s7UpdatedAt: datetime | None = None


class StoreQrOut(BaseModel):
    s7Code: str
    s7QrVer: int
    qrSig: str
    qrQuery: str  # append to the app URL: ?shop=...&sig=...
