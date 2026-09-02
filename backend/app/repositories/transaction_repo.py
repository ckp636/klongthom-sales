from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


async def get_all(
    db: AsyncSession,
    sid: int | None = None,
    pid: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Transaction]:
    q = (
        select(Transaction)
        .options(selectinload(Transaction.files))
        .order_by(Transaction.t1CreatedAt.desc())
    )
    if sid is not None:
        q = q.where(Transaction.t1Sid == sid)
    if pid is not None:
        q = q.where(Transaction.t1Pid == pid)
    if date_from is not None:
        q = q.where(Transaction.t1CreatedAt >= date_from)
    if date_to is not None:
        q = q.where(Transaction.t1CreatedAt < date_to)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, tid: int) -> Transaction | None:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.t1TID == tid)
        .options(selectinload(Transaction.files))
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, data: TransactionCreate) -> Transaction:
    txn = Transaction(**data.model_dump())
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return txn


async def update(db: AsyncSession, txn: Transaction, data: TransactionUpdate) -> Transaction:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(txn, field, value)
    await db.flush()
    await db.refresh(txn)
    return txn
