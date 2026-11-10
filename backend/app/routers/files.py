from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from sqlalchemy import select

from app.models.txn_file import TxnFile
from app.routers.transactions import _get_or_404
from app.schemas.log import LogCreate
from app.schemas.txn_file import TxnFileOut
from app.services import log_service, photo_service
from app.services.auth_service import CurrentPerson, Database
from app.core.config import settings

router = APIRouter(prefix="/transactions", tags=["files"])


@router.get("/{tid}/files", response_model=list[TxnFileOut])
def list_files(tid: int, db: Database, person: CurrentPerson):
    return _get_or_404(db, tid, person).files


@router.post("/{tid}/files", response_model=TxnFileOut, status_code=201)
def upload_photo(tid: int, file: UploadFile, request: Request, db: Database, person: CurrentPerson):
    txn = _get_or_404(db, tid, person)
    if txn.t1Status == "void":
        raise HTTPException(409, "ไม่สามารถแนบรูปกับรายการที่ยกเลิกแล้ว")
    try:
        content = file.file.read(settings.PHOTO_MAX_BYTES + 1)
    finally:
        file.file.close()
    mime = photo_service.validate_photo(content, file.content_type)
    photo = photo_service.store_photo(db, tid, person.p7PID, file.filename or "evidence", mime, content)
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="transaction", l9Action="upload_photo",
        l9Page="/form", l9Component="evidence_photo", l9Pid=person.p7PID,
        l9Sid=txn.t1Sid, l9RefTable="mod1$_TxnFile", l9RefID=photo.f1FID,
        l9NewVal={"f1TID": tid, "f1Size": photo.f1Size, "f1Sha256": photo.f1Sha256},
    ), request)
    return photo


@router.get("/{tid}/files/{fid}/content")
def photo_content(tid: int, fid: int, db: Database, person: CurrentPerson):
    _get_or_404(db, tid, person)
    photo = db.scalar(select(TxnFile).where(TxnFile.f1TID == tid, TxnFile.f1FID == fid))
    if not photo:
        raise HTTPException(404, "Photo not found")
    if not photo.available:
        raise HTTPException(410, "รูปหมดอายุหรือไม่มีไฟล์รูปที่จัดเก็บไว้")
    content = db.scalar(select(TxnFile.f1Content).where(
        TxnFile.f1FID == fid, TxnFile.f1ExpiresAt > photo_service.utcnow(),
        TxnFile.f1PurgedAt.is_(None),
    ))
    if content is None:
        raise HTTPException(410, "ไม่มีไฟล์รูปที่จัดเก็บไว้")
    return Response(content, media_type=photo.f1MimeType, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    })
