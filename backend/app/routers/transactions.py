from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import transaction_repo
from app.schemas.log import LogCreate
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.schemas.txn_file import TxnFileOut
from app.services import log_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    sid: int | None = Query(None),
    pid: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return transaction_repo.get_all(db, sid=sid, pid=pid, date_from=date_from, date_to=date_to)


@router.get("/{tid}", response_model=TransactionOut)
def get_transaction(tid: int, db: Session = Depends(get_db)):
    txn = transaction_repo.get_by_id(db, tid)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


@router.get("/{tid}/files", response_model=list[TxnFileOut])
def get_transaction_files(tid: int, db: Session = Depends(get_db)):
    txn = transaction_repo.get_by_id(db, tid)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn.files


@router.post("/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    txn = transaction_repo.create(db, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="create",
        l9Page="/transactions", l9Component="create_transaction",
        l9Sid=txn.t1Sid, l9Pid=txn.t1Pid,
        l9RefID=txn.t1TID, l9RefTable="mod1$_Transaction",
        l9NewVal=str(txn.t1Total),
    ))
    return txn


@router.patch("/{tid}", response_model=TransactionOut)
def update_transaction(tid: int, data: TransactionUpdate, db: Session = Depends(get_db)):
    txn = transaction_repo.get_by_id(db, tid)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    old_status = txn.t1PayStatus
    txn = transaction_repo.update(db, txn, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="update",
        l9Page="/transactions", l9Component="update_transaction",
        l9Sid=txn.t1Sid, l9Pid=txn.t1Pid,
        l9RefID=txn.t1TID, l9RefTable="mod1$_Transaction",
        l9OldVal=old_status, l9NewVal=txn.t1PayStatus,
    ))
    return txn
