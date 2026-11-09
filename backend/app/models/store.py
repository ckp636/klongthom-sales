from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Store(Base):
    __tablename__ = quoted_name("mod7$_Store", True)

    s7Sid: Mapped[int] = mapped_column("s7Sid", Integer, primary_key=True, autoincrement=True)
    s7Code: Mapped[str] = mapped_column("s7Code", String(20), nullable=False, unique=True)
    s7Name: Mapped[str] = mapped_column("s7Name", String(100), nullable=False)
    s7Type: Mapped[str] = mapped_column("s7Type", String(20), nullable=False, default="retail")
    s7Addr: Mapped[str | None] = mapped_column("s7Addr", String(500), nullable=True)
    s7Phone: Mapped[str | None] = mapped_column("s7Phone", String(20), nullable=True)
    s7TaxID: Mapped[str | None] = mapped_column("s7TaxID", String(20), nullable=True)
    s7QrVer: Mapped[int] = mapped_column("s7QrVer", Integer, nullable=False, default=1)
    s7Status: Mapped[bool] = mapped_column("s7Status", Boolean, nullable=False, default=True)
    s7CreatedAt: Mapped[datetime] = mapped_column("s7CreatedAt", DateTime, server_default=func.sysutcdatetime())
    s7UpdatedAt: Mapped[datetime | None] = mapped_column("s7UpdatedAt", DateTime, nullable=True, onupdate=func.sysutcdatetime())

    personnel: Mapped[list["Personnel"]] = relationship("Personnel", back_populates="store")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="store")
