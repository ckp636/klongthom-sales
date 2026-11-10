import hmac

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.schemas.log import LogCreate
from app.services import log_service, photo_service
from app.services.auth_service import Database

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/photos/cleanup")
def cleanup_photos(request: Request, db: Database):
    secret = settings.CRON_SECRET
    supplied = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(supplied.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(403, "Invalid scheduler credentials")
    count = photo_service.purge_expired(db, photo_service.utcnow())
    log_service.write(db, LogCreate(
        l9Type="audit", l9Module="maintenance", l9Action="purge_photos",
        l9Page="/maintenance/photos/cleanup", l9Component="daily_cleanup",
        l9NewVal={"purged": count},
    ), request)
    return {"purged": count}
