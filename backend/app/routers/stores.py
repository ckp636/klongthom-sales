from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories import store_repo
from app.schemas.log import LogCreate
from app.schemas.store import StoreCreate, StoreOut, StoreQrOut, StoreUpdate
from app.services import log_service
from app.services.security import qr_checks_enabled, qr_sig

router = APIRouter(prefix="/stores", tags=["stores"])

_REF = "mod7$_Store"


def _get_or_404(db: Session, sid: int):
    store = store_repo.get_by_id(db, sid)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Store not found")
    return store


@router.get("/", response_model=list[StoreOut])
def list_stores(active_only: bool = Query(False), db: Session = Depends(get_db)):
    return store_repo.get_all(db, active_only=active_only)


@router.get("/{sid}", response_model=StoreOut)
def get_store(sid: int, db: Session = Depends(get_db)):
    return _get_or_404(db, sid)


@router.post("/", response_model=StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(data: StoreCreate, request: Request, db: Session = Depends(get_db)):
    if store_repo.get_by_code(db, data.s7Code):
        raise HTTPException(status.HTTP_409_CONFLICT, "Store code already exists")
    store = store_repo.create(db, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="store", l9Action="create",
        l9Page="/admin/stores", l9Component="create_store",
        l9Sid=store.s7Sid, l9RefTable=_REF, l9RefID=store.s7Sid,
        l9NewVal=data.model_dump(),
    ), request)
    return store


@router.patch("/{sid}", response_model=StoreOut)
def update_store(sid: int, data: StoreUpdate, request: Request, db: Session = Depends(get_db)):
    store = _get_or_404(db, sid)
    changes = data.model_dump(exclude_unset=True)
    if "s7Code" in changes and changes["s7Code"] != store.s7Code and store_repo.get_by_code(db, changes["s7Code"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "Store code already exists")
    old = {k: getattr(store, k) for k in changes}
    store = store_repo.update(db, store, data)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="store", l9Action="update",
        l9Page="/admin/stores", l9Component="update_store",
        l9Sid=store.s7Sid, l9RefTable=_REF, l9RefID=store.s7Sid,
        l9OldVal=old, l9NewVal=changes,
    ), request)
    return store


@router.get("/{sid}/qr", response_model=StoreQrOut)
def get_store_qr(sid: int, db: Session = Depends(get_db)):
    """Signature to print in the store's QR code (?shop=…&sig=…)."""
    if not qr_checks_enabled():
        raise HTTPException(status.HTTP_409_CONFLICT, "QR_HMAC_SECRET is not configured")
    store = _get_or_404(db, sid)
    sig = qr_sig(store.s7Code, store.s7QrVer)
    return StoreQrOut(s7Code=store.s7Code, s7QrVer=store.s7QrVer, qrSig=sig,
                      qrQuery=f"?shop={store.s7Code}&sig={sig}")


@router.post("/{sid}/qr/rotate", response_model=StoreOut)
def rotate_store_qr(sid: int, request: Request, db: Session = Depends(get_db)):
    """Invalidate every QR printed for this store (bumps s7QrVer)."""
    store = _get_or_404(db, sid)
    old_ver = store.s7QrVer
    store = store_repo.rotate_qr(db, store)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="store", l9Action="rotate_qr",
        l9Page="/admin/stores", l9Component="btn_rotate_qr",
        l9Sid=store.s7Sid, l9RefTable=_REF, l9RefID=store.s7Sid,
        l9OldVal={"s7QrVer": old_ver}, l9NewVal={"s7QrVer": store.s7QrVer},
    ), request)
    return store
