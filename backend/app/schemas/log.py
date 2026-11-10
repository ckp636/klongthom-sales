import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class LogCreate(BaseModel):
    l9Type: Literal["info", "warning", "error", "audit", "pageview", "click"]
    l9Module: str
    l9Action: str
    l9Page: str | None = None
    l9Component: str | None = None
    l9SessionID: str | None = None
    l9Pid: int | None = None
    l9Sid: int | None = None
    l9RefTable: str | None = None
    l9RefID: int | None = None
    # pass a dict; stored as JSON (the DB rejects non-JSON text)
    l9OldVal: dict[str, Any] | None = None
    l9NewVal: dict[str, Any] | None = None
    l9IP: str | None = None
    l9UA: str | None = None

    def to_row(self) -> dict[str, Any]:
        row = self.model_dump()
        for key in ("l9OldVal", "l9NewVal"):
            if row[key] is not None:
                row[key] = json.dumps(row[key], ensure_ascii=False, default=str)
        if row["l9UA"]:
            row["l9UA"] = row["l9UA"][:255]
        return row


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
    l9RefTable: str | None = None
    l9RefID: int | None = None
    l9OldVal: Any = None
    l9NewVal: Any = None
    l9CreatedAt: datetime

    @field_validator("l9OldVal", "l9NewVal", mode="before")
    @classmethod
    def parse_json(cls, v: Any) -> Any:
        return json.loads(v) if isinstance(v, str) else v
