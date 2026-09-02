from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store
from app.schemas.store import StoreCreate, StoreUpdate


async def get_all(db: AsyncSession) -> list[Store]:
    result = await db.execute(select(Store).order_by(Store.s7Code))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, sid: int) -> Store | None:
    return await db.get(Store, sid)


async def get_by_code(db: AsyncSession, code: str) -> Store | None:
    result = await db.execute(select(Store).where(Store.s7Code == code))
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: StoreCreate) -> Store:
    store = Store(**data.model_dump())
    db.add(store)
    await db.flush()
    await db.refresh(store)
    return store


async def update(db: AsyncSession, store: Store, data: StoreUpdate) -> Store:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(store, field, value)
    await db.flush()
    await db.refresh(store)
    return store
