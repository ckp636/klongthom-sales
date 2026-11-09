from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.personnel import Personnel
from app.repositories import personnel_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelOut
from app.schemas.store import StoreOut
from app.services import log_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    line_user_id: str


class DevLoginRequest(BaseModel):
    """Pick a person by id, or the first active person with this role."""

    p7PID: int | None = None
    role: Literal["staff", "admin"] | None = None

    @model_validator(mode="after")
    def one_of(self) -> "DevLoginRequest":
        if (self.p7PID is None) == (self.role is None):
            raise ValueError("send exactly one of p7PID or role")
        return self


class LoginResponse(BaseModel):
    personnel: PersonnelOut
    store: StoreOut | None = None  # home store, if the person has one


def _finish_login(db: Session, person: Personnel, method: str, request: Request) -> LoginResponse:
    if not person.p7Status:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "บัญชีนี้ถูกระงับ")
    person.p7LastLogin = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="auth", l9Action="login",
        l9Page="/login", l9Component="btn_line_login" if method == "line" else "btn_dev_login",
        l9Pid=person.p7PID, l9Sid=person.p7Sid, l9NewVal={"method": method},
    ), request)
    return LoginResponse(
        personnel=PersonnelOut.model_validate(person),
        store=StoreOut.model_validate(person.store) if person.store else None,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # NOTE: line_user_id is trusted as sent. Before production, verify a LIFF
    # ID token with LINE instead of accepting the raw userId.
    person = personnel_repo.get_by_line_uid(db, body.line_user_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบัญชีผู้ใช้ กรุณาติดต่อผู้ดูแลระบบ")
    return _finish_login(db, person, "line", request)


@router.post("/login-dev", response_model=LoginResponse)
def login_dev(body: DevLoginRequest, request: Request, db: Session = Depends(get_db)):
    """DEV only (DEV_LOGIN_ENABLED=true) — log in without LINE."""
    if not settings.DEV_LOGIN_ENABLED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    person = (personnel_repo.get_by_id(db, body.p7PID) if body.p7PID is not None
              else personnel_repo.get_first_by_role(db, body.role))
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Personnel not found")
    return _finish_login(db, person, "dev", request)
