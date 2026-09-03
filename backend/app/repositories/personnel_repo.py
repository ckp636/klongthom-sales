from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personnel import Personnel
from app.schemas.personnel import PersonnelCreate, PersonnelUpdate


async def get_all(db: AsyncSession, sid: int | None = None) -> list[Personnel]:
    q = select(Personnel).order_by(Personnel.p7FName, Personnel.p7LName)
    if sid is not None:
        q = q.where(Personnel.p7Sid == sid)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, pid: int) -> Personnel | None:
    return await db.get(Personnel, pid)


async def get_by_line_user(db: AsyncSession, line_user_id: str) -> Personnel | None:
    result = await db.execute(select(Personnel).where(Personnel.p7User == line_user_id))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: PersonnelCreate) -> Personnel:
    person = Personnel(**data.model_dump())
    db.add(person)
    await db.flush()
    await db.refresh(person)
    return person


async def update(db: AsyncSession, person: Personnel, data: PersonnelUpdate) -> Personnel:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(person, field, value)
    await db.flush()
    await db.refresh(person)
    return person
