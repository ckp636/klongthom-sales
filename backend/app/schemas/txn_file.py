from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TxnFileCreate(BaseModel):
    f1TID: int
    f1Pid: int | None = None
    f1Path: str
    f1MimeType: str | None = None
    f1Tag: Literal["receipt", "slip", "product", "other"] = "receipt"


class TxnFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    f1FID: int
    f1TID: int
    f1Pid: int | None
    f1Path: str
    f1MimeType: str | None
    f1Tag: str
    f1CreatedAt: datetime
