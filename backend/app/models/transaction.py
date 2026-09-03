from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Transaction(Base):
    __tablename__ = quoted_name("mod1$_Transaction", True)

    t1TID: Mapped[int] = mapped_column("t1TID", Integer, primary_key=True, autoincrement=True)
    t1TNo: Mapped[str] = mapped_column("t1TNo", String(30), nullable=False)
    t1Sid: Mapped[int] = mapped_column("t1Sid", Integer, ForeignKey("mod7$_Store.s7Sid"), nullable=False)
    t1Pid: Mapped[int] = mapped_column("t1Pid", Integer, ForeignKey("mod7$_Personnel.p7PID"), nullable=False)
    t1Date: Mapped[datetime] = mapped_column("t1Date", DateTime, nullable=False)
    t1Shift: Mapped[str] = mapped_column("t1Shift", String(15), nullable=False)
    t1Sub: Mapped[Decimal] = mapped_column("t1Sub", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Disc: Mapped[Decimal] = mapped_column("t1Disc", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Tax: Mapped[Decimal] = mapped_column("t1Tax", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Total: Mapped[Decimal] = mapped_column("t1Total", Numeric(12, 2), nullable=False)
    t1PayMethod: Mapped[str] = mapped_column("t1PayMethod", String(20), nullable=False)
    t1PayStatus: Mapped[str] = mapped_column("t1PayStatus", String(20), nullable=False, default="paid")
    t1CustName: Mapped[str | None] = mapped_column("t1CustName", String(100), nullable=True)
    t1CustPhone: Mapped[str | None] = mapped_column("t1CustPhone", String(20), nullable=True)
    t1Note: Mapped[str | None] = mapped_column("t1Note", Text, nullable=True)
    t1CreatedAt: Mapped[datetime] = mapped_column("t1CreatedAt", DateTime, server_default=func.now())
    t1UpdatedAt: Mapped[datetime | None] = mapped_column("t1UpdatedAt", DateTime, nullable=True, onupdate=func.now())

    store: Mapped["Store"] = relationship("Store", back_populates="transactions")
    personnel: Mapped["Personnel"] = relationship("Personnel", back_populates="transactions")
    files: Mapped[list["TxnFile"]] = relationship("TxnFile", back_populates="transaction", cascade="all, delete-orphan")
