from datetime import date, datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.personnel import Personnel
from app.models.store import Store
from app.models.transaction import Transaction
from app.models.txn_file import TxnFile
from app.schemas.transaction import SummaryRow, TransactionCreate, TransactionUpdate
from app.schemas.txn_file import TxnFileCreate

_SHIFT_LETTER = {"morning": "M", "afternoon": "A", "evening": "E"}
_LOAD = (selectinload(Transaction.store), selectinload(Transaction.personnel), selectinload(Transaction.files))


class DuplicateSlot(Exception):
    """A live report already exists for this staff · store · date · shift."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _filtered(q, sid, pid, date_from, date_to, status, include_void):
    if sid is not None:
        q = q.where(Transaction.t1Sid == sid)
    if pid is not None:
        q = q.where(Transaction.t1Pid == pid)
    if date_from is not None:
        q = q.where(Transaction.t1Date >= date_from)
    if date_to is not None:
        q = q.where(Transaction.t1Date <= date_to)
    if status is not None:
        q = q.where(Transaction.t1Status == status)
    elif not include_void:
        q = q.where(Transaction.t1Status != "void")
    return q


def get_all(
    db: Session,
    sid: int | None = None,
    pid: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
    include_void: bool = False,
) -> list[Transaction]:
    q = select(Transaction).options(*_LOAD).order_by(Transaction.t1Date.desc(), Transaction.t1CreatedAt.desc())
    q = _filtered(q, sid, pid, date_from, date_to, status, include_void)
    return list(db.execute(q).scalars().all())


def get_by_id(db: Session, tid: int) -> Transaction | None:
    return db.execute(select(Transaction).where(Transaction.t1TID == tid).options(*_LOAD)).scalar_one_or_none()


def _next_tno(db: Session, store_code: str, day: date, shift: str) -> str:
    base = f"{store_code}-{day:%Y%m%d}-{_SHIFT_LETTER[shift]}"
    taken = set(db.execute(select(Transaction.t1TNo).where(Transaction.t1TNo.like(f"{base}%"))).scalars())
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def create(db: Session, store: Store, data: TransactionCreate) -> Transaction:
    txn = Transaction(
        t1TNo=_next_tno(db, store.s7Code, data.t1Date, data.t1Shift),
        t1Sid=store.s7Sid,
        t1Pid=data.t1Pid,
        t1Date=data.t1Date,
        t1Shift=data.t1Shift,
        t1Cash=data.t1Cash,
        t1Transfer=data.t1Transfer,
        t1Expense=data.t1Expense,
        t1Note=data.t1Note,
        t1QrVer=store.s7QrVer,
        t1Status="submitted",
    )
    try:
        # savepoint: a duplicate undoes only this insert, not the whole request
        with db.begin_nested():
            db.add(txn)
            db.flush()
    except IntegrityError as e:
        if "uq_t1Slot" in str(e.orig):
            raise DuplicateSlot() from e
        raise
    return get_by_id(db, txn.t1TID)


def update(db: Session, txn: Transaction, data: TransactionUpdate) -> Transaction:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.flush()
    db.refresh(txn)
    return txn


def void(db: Session, txn: Transaction, by_pid: int, reason: str) -> Transaction:
    txn.t1Status = "void"
    txn.t1VoidBy = by_pid
    txn.t1VoidAt = _utcnow()
    txn.t1VoidReason = reason
    db.flush()
    db.refresh(txn)
    return txn


def verify(db: Session, txn: Transaction, by_pid: int) -> Transaction:
    txn.t1Status = "verified"
    txn.t1VerifiedBy = by_pid
    txn.t1VerifiedAt = _utcnow()
    db.flush()
    db.refresh(txn)
    return txn


def add_file(db: Session, txn: Transaction, data: TxnFileCreate) -> TxnFile:
    f = TxnFile(f1TID=txn.t1TID, **data.model_dump())
    db.add(f)
    db.flush()
    db.refresh(f)
    return f


def summary(
    db: Session,
    group_by: Literal["store", "employee", "date"],
    date_from: date | None = None,
    date_to: date | None = None,
    sid: int | None = None,
    pid: int | None = None,
) -> list[SummaryRow]:
    """Totals for the admin dashboard. Voided reports are always excluded."""
    T = Transaction
    if group_by == "store":
        key_cols = (Store.s7Code, Store.s7Name)
        base = select(*key_cols).join(Store, Store.s7Sid == T.t1Sid)
    elif group_by == "employee":
        key_cols = (Personnel.p7PID, Personnel.p7FName, Personnel.p7LName)
        base = select(*key_cols).join(Personnel, Personnel.p7PID == T.t1Pid)
    else:
        key_cols = (T.t1Date,)
        base = select(*key_cols).select_from(T)

    q = base.add_columns(
        func.count().label("reports"),
        func.sum(T.t1Cash), func.sum(T.t1Transfer), func.sum(T.t1Expense), func.sum(T.t1Total),
    ).group_by(*key_cols).order_by(func.sum(T.t1Total).desc() if group_by != "date" else T.t1Date)
    q = _filtered(q, sid, pid, date_from, date_to, status=None, include_void=False)

    rows = []
    for r in db.execute(q).all():
        if group_by == "store":
            key, label, rest = r[0], r[1], r[2:]
        elif group_by == "employee":
            key, label, rest = str(r[0]), f"{r[1]} {r[2]}".strip(), r[3:]
        else:
            key = label = r[0].isoformat()
            rest = r[1:]
        reports, cash, transfer, expense, total = rest
        rows.append(SummaryRow(key=key, label=label, reports=reports, cash=cash,
                               transfer=transfer, expense=expense, total=total))
    return rows
