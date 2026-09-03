from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LogCreate(BaseModel):
    l9Type: Literal["info", "warning", "error", "audit", "pageview", "click"]
    l9Module: str
    l9Action: str
    l9Page: str | None = None
    l9Component: str | None = None
    l9SessionID: str | None = None
    l9Pid: int | None = None
    l9Sid: int | None = None
    l9RefID: int | None = None
    l9RefTable: str | None = None
    l9OldVal: str | None = None
    l9NewVal: str | None = None
    l9IP: str | None = None
    l9UA: str | None = None


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    l9LID: int
    l9Type: str
    l9Module: str
    l9Action: str
    l9Page: str | None = None
    l9Component: str | None = None
    l9SessionID: str | None = None
    l9Pid: int | None = None
    l9Sid: int | None = None
    l9RefID: int | None = None
    l9RefTable: str | None = None
    l9OldVal: str | None = None
    l9NewVal: str | None = None
    l9CreatedAt: datetime
