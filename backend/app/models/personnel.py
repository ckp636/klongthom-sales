from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Personnel(Base):
    __tablename__ = quoted_name("mod7$_Personnel", True)

    p7PID: Mapped[int] = mapped_column("p7PID", Integer, primary_key=True, autoincrement=True)
    p7Sid: Mapped[int] = mapped_column("p7Sid", Integer, ForeignKey("mod7$_Store.s7Sid"), nullable=False)
    p7Name: Mapped[str] = mapped_column("p7Name", String(200), nullable=False)
    p7Role: Mapped[str] = mapped_column("p7Role", String(20), nullable=False, default="staff")  # staff | admin
    p7User: Mapped[str | None] = mapped_column("p7User", String(100), nullable=True)            # LINE userId
    p7PwdHash: Mapped[str | None] = mapped_column("p7PwdHash", String(255), nullable=True)
    p7Active: Mapped[bool] = mapped_column("p7Active", Boolean, default=True, nullable=False)
    p7CreatedAt: Mapped[datetime] = mapped_column("p7CreatedAt", DateTime, server_default=func.now())
    p7UpdatedAt: Mapped[datetime] = mapped_column("p7UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

    store: Mapped["Store"] = relationship("Store", back_populates="personnel")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="personnel")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="personnel")
