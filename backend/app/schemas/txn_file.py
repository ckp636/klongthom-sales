from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MimeType = Literal["image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"]


class TxnFileCreate(BaseModel):
    """Metadata for a file already uploaded to object storage."""

    f1Pid: int | None = None
    f1FileName: str = Field(min_length=1, max_length=255)
    f1Path: str = Field(min_length=1, max_length=500)
    f1MimeType: MimeType
    f1Size: int | None = Field(None, ge=1, le=10 * 1024 * 1024)
    f1Sha256: str | None = Field(None, pattern=r"^[0-9A-Fa-f]{64}$")
    f1Tag: Literal["receipt", "slip", "product", "other"] = "slip"


class TxnFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    f1FID: int
    f1TID: int
    f1Pid: int | None
    f1FileName: str
    f1Path: str
    f1MimeType: str
    f1Size: int | None
    f1Tag: str
    f1CreatedAt: datetime
