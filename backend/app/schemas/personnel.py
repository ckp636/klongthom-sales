from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PersonnelBase(BaseModel):
    p7Sid: int | None = None
    p7EmpCode: str = Field(min_length=1, max_length=20)
    p7LineUID: str | None = Field(None, max_length=64)
    p7User: str | None = Field(None, max_length=50)
    p7FName: str = Field(min_length=1, max_length=50)
    p7LName: str = Field("", max_length=50)
    p7Nick: str | None = Field(None, max_length=50)
    p7Role: Literal["staff", "admin"] = "staff"
    p7Phone: str | None = None
    p7Email: str | None = None
    p7Status: bool = True


class PersonnelCreate(PersonnelBase):
    # plain text in, hashed by the API; never stored or returned as-is
    password: str | None = Field(None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def needs_login_method(self) -> "PersonnelCreate":
        if not self.p7LineUID and not (self.p7User and self.password):
            raise ValueError("ต้องมี p7LineUID หรือ p7User + password อย่างน้อยหนึ่งอย่าง")
        if self.password and not self.p7User:
            raise ValueError("password requires p7User")
        return self


class PersonnelUpdate(BaseModel):
    p7Sid: int | None = None
    p7LineUID: str | None = Field(None, max_length=64)
    p7FName: str | None = Field(None, min_length=1, max_length=50)
    p7LName: str | None = Field(None, max_length=50)
    p7Nick: str | None = None
    p7Role: Literal["staff", "admin"] | None = None
    p7Phone: str | None = None
    p7Email: str | None = None
    p7Status: bool | None = None

    @model_validator(mode="after")
    def required_values(self) -> "PersonnelUpdate":
        for field in ("p7FName", "p7LName", "p7Role", "p7Status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class PersonnelOut(PersonnelBase):
    """p7PwdHash is intentionally not part of any response schema."""

    model_config = ConfigDict(from_attributes=True)

    p7PID: int
    fullName: str
    p7LastLogin: datetime | None = None
    p7CreatedAt: datetime
    p7UpdatedAt: datetime | None = None
