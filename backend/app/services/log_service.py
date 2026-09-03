from sqlalchemy.orm import Session

from app.models.log import Log
from app.schemas.log import LogCreate


def write(db: Session, data: LogCreate) -> None:
    """Append-only — never UPDATE or DELETE mod9$_Logging rows."""
    log = Log(**data.model_dump())
    db.add(log)
    db.flush()
