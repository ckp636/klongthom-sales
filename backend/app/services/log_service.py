from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import Log
from app.schemas.log import LogCreate


async def write(db: AsyncSession, data: LogCreate) -> None:
    """Append-only — never UPDATE or DELETE mod9$_Logging rows."""
    log = Log(**data.model_dump())
    db.add(log)
    # flush so the row is persisted with the parent transaction commit
    await db.flush()
