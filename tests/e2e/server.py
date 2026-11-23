"""End-to-end test server: the real FastAPI app + app.html on one origin,
backed by a throw-away in-memory SQLite database. Never touches Azure.

    python tests/e2e/server.py          # http://app.localhost:8180/app.html

Runs like production (not localhost, so no DEV tools; LIFF is stubbed by the
test). Seed data: see seed() below. Every start is a fresh database.
"""
import itertools
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PORT = int(os.getenv("E2E_PORT", 8180))
ORIGIN = f"http://app.localhost:{PORT}"
QR_SECRET = "e2e-qr-secret"

os.environ.update(
    DB_HOST="invalid.test", DB_USER="e2e", DB_PASSWORD="e2e", DB_NAME="e2e",
    SESSION_SECRET="e2e-session-secret-" * 3, SESSION_COOKIE_SECURE="false",
    QR_HMAC_SECRET=QR_SECRET, LINE_CHANNEL_ID="12345", CRON_SECRET="e2e-cron",
    DEV_LOGIN_ENABLED="false", PASSWORD_LOGIN_ENABLED="true", ALLOW_MANUAL_STORE_PICK="true",
    CORS_ORIGINS=f'["{ORIGIN}"]',
)
sys.path.insert(0, str(ROOT / "backend"))

import pymssql  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from sqlalchemy import BigInteger, create_engine, event  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

with patch("pydantic_settings.sources.DotEnvSettingsSource._read_env_files", return_value={}):
    from app.core.config import settings  # noqa: E402,F401  (never reads backend/.env)
from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.personnel import Personnel  # noqa: E402
from app.models.store import Store  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.repositories import transaction_repo  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PASSWORD = "demo1234"


@compiles(BigInteger, "sqlite")
def _sqlite_identity(type_, compiler, **kwargs):
    return "INTEGER"


def build_database():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _functions(connection, record):
        connection.isolation_level = None
        connection.create_function(
            "sysutcdatetime", 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "))

    @event.listens_for(engine, "handle_error")
    def _name_slot_index(ctx):
        # SQL Server names the violated index (uq_t1Slot) and the app relies on it; SQLite doesn't.
        err = ctx.original_exception
        if "UNIQUE constraint failed" in str(err) and "t1Shift" in str(err):
            err.args = (f"uq_t1Slot: {err}",)

    @event.listens_for(engine, "begin")
    def _begin(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            'CREATE UNIQUE INDEX uq_t1Slot ON "mod1$_Transaction" '
            '("t1Sid", "t1Date", "t1Shift", "t1Pid") WHERE "t1Status" <> \'void\'')
    return sessionmaker(engine, expire_on_commit=False)


def seed(Session):
    bangkok_today = (datetime.now(timezone.utc) + timedelta(hours=7)).date()
    with Session.begin() as db:
        db.add_all([
            Store(s7Sid=1, s7Code="A1", s7Name="กอล์ฟ", s7QrVer=1, s7Status=True),
            Store(s7Sid=2, s7Code="A2", s7Name="นิ่ม", s7QrVer=1, s7Status=True),
            Store(s7Sid=3, s7Code="Z9", s7Name="ร้านปิด", s7QrVer=1, s7Status=False),
        ])
        people = [  # pid, emp, user, first, last, role, home, active
            (1, "EMP001", "staff01", "สตาฟ", "หนึ่ง", "staff", 1, True),
            (2, "EMP002", "staff02", "สตาฟ", "สอง", "staff", 2, True),
            (3, "ADM001", "admin01", "แอดมิน", "หนึ่ง", "admin", None, True),
            (4, "EMP099", "staff99", "สตาฟ", "ระงับ", "staff", None, False),
        ]
        for pid, emp, user, first, last, role, home, active in people:
            db.add(Personnel(p7PID=pid, p7EmpCode=emp, p7LineUID=f"line-{user}", p7User=user,
                             p7PwdHash=hash_password(PASSWORD), p7FName=first, p7LName=last,
                             p7Role=role, p7Sid=home, p7Status=active))
        db.flush()
        # one report already sent today: staff02 · A2 · afternoon
        db.add(Transaction(t1TNo="A2-SEED-1", t1Sid=2, t1Pid=2, t1Date=bangkok_today, t1Shift="afternoon",
                           t1Cash=Decimal("3000"), t1Transfer=Decimal("1200"), t1Expense=Decimal("200"),
                           t1Status="submitted", t1QrVer=1))


def main():
    pymssql.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Azure access prohibited in e2e"))
    Session = build_database()
    seed(Session)

    lock = threading.Lock()  # one shared SQLite connection: serialise requests like a real DB would isolate them

    def test_db():
        with lock, Session() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = test_db
    counter = itertools.count(1)
    transaction_repo._next_tno = lambda db, code, day, shift: f"{code}-{day:%Y%m%d}-{shift[0].upper()}-E{next(counter)}"

    # serve only the public static assets, never the repo (backend/.env lives there)
    for name in ("app.html", "index.html", "support.js"):
        def page(name=name):
            return FileResponse(ROOT / name, headers={"Cache-Control": "no-store"})
        app.add_api_route(f"/{name}", page, methods=["GET"], include_in_schema=False)

    import uvicorn
    print(f"E2E server: {ORIGIN}/app.html (in-memory DB)", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
