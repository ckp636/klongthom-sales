from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import personnel_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelCreate, PersonnelOut, PersonnelUpdate
from app.services import log_service

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("/", response_model=list[PersonnelOut])
def list_personnel(
    sid: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return personnel_repo.get_all(db, sid=sid)


@router.get("/{pid}", response_model=PersonnelOut)
def get_person(pid: int, db: Session = Depends(get_db)):
    person = personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    return person


@router.post("/", response_model=PersonnelOut, status_code=status.HTTP_201_CREATED)
def create_person(data: PersonnelCreate, db: Session = Depends(get_db)):
    person = personnel_repo.create(db, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="create",
        l9Page="/personnel", l9Component="create_personnel",
        l9Pid=person.p7PID, l9NewVal=f"{person.p7FName} {person.p7LName}",
    ))
    return person


@router.patch("/{pid}", response_model=PersonnelOut)
def update_person(pid: int, data: PersonnelUpdate, db: Session = Depends(get_db)):
    person = personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    person = personnel_repo.update(db, person, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="update",
        l9Page="/personnel", l9Component="update_personnel",
        l9Pid=person.p7PID, l9RefID=person.p7PID, l9RefTable="mod7$_Personnel",
    ))
    return person
