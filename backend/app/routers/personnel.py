from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.personnel import Personnel
from app.repositories import personnel_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelCreate, PersonnelOut, PersonnelUpdate
from app.services import log_service

router = APIRouter(prefix="/personnel", tags=["personnel"])

_REF = "mod7$_Personnel"


@router.get("/", response_model=list[PersonnelOut])
def list_personnel(
    sid: int | None = Query(None),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    return personnel_repo.get_all(db, sid=sid, active_only=active_only)


@router.get("/{pid}", response_model=PersonnelOut)
def get_person(pid: int, db: Session = Depends(get_db)):
    person = personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Personnel not found")
    return person


@router.post("/", response_model=PersonnelOut, status_code=status.HTTP_201_CREATED)
def create_person(data: PersonnelCreate, request: Request, db: Session = Depends(get_db)):
    clash = db.execute(select(Personnel.p7PID).where(or_(
        Personnel.p7EmpCode == data.p7EmpCode,
        Personnel.p7LineUID == data.p7LineUID if data.p7LineUID else False,
        Personnel.p7User == data.p7User if data.p7User else False,
    ))).first()
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, "รหัสพนักงาน, LINE หรือชื่อผู้ใช้นี้มีอยู่แล้ว")
    person = personnel_repo.create(db, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="create",
        l9Page="/admin/personnel", l9Component="create_personnel",
        l9RefTable=_REF, l9RefID=person.p7PID,
        l9NewVal=data.model_dump(exclude={"password"}),
    ), request)
    return person


@router.patch("/{pid}", response_model=PersonnelOut)
def update_person(pid: int, data: PersonnelUpdate, request: Request, db: Session = Depends(get_db)):
    person = personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Personnel not found")
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(person, k) for k in changes}
    person = personnel_repo.update(db, person, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="update",
        l9Page="/admin/personnel", l9Component="update_personnel",
        l9RefTable=_REF, l9RefID=person.p7PID, l9OldVal=old, l9NewVal=changes,
    ), request)
    return person
