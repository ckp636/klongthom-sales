import hashlib
import io
import warnings
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.txn_file import TxnFile

_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_photo(content: bytes, mime: str | None) -> str:
    if not content:
        raise HTTPException(422, "ไฟล์รูปภาพว่าง")
    if len(content) > settings.PHOTO_MAX_BYTES:
        raise HTTPException(413, "รูปภาพต้องมีขนาดไม่เกิน 2 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                detected = _TYPES.get(image.format)
                if not detected or detected != mime:
                    raise HTTPException(415, "รองรับรูป JPEG, PNG และ WebP ที่ถูกต้องเท่านั้น")
                if image.width * image.height > 16_000_000 or getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(422, "รูปภาพมีขนาดใหญ่เกินไปหรือเป็นภาพเคลื่อนไหว")
                image.verify()
            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, "ไฟล์รูปภาพเสียหายหรือไม่ปลอดภัย")
    return detected


def store_photo(db: Session, tid: int, pid: int, name: str, mime: str, content: bytes) -> TxnFile:
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalars(select(TxnFile).where(
        TxnFile.f1TID == tid, TxnFile.f1Sha256 == digest,
        TxnFile.f1ExpiresAt > utcnow(), TxnFile.f1PurgedAt.is_(None),
    )).first()
    if existing is not None:
        return existing
    photo = TxnFile(
        f1TID=tid, f1Pid=pid, f1FileName=name[:255] or "evidence",
        f1Path=f"sql/{uuid4().hex}", f1MimeType=mime, f1Size=len(content),
        f1Sha256=digest, f1Tag="slip", f1Content=content,
        f1ExpiresAt=utcnow() + timedelta(days=settings.PHOTO_RETENTION_DAYS),
    )
    db.add(photo)
    db.flush()
    db.refresh(photo)
    return photo


def purge_expired(db: Session, now: datetime) -> int:
    total = 0
    for _ in range(10):
        ids = list(db.scalars(select(TxnFile.f1FID).where(
            TxnFile.f1ExpiresAt <= now, TxnFile.f1Content.is_not(None),
        ).order_by(TxnFile.f1ExpiresAt, TxnFile.f1FID).limit(100)))
        if not ids:
            break
        result = db.execute(update(TxnFile).where(
            TxnFile.f1FID.in_(ids), TxnFile.f1ExpiresAt <= now,
            TxnFile.f1Content.is_not(None),
        ).values(f1Content=None, f1PurgedAt=now).execution_options(synchronize_session=False))
        total += result.rowcount
    return total
