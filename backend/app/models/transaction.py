from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Transaction(Base):
    __tablename__ = quoted_name("mod1$_Transaction", True)

    t1TID: Mapped[int] = mapped_column("t1TID", Integer, primary_key=True, autoincrement=True)
    t1Sid: Mapped[int] = mapped_column("t1Sid", Integer, ForeignKey("mod7$_Store.s7Sid"), nullable=False)
    t1Pid: Mapped[int] = mapped_column("t1Pid", Integer, ForeignKey("mod7$_Personnel.p7PID"), nullable=False)
    t1Shift: Mapped[str] = mapped_column("t1Shift", String(20), nullable=False)           # morning|afternoon|evening
    t1PayMethod: Mapped[str] = mapped_column("t1PayMethod", String(20), nullable=False)   # cash|card|transfer|qr
    t1PayStatus: Mapped[str] = mapped_column("t1PayStatus", String(20), nullable=False, default="paid")  # pending|paid|refunded|void
    t1Sub: Mapped[Decimal] = mapped_column("t1Sub", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Disc: Mapped[Decimal] = mapped_column("t1Disc", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Tax: Mapped[Decimal] = mapped_column("t1Tax", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Total: Mapped[Decimal] = mapped_column("t1Total", Numeric(12, 2), nullable=False)
    t1Note: Mapped[str | None] = mapped_column("t1Note", String(500), nullable=True)
    t1CreatedAt: Mapped[datetime] = mapped_column("t1CreatedAt", DateTime, server_default=func.now())
    t1UpdatedAt: Mapped[datetime] = mapped_column("t1UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

    store: Mapped["Store"] = relationship("Store", back_populates="transactions")
    personnel: Mapped["Personnel"] = relationship("Personnel", back_populates="transactions")
    files: Mapped[list["TxnFile"]] = relationship("TxnFile", back_populates="transaction", cascade="all, delete-orphan")
