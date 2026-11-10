import io
import itertools
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

# Never read credentials or connect to Azure during local tests.
os.environ.update(
    DB_HOST="invalid.test", DB_USER="test", DB_PASSWORD="test", DB_NAME="test",
    SESSION_SECRET="local-tests-only-" * 3, SESSION_COOKIE_SECURE="false",
    QR_HMAC_SECRET="local-qr-test", LINE_CHANNEL_ID="12345", CRON_SECRET="cron-test",
    DEV_LOGIN_ENABLED="true",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import jwt
import pymssql
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import BigInteger, Index, create_engine, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

with patch("pydantic_settings.sources.DotEnvSettingsSource._read_env_files", return_value={}):
    from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.log import Log
from app.models.personnel import Personnel
from app.models.store import Store
from app.models.transaction import Transaction
from app.models.txn_file import TxnFile
from app.repositories import transaction_repo
from app.services import auth_service, photo_service
from app.services.security import qr_sig


@compiles(BigInteger, "sqlite")
def sqlite_identity(type_, compiler, **kwargs):
    return "INTEGER"


def image_bytes():
    output = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(output, format="JPEG")
    return output.getvalue()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.no_azure = patch.object(pymssql, "connect", side_effect=AssertionError("Azure access prohibited"))
        self.no_azure.start()
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def sql_functions(connection, record):
            connection.isolation_level = None
            connection.create_function("sysutcdatetime", 0, lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat(" "))

        @event.listens_for(self.engine, "begin")
        def explicit_begin(connection):
            connection.exec_driver_sql("BEGIN")

        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                'CREATE UNIQUE INDEX uq_t1Slot ON "mod1$_Transaction" '
                '("t1Sid", "t1Date", "t1Shift", "t1Pid") WHERE "t1Status" <> \'void\''
            )
        self.session = sessionmaker(self.engine, expire_on_commit=False)

        def test_db():
            with self.session() as db:
                try:
                    yield db
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

        app.dependency_overrides[get_db] = test_db
        self.counter = itertools.count(1)
        self.numbers = patch.object(transaction_repo, "_next_tno", side_effect=lambda *a: f"A1-20261110-A-N{next(self.counter)}")
        self.numbers.start()
        with self.session.begin() as db:
            db.add(Store(s7Sid=1, s7Code="A1", s7Name="ร้านทดสอบ", s7QrVer=1, s7Status=True))
            for pid, role in [(1, "staff"), (2, "staff"), (3, "admin")]:
                db.add(Personnel(p7PID=pid, p7EmpCode=f"TEST{pid}", p7LineUID=f"line{pid}",
                                 p7FName="ทดสอบ", p7LName=str(pid), p7Role=role, p7Status=True))
        self.client = TestClient(app, headers={"Origin": "http://testserver"})

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.numbers.stop()
        self.engine.dispose()
        self.no_azure.stop()

    def login(self, pid=1):
        response = self.client.post("/api/auth/login-dev", json={"p7PID": pid})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def submit(self, **changes):
        body = dict(storeCode="A1", qrSig=qr_sig("A1", 1), t1Date="2026-11-10",
                    t1Shift="afternoon", t1Cash="100.25", t1Transfer="0.10", t1Expense="0.05")
        return self.client.post("/api/transactions/", json={**body, **changes})

    def test_auth_required_and_origin(self):
        self.assertEqual(self.client.get("/api/transactions/").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login-dev", json={"role": "admin"},
                                         headers={"Origin": "https://evil.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/api/auth/login-dev", json={"role": "admin"},
                                         headers={"Origin": ""}).status_code, 403)
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        preflight = self.client.options("/api/auth/login", headers={
            "Origin": "http://localhost:8080", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers["access-control-allow-origin"], "http://localhost:8080")
        self.assertEqual(preflight.headers["access-control-allow-credentials"], "true")

    def test_session_and_logout(self):
        login = self.login()
        cookie = login.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=28800", cookie)
        self.assertNotIn("p7PwdHash", login.text)
        self.assertEqual(self.client.get("/api/auth/me").json()["personnel"]["p7PID"], 1)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_expired_session_and_suspended_user(self):
        now = datetime.now(timezone.utc)
        expired = jwt.encode({"iss": "klongthom-sales", "sub": "1", "iat": now-timedelta(hours=9),
                              "exp": now-timedelta(hours=1)}, settings.SESSION_SECRET, algorithm="HS256")
        self.client.cookies.set(auth_service.COOKIE_NAME, expired)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.client.cookies.clear()
        self.login()
        with self.session.begin() as db:
            db.get(Personnel, 1).p7Status = False
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_line_verification_contract(self):
        claims = {"iss": "https://access.line.me", "aud": settings.LINE_CHANNEL_ID,
                  "sub": "line1", "exp": datetime.now(timezone.utc).timestamp()+60}
        with patch("app.services.auth_service.httpx.post") as verify:
            verify.return_value.status_code = 200
            verify.return_value.json.return_value = claims
            response = self.client.post("/api/auth/login", json={"id_token": "test-token"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(verify.call_args.kwargs["data"]["client_id"], settings.LINE_CHANNEL_ID)
            verify.return_value.status_code = 400
            self.assertEqual(self.client.post("/api/auth/login", json={"id_token": "bad"}).status_code, 401)
            verify.return_value.status_code = 200
            verify.return_value.json.return_value = {**claims, "aud": "wrong"}
            self.assertEqual(self.client.post("/api/auth/login", json={"id_token": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/login", json={"line_user_id": "line1"}).status_code, 422)

    def test_dev_login_not_on_vercel(self):
        with patch.dict(os.environ, {"VERCEL": "1"}):
            self.assertEqual(self.client.post("/api/auth/login-dev", json={"p7PID": 3}).status_code, 404)

    def test_persistence_actor_money_and_ownership(self):
        self.login()
        created = self.submit(t1Pid=2)
        self.assertEqual(created.status_code, 201, created.text)
        data = created.json()
        self.assertEqual(data["t1Pid"], 1)
        self.assertEqual(data["t1Total"], "100.30")
        self.assertEqual(data["storeName"], "ร้านทดสอบ")
        self.assertEqual(self.client.get("/api/transactions/").json()[0]["t1TID"], data["t1TID"])
        self.login(2)
        self.assertEqual(self.client.get("/api/transactions/?pid=1").json(), [])
        self.assertEqual(self.client.get(f"/api/transactions/{data['t1TID']}").status_code, 404)
        self.assertEqual(self.client.get("/api/personnel/").status_code, 403)
        self.assertEqual(self.client.get("/api/transactions/summary").status_code, 403)
        self.assertEqual(self.client.patch("/api/stores/1", json={"s7Name": "x"}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/transactions/{data['t1TID']}/verify", json={"byPid": 3}).status_code, 403)
        self.login(3)
        self.assertEqual(len(self.client.get("/api/transactions/").json()), 1)
        with self.session() as db:
            self.assertEqual(db.scalar(select(Log).where(Log.l9Action == "create")).l9Pid, 1)

    def test_amount_validation_qr_void_resubmit(self):
        self.login()
        for amount in ("-1", "0.001", "10000000000"):
            self.assertEqual(self.submit(t1Cash=amount).status_code, 422)
        self.assertEqual(self.submit(qrSig=None).status_code, 403)
        first = self.submit().json()
        with patch.object(transaction_repo, "create", side_effect=transaction_repo.DuplicateSlot):
            duplicate = self.submit()
        self.assertEqual(duplicate.status_code, 409, duplicate.text)
        self.login(3)
        self.assertEqual(self.client.post(f"/api/transactions/{first['t1TID']}/verify").status_code, 200)
        self.assertEqual(self.client.post(f"/api/transactions/{first['t1TID']}/void",
                                         json={"reason": "แก้ไข", "byPid": 1}).json()["t1VoidBy"], 3)
        self.login()
        self.assertEqual(self.submit().status_code, 201)

    def test_upload_authorization_bytes_and_retention(self):
        self.login()
        tid = self.submit().json()["t1TID"]
        content = image_bytes()
        response = self.client.post(f"/api/transactions/{tid}/files",
                                    files={"file": ("slip.jpg", content, "image/jpeg")})
        self.assertEqual(response.status_code, 201, response.text)
        photo = response.json()
        self.assertNotIn("f1Content", photo)
        self.assertTrue(photo["available"])
        self.assertEqual(self.client.get(photo["contentUrl"]).content, content)
        self.assertEqual(self.client.get(photo["contentUrl"]).headers["cache-control"], "no-store")
        self.assertEqual(len(self.client.get(f"/api/transactions/{tid}/files").json()), 1)
        self.client.post(f"/api/transactions/{tid}/files", files={"file": ("slip.jpg", content, "image/jpeg")})
        self.assertEqual(len(self.client.get(f"/api/transactions/{tid}/files").json()), 1)
        self.login(2)
        self.assertEqual(self.client.get(photo["contentUrl"]).status_code, 404)
        self.assertEqual(self.client.post(f"/api/transactions/{tid}/files",
                                         files={"file": ("slip.jpg", content, "image/jpeg")}).status_code, 404)
        self.login()
        with self.session.begin() as db:
            db.get(TxnFile, photo["f1FID"]).f1ExpiresAt = photo_service.utcnow()
        self.assertEqual(self.client.get(photo["contentUrl"]).status_code, 410)
        self.assertEqual(self.client.get("/api/maintenance/photos/cleanup").status_code, 403)
        cleaned = self.client.get("/api/maintenance/photos/cleanup", headers={"Authorization": "Bearer cron-test"})
        self.assertEqual(cleaned.json(), {"purged": 1})
        with self.session() as db:
            saved = db.get(TxnFile, photo["f1FID"])
            self.assertIsNone(saved.f1Content)
            self.assertIsNotNone(saved.f1PurgedAt)
            self.assertIsNotNone(db.get(Transaction, tid))

    def test_photo_size_and_format(self):
        self.login()
        tid = self.submit().json()["t1TID"]
        for data, mime, status in [(b"", "image/jpeg", 422), (b"not an image", "image/jpeg", 422),
                                   (image_bytes(), "image/png", 415),
                                   (b"x" * (2*1024*1024+1), "image/jpeg", 413)]:
            response = self.client.post(f"/api/transactions/{tid}/files", files={"file": ("slip", data, mime)})
            self.assertEqual(response.status_code, status, response.text)
        with patch.object(photo_service.settings, "PHOTO_MAX_BYTES", len(image_bytes())):
            self.assertEqual(photo_service.validate_photo(image_bytes(), "image/jpeg"), "image/jpeg")
        with self.assertRaises(HTTPException) as truncated:
            photo_service.validate_photo(image_bytes()[:-20], "image/jpeg")
        self.assertEqual(truncated.exception.status_code, 422)
        exact_limit = image_bytes() + b"\0" * (2*1024*1024 - len(image_bytes()))
        accepted = self.client.post(f"/api/transactions/{tid}/files",
                                    files={"file": ("limit.jpg", exact_limit, "image/jpeg")})
        self.assertEqual(accepted.status_code, 201, accepted.text)
        self.assertEqual(accepted.json()["f1Size"], 2*1024*1024)

    def test_admin_management_signed_qr_and_rotation(self):
        self.login(3)
        people = self.client.get("/api/personnel/").json()
        self.assertEqual(len(people), 3)
        self.assertEqual(self.client.patch("/api/personnel/1", json={"p7FName": "ชื่อใหม่"}).status_code, 200)
        self.assertEqual(self.client.patch("/api/personnel/1", json={"p7FName": None}).status_code, 422)
        self.assertEqual(self.client.patch("/api/stores/1", json={"s7Name": None}).status_code, 422)
        signed = self.client.get("/api/stores/1/qr").json()
        self.assertIn("sig=", signed["qrQuery"])
        self.assertEqual(self.client.post("/api/stores/1/qr/rotate").status_code, 200)
        self.login()
        self.assertEqual(self.submit(qrSig=signed["qrSig"]).status_code, 403)
        self.assertEqual(self.submit(qrSig=qr_sig("A1", 2)).status_code, 201)
        self.login(3)
        self.assertEqual(self.client.patch("/api/stores/1", json={"s7Status": False}).status_code, 200)
        self.login()
        self.assertEqual(self.client.get("/api/stores/").json(), [])
        self.assertEqual(self.client.get("/api/stores/1").status_code, 404)

    def test_named_sql_server_duplicate_is_translated(self):
        from app.schemas.transaction import TransactionCreate
        fake = unittest.mock.MagicMock()
        fake.begin_nested.return_value.__enter__.side_effect = IntegrityError(
            "INSERT", {}, RuntimeError("Violation of unique index uq_t1Slot"),
        )
        data = TransactionCreate(storeCode="A1", t1Date="2026-11-10", t1Shift="afternoon", t1Cash="1")
        store = unittest.mock.Mock(s7Code="A1", s7Sid=1, s7QrVer=1)
        with self.assertRaises(transaction_repo.DuplicateSlot):
            transaction_repo.create(fake, store, data, 1)

    def test_audit_failure_rolls_back_report(self):
        self.login()
        with patch("app.routers.transactions.log_service.write", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertEqual(self.client.get("/api/transactions/").json(), [])

    def test_database_dependency_rolls_back_commit_failure(self):
        fake = unittest.mock.Mock()
        fake.commit.side_effect = RuntimeError("commit failed")
        with patch("app.core.database.SessionLocal", return_value=fake):
            dependency = get_db()
            next(dependency)
            with self.assertRaises(RuntimeError):
                next(dependency)
        fake.rollback.assert_called_once()
        fake.close.assert_called_once()

    def test_commit_failure_cannot_return_success(self):
        self.login()

        def broken_commit():
            with self.session() as db:
                try:
                    yield db
                    raise RuntimeError("commit failed")
                finally:
                    db.rollback()

        app.dependency_overrides[get_db] = broken_commit
        with TestClient(app, raise_server_exceptions=False, headers={"Origin": "http://testserver"}) as client:
            client.cookies.update(self.client.cookies)
            response = client.post("/api/auth/logout")
            self.assertEqual(response.status_code, 500)

    def test_sql_server_metadata_and_number_bounds(self):
        self.numbers.stop()
        try:
            fake = unittest.mock.Mock()
            fake.scalar.return_value = 9223372036854775807
            number = transaction_repo._next_tno(fake, "A"*20, datetime(2026, 11, 10), "afternoon")
            self.assertLessEqual(len(number), Transaction.__table__.c.t1TNo.type.length)
            self.assertIn("NEXT VALUE FOR", str(fake.scalar.call_args.args[0].compile(dialect=mssql.dialect())))
            sql = str(select(TxnFile).compile(dialect=mssql.dialect()))
            self.assertNotIn("f1Content", sql)
            self.assertEqual(TxnFile.__table__.c.f1Content.type.compile(dialect=mssql.dialect()).upper(), "VARBINARY(MAX)")
        finally:
            self.numbers.start()


if __name__ == "__main__":
    unittest.main()
