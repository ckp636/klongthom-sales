from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class TransactionCreate(BaseModel):
    t1TNo: str
    t1Sid: int
    t1Pid: int
    t1Date: datetime
    t1Shift: Literal["morning", "afternoon", "evening"]
    t1Sub: Decimal
    t1Disc: Decimal = Decimal("0")
    t1Tax: Decimal = Decimal("0")
    t1Total: Decimal
    t1PayMethod: Literal["cash", "card", "transfer", "qr"]
    t1PayStatus: Literal["pending", "paid", "refunded", "void"] = "paid"
    t1CustName: str | None = None
    t1CustPhone: str | None = None
    t1Note: str | None = None

    @model_validator(mode="after")
    def validate_total(self) -> "TransactionCreate":
        expected = self.t1Sub - self.t1Disc + self.t1Tax
        if abs(self.t1Total - expected) > Decimal("0.01"):
            raise ValueError("t1Total must equal t1Sub - t1Disc + t1Tax")
        return self


class TransactionUpdate(BaseModel):
    t1PayStatus: Literal["pending", "paid", "refunded", "void"] | None = None
    t1Note: str | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    t1TID: int
    t1TNo: str
    t1Sid: int
    t1Pid: int
    t1Date: datetime
    t1Shift: str
    t1Sub: Decimal
    t1Disc: Decimal
    t1Tax: Decimal
    t1Total: Decimal
    t1PayMethod: str
    t1PayStatus: str
    t1CustName: str | None = None
    t1CustPhone: str | None = None
    t1Note: str | None = None
    t1CreatedAt: datetime
    t1UpdatedAt: datetime | None = None
