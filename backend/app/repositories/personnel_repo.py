from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personnel import Personnel
from app.schemas.personnel import PersonnelCreate, PersonnelUpdate
from app.services.security import hash_password


def get_all(db: Session, sid: int | None = None, active_only: bool = False) -> list[Personnel]:
    q = select(Personnel).order_by(Personnel.p7FName, Personnel.p7LName)
    if sid is not None:
        q = q.where(Personnel.p7Sid == sid)
    if active_only:
        q = q.where(Personnel.p7Status == True)  # noqa: E712
    return list(db.execute(q).scalars().all())


def get_by_id(db: Session, pid: int) -> Personnel | None:
    return db.get(Personnel, pid)


def get_by_line_uid(db: Session, line_uid: str) -> Personnel | None:
    return db.execute(select(Personnel).where(Personnel.p7LineUID == line_uid)).scalar_one_or_none()


def get_first_by_role(db: Session, role: str) -> Personnel | None:
    return db.execute(
        select(Personnel)
        .where(Personnel.p7Role == role, Personnel.p7Status == True)  # noqa: E712
        .order_by(Personnel.p7PID)
    ).scalars().first()


def create(db: Session, data: PersonnelCreate) -> Personnel:
    fields = data.model_dump(exclude={"password"})
    person = Personnel(**fields, p7PwdHash=hash_password(data.password) if data.password else None)
    db.add(person)
    db.flush()
    db.refresh(person)
    return person


def update(db: Session, person: Personnel, data: PersonnelUpdate) -> Personnel:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    db.flush()
    db.refresh(person)
    return person
