from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store import Store
from app.schemas.store import StoreCreate, StoreUpdate


def get_all(db: Session) -> list[Store]:
    return list(db.execute(select(Store).order_by(Store.s7Code)).scalars().all())


def get_by_id(db: Session, sid: int) -> Store | None:
    return db.get(Store, sid)


def get_by_code(db: Session, code: str) -> Store | None:
    return db.execute(select(Store).where(Store.s7Code == code)).scalar_one_or_none()


def create(db: Session, data: StoreCreate) -> Store:
    store = Store(**data.model_dump())
    db.add(store)
    db.flush()
    db.refresh(store)
    return store


def update(db: Session, store: Store, data: StoreUpdate) -> Store:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(store, field, value)
    db.flush()
    db.refresh(store)
    return store
