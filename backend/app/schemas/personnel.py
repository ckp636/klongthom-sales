from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PersonnelBase(BaseModel):
    p7Sid: int
    p7EmpCode: str
    p7User: str
    p7FName: str
    p7LName: str
    p7Role: Literal["staff", "admin"] = "staff"
    p7Phone: str | None = None
    p7Email: str | None = None
    p7Status: bool = True


class PersonnelCreate(PersonnelBase):
    p7PwdHash: str


class PersonnelUpdate(BaseModel):
    p7FName: str | None = None
    p7LName: str | None = None
    p7Role: Literal["staff", "admin"] | None = None
    p7Phone: str | None = None
    p7Email: str | None = None
    p7Status: bool | None = None


class PersonnelOut(PersonnelBase):
    model_config = ConfigDict(from_attributes=True)

    p7PID: int
    p7LastLogin: datetime | None = None
    p7CreatedAt: datetime
    p7UpdatedAt: datetime | None = None
    # p7PwdHash intentionally excluded
