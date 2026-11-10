from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Shift = Literal["morning", "afternoon", "evening"]  # เช้า · เย็น · ค่ำ
Status = Literal["submitted", "verified", "void"]
Money = Decimal


class TransactionCreate(BaseModel):
    """Staff form submit. The store comes from the scanned QR code."""

    storeCode: str = Field(min_length=1, max_length=20)
    qrSig: str | None = Field(None, min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")
    t1Date: date  # Bangkok business date picked in the app
    t1Shift: Shift
    t1Cash: Money = Field(ge=0, max_digits=12, decimal_places=2)
    t1Transfer: Money = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    t1Expense: Money = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    t1Note: str | None = Field(None, max_length=500)


class TransactionUpdate(BaseModel):
    """Only the note is editable. Amounts are fixed: void and resubmit to fix them."""

    t1Note: str | None = Field(None, max_length=500)


class TransactionVoid(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    t1TID: int
    t1TNo: str
    t1Sid: int
    t1Pid: int
    t1Date: date
    t1Shift: str
    t1Cash: Money
    t1Transfer: Money
    t1Expense: Money
    t1Total: Money  # net = cash + transfer − expense
    t1Status: str
    t1Note: str | None = None
    t1QrVer: int | None = None
    t1VerifiedBy: int | None = None
    t1VerifiedAt: datetime | None = None
    t1VoidBy: int | None = None
    t1VoidAt: datetime | None = None
    t1VoidReason: str | None = None
    t1CreatedAt: datetime
    t1UpdatedAt: datetime | None = None
    storeCode: str
    storeName: str
    employeeName: str
    fileCount: int


class SummaryRow(BaseModel):
    key: str        # s7Code, p7PID or ISO date, depending on group_by
    label: str      # store name, employee name or date
    reports: int
    cash: Money
    transfer: Money
    expense: Money
    total: Money
