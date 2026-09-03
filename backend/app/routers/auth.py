from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import personnel_repo, store_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelOut
from app.schemas.store import StoreOut
from app.services import log_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    line_user_id: str


class DevLoginRequest(BaseModel):
    p7PID: int


class LoginResponse(BaseModel):
    personnel: PersonnelOut
    store: StoreOut


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    person = personnel_repo.get_by_line_user(db, body.line_user_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ไม่พบบัญชีผู้ใช้ กรุณาติดต่อผู้ดูแลระบบ")
    if not person.p7Status:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="บัญชีนี้ถูกระงับ")

    store = store_repo.get_by_id(db, person.p7Sid)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ไม่พบข้อมูลร้านค้า")

    person.p7LastLogin = datetime.now()
    db.flush()

    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="auth", l9Action="login",
        l9Page="/login", l9Pid=person.p7PID, l9Sid=store.s7Sid,
    ))
    return LoginResponse(
        personnel=PersonnelOut.model_validate(person),
        store=StoreOut.model_validate(store),
    )


@router.post("/login-dev", response_model=LoginResponse)
def login_dev(body: DevLoginRequest, db: Session = Depends(get_db)):
    """DEV only — ใช้ p7PID เพื่อ login โดยไม่ต้องผ่าน LINE"""
    person = personnel_repo.get_by_id(db, body.p7PID)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    store = store_repo.get_by_id(db, person.p7Sid)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return LoginResponse(
        personnel=PersonnelOut.model_validate(person),
        store=StoreOut.model_validate(store),
    )
