from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class Store(Base):
    __tablename__ = quoted_name("mod7$_Store", True)

    s7Sid: Mapped[int] = mapped_column("s7Sid", Integer, primary_key=True, autoincrement=True)
    s7Code: Mapped[str] = mapped_column("s7Code", String(20), nullable=False, unique=True)
    s7Name: Mapped[str] = mapped_column("s7Name", String(200), nullable=False)
    s7Active: Mapped[bool] = mapped_column("s7Active", Boolean, default=True, nullable=False)
    s7CreatedAt: Mapped[datetime] = mapped_column("s7CreatedAt", DateTime, server_default=func.now())
    s7UpdatedAt: Mapped[datetime] = mapped_column("s7UpdatedAt", DateTime, server_default=func.now(), onupdate=func.now())

    personnel: Mapped[list["Personnel"]] = relationship("Personnel", back_populates="store")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="store")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="store")
