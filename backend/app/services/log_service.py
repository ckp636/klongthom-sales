from fastapi import Request
from sqlalchemy.orm import Session

from app.models.log import Log
from app.schemas.log import LogCreate


def write(db: Session, data: LogCreate, request: Request | None = None) -> None:
    """Append-only — mod9$_Logging rows are never updated or deleted
    (the database enforces this with a trigger)."""
    if request is not None:
        if data.l9IP is None:
            forwarded = request.headers.get("x-forwarded-for", "")
            data.l9IP = (forwarded.split(",")[0].strip() or (request.client.host if request.client else None))
        if data.l9UA is None:
            data.l9UA = request.headers.get("user-agent")
        if data.l9SessionID is None:
            data.l9SessionID = request.headers.get("x-session-id")
    db.add(Log(**data.to_row()))
    db.flush()
