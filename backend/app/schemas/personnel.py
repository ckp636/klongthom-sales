from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PersonnelBase(BaseModel):
    p7Sid: int
    p7Name: str
    p7Role: Literal["staff", "admin"] = "staff"
    p7User: str | None = None
    p7Active: bool = True


class PersonnelCreate(PersonnelBase):
    pass


class PersonnelUpdate(BaseModel):
    p7Name: str | None = None
    p7Role: Literal["staff", "admin"] | None = None
    p7User: str | None = None
    p7Active: bool | None = None


class PersonnelOut(PersonnelBase):
    model_config = ConfigDict(from_attributes=True)

    p7PID: int
    p7CreatedAt: datetime
    p7UpdatedAt: datetime
    # p7PwdHash intentionally excluded
