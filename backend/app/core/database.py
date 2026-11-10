import time
from typing import Generator

import pymssql
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Azure SQL serverless pauses when idle; the first login after that fails with
# 40613 ("database not currently available") for up to a minute while it resumes.
_RESUME_ERROR = "40613"
_RESUME_RETRIES = 6
_RESUME_WAIT_S = 10


def _create_conn():
    for attempt in range(_RESUME_RETRIES + 1):
        try:
            return pymssql.connect(
                server=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                tds_version=settings.DB_TDS_VERSION,
                charset="UTF-8",
                login_timeout=30,
            )
        except pymssql.OperationalError as e:
            if _RESUME_ERROR not in str(e) or attempt == _RESUME_RETRIES:
                raise
            time.sleep(_RESUME_WAIT_S)


engine = create_engine(
    "mssql+pymssql://",
    creator=_create_conn,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
