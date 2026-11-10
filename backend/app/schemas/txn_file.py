from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
    f1ExpiresAt: datetime | None = None
    f1PurgedAt: datetime | None = None
    available: bool
    contentUrl: str | None = None
