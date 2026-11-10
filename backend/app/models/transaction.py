from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Computed, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Transaction(Base):
    """One shift report: a staff member's cash + transfer − expense for one
    store, business date and shift."""

    __tablename__ = quoted_name("mod1$_Transaction", True)

    t1TID: Mapped[int] = mapped_column("t1TID", Integer, primary_key=True, autoincrement=True)
    t1TNo: Mapped[str] = mapped_column("t1TNo", String(64), nullable=False, unique=True)
    t1Sid: Mapped[int] = mapped_column("t1Sid", Integer, ForeignKey("mod7$_Store.s7Sid"), nullable=False)
    t1Pid: Mapped[int] = mapped_column("t1Pid", Integer, ForeignKey("mod7$_Personnel.p7PID"), nullable=False)
    t1Date: Mapped[date] = mapped_column("t1Date", Date, nullable=False)
    t1Shift: Mapped[str] = mapped_column("t1Shift", String(15), nullable=False)
    t1Cash: Mapped[Decimal] = mapped_column("t1Cash", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Transfer: Mapped[Decimal] = mapped_column("t1Transfer", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Expense: Mapped[Decimal] = mapped_column("t1Expense", Numeric(12, 2), nullable=False, default=Decimal("0"))
    t1Total: Mapped[Decimal] = mapped_column(
        "t1Total", Numeric(12, 2), Computed("t1Cash + t1Transfer - t1Expense", persisted=True)
    )
    t1Status: Mapped[str] = mapped_column("t1Status", String(15), nullable=False, default="submitted")
    t1Note: Mapped[str | None] = mapped_column("t1Note", String(500), nullable=True)
    t1QrVer: Mapped[int | None] = mapped_column("t1QrVer", Integer, nullable=True)
    t1VerifiedBy: Mapped[int | None] = mapped_column("t1VerifiedBy", Integer, ForeignKey("mod7$_Personnel.p7PID"), nullable=True)
    t1VerifiedAt: Mapped[datetime | None] = mapped_column("t1VerifiedAt", DateTime, nullable=True)
    t1VoidBy: Mapped[int | None] = mapped_column("t1VoidBy", Integer, ForeignKey("mod7$_Personnel.p7PID"), nullable=True)
    t1VoidAt: Mapped[datetime | None] = mapped_column("t1VoidAt", DateTime, nullable=True)
    t1VoidReason: Mapped[str | None] = mapped_column("t1VoidReason", String(200), nullable=True)
    t1CreatedAt: Mapped[datetime] = mapped_column("t1CreatedAt", DateTime, server_default=func.sysutcdatetime())
    t1UpdatedAt: Mapped[datetime | None] = mapped_column("t1UpdatedAt", DateTime, nullable=True, onupdate=func.sysutcdatetime())

    store: Mapped["Store"] = relationship("Store", back_populates="transactions")
    personnel: Mapped["Personnel"] = relationship("Personnel", back_populates="transactions", foreign_keys=[t1Pid])
    files: Mapped[list["TxnFile"]] = relationship("TxnFile", back_populates="transaction", cascade="all, delete-orphan")

    # flattened names for list screens (history, admin tables)
    @property
    def storeCode(self) -> str:
        return self.store.s7Code if self.store else ""

    @property
    def storeName(self) -> str:
        return self.store.s7Name if self.store else ""

    @property
    def employeeName(self) -> str:
        return self.personnel.fullName if self.personnel else ""

    @property
    def fileCount(self) -> int:
        return len(self.files)
