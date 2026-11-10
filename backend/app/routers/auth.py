from datetime import datetime, timezone
import os
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.personnel import Personnel
from app.repositories import personnel_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelOut
from app.schemas.store import StoreOut
from app.services import log_service
from app.services.auth_service import (
    CurrentPerson, Database, clear_session, issue_session, verify_line_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=8192)


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


def _finish_login(db: Session, person: Personnel, method: str, request: Request, response: Response) -> LoginResponse:
    if not person.p7Status:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "บัญชีนี้ถูกระงับ")
    person.p7LastLogin = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="auth", l9Action="login",
        l9Page="/login", l9Component="btn_line_login" if method == "line" else "btn_dev_login",
        l9Pid=person.p7PID, l9Sid=person.p7Sid, l9NewVal={"method": method},
    ), request)
    issue_session(response, person.p7PID)
    return _login_response(person)


def _login_response(person: Personnel) -> LoginResponse:
    return LoginResponse(
        personnel=PersonnelOut.model_validate(person),
        store=StoreOut.model_validate(person.store) if person.store else None,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Database):
    line_user_id = verify_line_token(body.id_token)
    person = personnel_repo.get_by_line_uid(db, line_user_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบัญชีผู้ใช้ กรุณาติดต่อผู้ดูแลระบบ")
    return _finish_login(db, person, "line", request, response)


@router.post("/login-dev", response_model=LoginResponse)
def login_dev(body: DevLoginRequest, request: Request, response: Response, db: Database):
    """DEV only (DEV_LOGIN_ENABLED=true) — log in without LINE."""
    if not settings.DEV_LOGIN_ENABLED or os.getenv("VERCEL"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    person = (personnel_repo.get_by_id(db, body.p7PID) if body.p7PID is not None
              else personnel_repo.get_first_by_role(db, body.role))
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Personnel not found")
    return _finish_login(db, person, "dev", request, response)


@router.get("/me", response_model=LoginResponse)
def me(person: CurrentPerson):
    return _login_response(person)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, person: CurrentPerson, db: Database):
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="auth", l9Action="logout", l9Pid=person.p7PID,
        l9Page="/login", l9Component="btn_logout",
    ), request)
    clear_session(response)
