from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.models.personnel import Personnel
from app.repositories import store_repo, transaction_repo
from app.schemas.log import LogCreate
from app.schemas.transaction import (
    Status, SummaryRow, TransactionCreate, TransactionOut, TransactionUpdate,
    TransactionVoid,
)
from app.services import log_service
from app.services.security import verify_qr
from app.services.auth_service import AdminPerson, CurrentPerson, Database

router = APIRouter(prefix="/transactions", tags=["transactions"])

_REF = "mod1$_Transaction"


def _amounts(t: Transaction) -> dict:
    return {"t1TNo": t.t1TNo, "t1Cash": t.t1Cash, "t1Transfer": t.t1Transfer,
            "t1Expense": t.t1Expense, "t1Total": t.t1Total, "t1Status": t.t1Status}


def _get_or_404(db: Session, tid: int, person: Personnel) -> Transaction:
    txn = transaction_repo.get_by_id(db, tid)
    if not txn:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    if person.p7Role != "admin" and txn.t1Pid != person.p7PID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")
    return txn


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    db: Database,
    person: CurrentPerson,
    sid: int | None = Query(None),
    pid: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status_: Status | None = Query(None, alias="status"),
    include_void: bool = Query(False),
):
    if person.p7Role != "admin":
        pid = person.p7PID
    return transaction_repo.get_all(db, sid=sid, pid=pid, date_from=date_from, date_to=date_to,
                                    status=status_, include_void=include_void)


@router.get("/summary", response_model=list[SummaryRow])
def summary(
    db: Database,
    person: AdminPerson,
    group_by: Literal["store", "employee", "date"] = Query("store"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sid: int | None = Query(None),
    pid: int | None = Query(None),
):
    """Admin dashboard totals (voided reports excluded)."""
    return transaction_repo.summary(db, group_by, date_from=date_from, date_to=date_to, sid=sid, pid=pid)


@router.get("/{tid}", response_model=TransactionOut)
def get_transaction(tid: int, db: Database, person: CurrentPerson):
    return _get_or_404(db, tid, person)


@router.post("/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, request: Request, db: Database, person: CurrentPerson):
    store = store_repo.get_by_code(db, data.storeCode)
    if not store or not store.s7Status:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบร้านค้า หรือร้านถูกปิดใช้งาน")
    if not verify_qr(store.s7Code, store.s7QrVer, data.qrSig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "QR code ไม่ถูกต้องหรือหมดอายุ กรุณาสแกนใหม่")
    try:
        txn = transaction_repo.create(db, store, data, person.p7PID)
    except transaction_repo.DuplicateSlot:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "ส่งยอดรอบนี้ของร้านนี้ไปแล้ว — ถ้าต้องการแก้ไข ให้แอดมินยกเลิกรายการเดิมก่อน",
        )
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="create",
        l9Page="/form", l9Component="btn_submit",
        l9Sid=txn.t1Sid, l9Pid=txn.t1Pid, l9RefTable=_REF, l9RefID=txn.t1TID,
        l9NewVal=_amounts(txn),
    ), request)
    return txn


@router.patch("/{tid}", response_model=TransactionOut)
def update_transaction(tid: int, data: TransactionUpdate, request: Request, db: Database, person: CurrentPerson):
    txn = _get_or_404(db, tid, person)
    if txn.t1Status == "void":
        raise HTTPException(status.HTTP_409_CONFLICT, "รายการนี้ถูกยกเลิกแล้ว")
    old = {"t1Note": txn.t1Note}
    txn = transaction_repo.update(db, txn, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="update",
        l9Page="/history", l9Component="update_note",
        l9Sid=txn.t1Sid, l9Pid=person.p7PID, l9RefTable=_REF, l9RefID=txn.t1TID,
        l9OldVal=old, l9NewVal={"t1Note": txn.t1Note},
    ), request)
    return txn


@router.post("/{tid}/void", response_model=TransactionOut)
def void_transaction(tid: int, data: TransactionVoid, request: Request, db: Database, person: AdminPerson):
    txn = _get_or_404(db, tid, person)
    if txn.t1Status == "void":
        raise HTTPException(status.HTTP_409_CONFLICT, "รายการนี้ถูกยกเลิกแล้ว")
    old_status = txn.t1Status
    txn = transaction_repo.void(db, txn, person.p7PID, data.reason)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="void",
        l9Page="/admin", l9Component="btn_void",
        l9Sid=txn.t1Sid, l9Pid=person.p7PID, l9RefTable=_REF, l9RefID=txn.t1TID,
        l9OldVal={"t1Status": old_status}, l9NewVal={"t1Status": "void", "t1VoidReason": data.reason},
    ), request)
    return txn


@router.post("/{tid}/verify", response_model=TransactionOut)
def verify_transaction(tid: int, request: Request, db: Database, person: AdminPerson):
    txn = _get_or_404(db, tid, person)
    if txn.t1Status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, f"ยืนยันได้เฉพาะรายการที่ส่งแล้ว (สถานะปัจจุบัน: {txn.t1Status})")
    txn = transaction_repo.verify(db, txn, person.p7PID)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="verify",
        l9Page="/admin", l9Component="btn_verify",
        l9Sid=txn.t1Sid, l9Pid=person.p7PID, l9RefTable=_REF, l9RefID=txn.t1TID,
        l9OldVal={"t1Status": "submitted"}, l9NewVal={"t1Status": "verified"},
    ), request)
    return txn
