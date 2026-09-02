from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Log(Base):
    __tablename__ = quoted_name("mod9$_Logging", True)

    l9LID: Mapped[int] = mapped_column("l9LID", Integer, primary_key=True, autoincrement=True)
    l9Type: Mapped[str] = mapped_column("l9Type", String(20), nullable=False)          # info|warning|error|audit|pageview|click
    l9Page: Mapped[str | None] = mapped_column("l9Page", String(200), nullable=True)
    l9Component: Mapped[str | None] = mapped_column("l9Component", String(100), nullable=True)
    l9SessionID: Mapped[str | None] = mapped_column("l9SessionID", String(100), nullable=True)
    l9Sid: Mapped[int | None] = mapped_column("l9Sid", Integer, ForeignKey("mod7$_Store.s7Sid", ondelete="SET NULL"), nullable=True)
    l9Pid: Mapped[int | None] = mapped_column("l9Pid", Integer, ForeignKey("mod7$_Personnel.p7PID", ondelete="SET NULL"), nullable=True)
    l9Detail: Mapped[str | None] = mapped_column("l9Detail", String(2000), nullable=True)
    l9CreatedAt: Mapped[datetime] = mapped_column("l9CreatedAt", DateTime, server_default=func.now())

    store: Mapped["Store | None"] = relationship("Store", back_populates="logs")
    personnel: Mapped["Personnel | None"] = relationship("Personnel", back_populates="logs")
