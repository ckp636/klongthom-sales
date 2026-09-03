from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Personnel(Base):
    __tablename__ = quoted_name("mod7$_Personnel", True)

    p7PID: Mapped[int] = mapped_column("p7PID", Integer, primary_key=True, autoincrement=True)
    p7Sid: Mapped[int] = mapped_column("p7Sid", Integer, ForeignKey("mod7$_Store.s7Sid"), nullable=False)
    p7EmpCode: Mapped[str] = mapped_column("p7EmpCode", String(20), nullable=False)
    p7User: Mapped[str] = mapped_column("p7User", String(50), nullable=False)
    p7PwdHash: Mapped[str] = mapped_column("p7PwdHash", String(255), nullable=False)
    p7FName: Mapped[str] = mapped_column("p7FName", String(50), nullable=False)
    p7LName: Mapped[str] = mapped_column("p7LName", String(50), nullable=False)
    p7Role: Mapped[str] = mapped_column("p7Role", String(20), nullable=False, default="staff")
    p7Phone: Mapped[str | None] = mapped_column("p7Phone", String(20), nullable=True)
    p7Email: Mapped[str | None] = mapped_column("p7Email", String(100), nullable=True)
    p7Status: Mapped[bool] = mapped_column("p7Status", Boolean, default=True, nullable=False)
    p7LastLogin: Mapped[datetime | None] = mapped_column("p7LastLogin", DateTime, nullable=True)
    p7CreatedAt: Mapped[datetime] = mapped_column("p7CreatedAt", DateTime, server_default=func.now())
    p7UpdatedAt: Mapped[datetime | None] = mapped_column("p7UpdatedAt", DateTime, nullable=True, onupdate=func.now())

    store: Mapped["Store"] = relationship("Store", back_populates="personnel")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="personnel")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="personnel")
