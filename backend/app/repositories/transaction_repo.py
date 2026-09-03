from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


def get_all(
    db: Session,
    sid: int | None = None,
    pid: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Transaction]:
    q = (
        select(Transaction)
        .options(
            selectinload(Transaction.store),
            selectinload(Transaction.personnel),
            selectinload(Transaction.files),
        )
        .order_by(Transaction.t1Date.desc())
    )
    if sid is not None:
        q = q.where(Transaction.t1Sid == sid)
    if pid is not None:
        q = q.where(Transaction.t1Pid == pid)
    if date_from is not None:
        q = q.where(Transaction.t1Date >= date_from)
    if date_to is not None:
        q = q.where(Transaction.t1Date <= date_to)
    return list(db.execute(q).scalars().all())


def get_by_id(db: Session, tid: int) -> Transaction | None:
    return db.execute(
        select(Transaction)
        .where(Transaction.t1TID == tid)
        .options(
            selectinload(Transaction.store),
            selectinload(Transaction.personnel),
            selectinload(Transaction.files),
        )
    ).scalar_one_or_none()


def create(db: Session, data: TransactionCreate) -> Transaction:
    txn = Transaction(**data.model_dump())
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


def update(db: Session, txn: Transaction, data: TransactionUpdate) -> Transaction:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(txn, field, value)
    db.flush()
    db.refresh(txn)
    return txn
