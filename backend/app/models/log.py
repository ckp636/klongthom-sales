from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Log(Base):
    __tablename__ = quoted_name("mod9$_Logging", True)

    l9LID: Mapped[int] = mapped_column("l9LID", BigInteger, primary_key=True, autoincrement=True)
    l9Type: Mapped[str] = mapped_column("l9Type", String(20), nullable=False)
    l9Module: Mapped[str] = mapped_column("l9Module", String(20), nullable=False)
    l9Action: Mapped[str] = mapped_column("l9Action", String(100), nullable=False)
    l9Page: Mapped[str | None] = mapped_column("l9Page", String(200), nullable=True)
    l9Component: Mapped[str | None] = mapped_column("l9Component", String(100), nullable=True)
    l9SessionID: Mapped[str | None] = mapped_column("l9SessionID", String(64), nullable=True)
    l9Pid: Mapped[int | None] = mapped_column("l9Pid", Integer, ForeignKey("mod7$_Personnel.p7PID", ondelete="SET NULL"), nullable=True)
    l9Sid: Mapped[int | None] = mapped_column("l9Sid", Integer, ForeignKey("mod7$_Store.s7Sid", ondelete="SET NULL"), nullable=True)
    l9RefID: Mapped[int | None] = mapped_column("l9RefID", Integer, nullable=True)
    l9RefTable: Mapped[str | None] = mapped_column("l9RefTable", String(50), nullable=True)
    l9OldVal: Mapped[str | None] = mapped_column("l9OldVal", Text, nullable=True)
    l9NewVal: Mapped[str | None] = mapped_column("l9NewVal", Text, nullable=True)
    l9IP: Mapped[str | None] = mapped_column("l9IP", String(45), nullable=True)
    l9UA: Mapped[str | None] = mapped_column("l9UA", String(255), nullable=True)
    l9CreatedAt: Mapped[datetime] = mapped_column("l9CreatedAt", DateTime, server_default=func.now())

    store: Mapped["Store | None"] = relationship("Store", back_populates="logs")
    personnel: Mapped["Personnel | None"] = relationship("Personnel", back_populates="logs")
