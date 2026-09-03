from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personnel import Personnel
from app.schemas.personnel import PersonnelCreate, PersonnelUpdate


def get_all(db: Session, sid: int | None = None) -> list[Personnel]:
    q = select(Personnel).order_by(Personnel.p7FName, Personnel.p7LName)
    if sid is not None:
        q = q.where(Personnel.p7Sid == sid)
    return list(db.execute(q).scalars().all())


def get_by_id(db: Session, pid: int) -> Personnel | None:
    return db.get(Personnel, pid)


def get_by_line_user(db: Session, line_user_id: str) -> Personnel | None:
    return db.execute(
        select(Personnel).where(Personnel.p7User == line_user_id)
    ).scalar_one_or_none()


def create(db: Session, data: PersonnelCreate) -> Personnel:
    person = Personnel(**data.model_dump())
    db.add(person)
    db.flush()
    db.refresh(person)
    return person


def update(db: Session, person: Personnel, data: PersonnelUpdate) -> Personnel:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(person, field, value)
    db.flush()
    db.refresh(person)
    return person
