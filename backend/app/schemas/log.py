from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogCreate(BaseModel):
    l9Type: Literal["info", "warning", "error", "audit", "pageview", "click"]
    l9Page: str | None = None
    l9Component: str | None = None
    l9SessionID: str | None = None
    l9Sid: int | None = None
    l9Pid: int | None = None
    l9Detail: str | None = None


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    l9LID: int
    l9Type: str
    l9Page: str | None
    l9Component: str | None
    l9SessionID: str | None
    l9Sid: int | None
    l9Pid: int | None
    l9Detail: str | None
    l9CreatedAt: datetime
