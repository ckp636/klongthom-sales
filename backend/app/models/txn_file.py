from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import quoted_name

from app.core.database import Base


class TxnFile(Base):
    __tablename__ = quoted_name("mod1$_TxnFile", True)

    f1FID: Mapped[int] = mapped_column("f1FID", Integer, primary_key=True, autoincrement=True)
    f1TID: Mapped[int] = mapped_column("f1TID", Integer, ForeignKey("mod1$_Transaction.t1TID", ondelete="CASCADE"), nullable=False)
    f1Pid: Mapped[int | None] = mapped_column("f1Pid", Integer, ForeignKey("mod7$_Personnel.p7PID", ondelete="SET NULL"), nullable=True)
    f1FileName: Mapped[str] = mapped_column("f1FileName", String(255), nullable=False)
    f1Path: Mapped[str] = mapped_column("f1Path", String(500), nullable=False)
    f1MimeType: Mapped[str] = mapped_column("f1MimeType", String(100), nullable=False)
    f1Size: Mapped[int | None] = mapped_column("f1Size", Integer, nullable=True)
    f1Tag: Mapped[str] = mapped_column("f1Tag", String(20), nullable=False, default="receipt")
    f1CreatedAt: Mapped[datetime] = mapped_column("f1CreatedAt", DateTime, server_default=func.now())

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="files")
