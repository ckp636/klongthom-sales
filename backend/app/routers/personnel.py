from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories import personnel_repo
from app.schemas.log import LogCreate
from app.schemas.personnel import PersonnelCreate, PersonnelOut, PersonnelUpdate
from app.services import log_service

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("/", response_model=list[PersonnelOut])
async def list_personnel(
    sid: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    return await personnel_repo.get_all(db, sid=sid)


@router.get("/{pid}", response_model=PersonnelOut)
async def get_person(pid: int, db: AsyncSession = Depends(get_db)):
    person = await personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    return person


@router.post("/", response_model=PersonnelOut, status_code=status.HTTP_201_CREATED)
async def create_person(data: PersonnelCreate, db: AsyncSession = Depends(get_db)):
    person = await personnel_repo.create(db, data)
    await log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="create",
        l9Page="/personnel", l9Component="create_personnel",
        l9Pid=person.p7PID, l9NewVal=f"{person.p7FName} {person.p7LName}",
    ))
    return person


@router.patch("/{pid}", response_model=PersonnelOut)
async def update_person(pid: int, data: PersonnelUpdate, db: AsyncSession = Depends(get_db)):
    person = await personnel_repo.get_by_id(db, pid)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    person = await personnel_repo.update(db, person, data)
    await log_service.write(db, LogCreate(
        l9Type="audit", l9Module="personnel", l9Action="update",
        l9Page="/personnel", l9Component="update_personnel",
        l9Pid=person.p7PID, l9RefID=person.p7PID, l9RefTable="mod7$_Personnel",
    ))
    return person
