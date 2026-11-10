# KlongthomSales — Database Design

Azure SQL (SQL Server 2022) · DDL: [`backend/database/sql/01_schema.sql`](../backend/database/sql/01_schema.sql)
Naming: `[entity][mod][Column]` camelCase (`s7`, `p7`, `t1`, `f1`, `l9`). Table names contain `$`, so quote them in raw SQL.

## What the app records

A staff member scans a store's QR code, logs in with LINE, and submits **one shift report**: store, date, shift (เช้า/เย็น/ค่ำ), **cash amount + transfer amount − expense** (หัก ค่าใช้จ่าย), a note, and an evidence photo.
Admins look at those reports by date range, grouped by employee or by store.

## ER

```
mod7$_Store (s7Sid)
  ├─< mod7$_Personnel.p7Sid        optional home store
  └─< mod1$_Transaction.t1Sid

mod7$_Personnel (p7PID)
  ├─< mod1$_Transaction.t1Pid      submitted by
  ├─< mod1$_Transaction.t1VerifiedBy / t1VoidBy
  └─< mod1$_TxnFile.f1Pid          uploaded by

mod1$_Transaction (t1TID)
  └─< mod1$_TxnFile.f1TID          ON DELETE CASCADE

mod9$_Logging                      no FKs (l9Pid, l9Sid, l9RefTable+l9RefID are soft refs)
```

## Tables

| Table | Row means | Notes |
|---|---|---|
| `mod7$_Store` | a shop | `s7Code` is what the QR carries. Bump `s7QrVer` to revoke every printed QR for that store; the HMAC key stays in app settings. |
| `mod7$_Personnel` | a staff member or admin | `p7LineUID` (unique) is the LINE login. `p7User`/`p7PwdHash` are optional (LINE-only staff have no password); a CHECK requires at least one login method. `p7Sid` is optional because staff collect at whichever store they scan. |
| `mod1$_Transaction` | one shift report | `t1Date` is a `DATE`. `t1Cash`, `t1Transfer`, `t1Expense`; `t1Total` is a persisted computed column holding the net amount (cash + transfer − expense). `t1Status`: `submitted → verified`, or `void` with who/when/why. `t1QrVer` records the QR version used. |
| `mod1$_TxnFile` | an evidence photo | Metadata plus deferred `f1Content VARBINARY(MAX)`. `f1Sha256` detects upload retries for a report. API uploads accept valid JPEG/PNG/WebP up to 2 MB; `f1Path` is a unique logical `sql/<uuid>` key, not a public URL. |
| `mod9$_Logging` | an audit/activity event | No FKs, so logging never fails and rows outlive what they point to. An `INSTEAD OF UPDATE, DELETE` trigger enforces append-only. `l9OldVal`/`l9NewVal` must be JSON. |

## Rules enforced by the database

- **No double submit:** a filtered unique index on `(t1Sid, t1Date, t1Shift, t1Pid) WHERE t1Status <> 'void'`. To correct a report, void it and resubmit.
- **Money:** `DECIMAL(12,2)` with `>= 0` checks; never `FLOAT`.
- **Void and verify integrity:** CHECK constraints require who, when and a reason.
- **Time:** every `*CreatedAt`/`*UpdatedAt` is **UTC** (`SYSUTCDATETIME()`). `t1Date` is the Bangkok business date the app sends. Convert to UTC+7 only for display.
- **Shift values:** เช้า = `morning`, เย็น = `afternoon`, ค่ำ = `evening`.

## Indexes, by screen

| Screen / query | Index |
|---|---|
| Admin dashboard: date range, by store or employee | `ix_t1Date (t1Date, t1Sid) INCLUDE (...)` |
| Staff history: my reports in a range | `ix_t1Pid_Date (t1Pid, t1Date) INCLUDE (...)` |
| Photos for a report | `ix_f1TID` |
| Audit trail for one record | `ix_l9Ref (l9RefTable, l9RefID)` |

## API mapping

| Frontend field | Column |
|---|---|
| `storeCode` (from QR) | sent as `storeCode`; API looks up `s7Code` → `t1Sid` |
| `employeeName` / LINE `userId` | lookup `p7LineUID` → `t1Pid` |
| `date`, `period` | `t1Date`, `t1Shift` |
| `cash`, `transfer`, `expense`, `note` | `t1Cash`, `t1Transfer`, `t1Expense`, `t1Note` |
| `evidencePhoto` | multipart photo upload to the persisted report; `mod1$_TxnFile.f1Content` (`f1Tag = 'slip'`) |
| `qrSig` | verified server-side against HMAC(`s7Code`, `s7QrVer`); not stored |

## Build and sample data

Database: Azure SQL `cs-azure.database.windows.net`, **`klongthom-sales`** (serverless: the first connection after an idle period can fail with error 40613 while it resumes, so retry). Connection details are in the git-ignored `backend/.env`.

1. `01_schema.sql` builds tables, indexes and the log trigger. It refuses to run if the tables already exist.
2. `02_sample_data.sql` loads 14 stores, 11 staff + 1 admin (LINE IDs `LINE_TEST_001…011`, `LINE_TEST_ADMIN`) and 21 days of shift reports (2026-10-18 → 11-07), plus photos and audit rows. It runs only on empty tables and produces the same data every time.
3. `03_sample_expense.sql` gives about two thirds of the sample reports an expense.

4. `04_transaction_numbers.sql` expands `t1TNo` to 64 characters and adds `seq_t1ReportNo`. New numbers use a database-allocated `-N<sequence>` suffix; existing numbers remain unchanged.
5. `05_photo_storage.sql` adds nullable photo bytes, UTC expiry/purge timestamps, and an expiry index. Existing metadata-only files remain listed but unavailable.

`cd backend && python seed.py` runs all five in order on an empty database only. For an existing database, apply **04 then 05 manually**, after a backup/review; do not rerun the seed script. FreeTDS/pymssql needs `tds_version="7.4"` (`DB_TDS_VERSION`).

## Photo storage and one-year retention

- The browser resizes photos to at most 1600 pixels on the longest side and compresses JPEG toward 500 KB. The server independently verifies actual image content, dimensions, format, and the 2 MB limit.
- Upload only after the shift report is saved: `POST /api/transactions/{tid}/files` with multipart field `file`. If upload fails, retry the photo on that report instead of resubmitting its amounts.
- `GET /api/transactions/{tid}/files` returns metadata and availability; `GET /api/transactions/{tid}/files/{fid}/content` delivers authenticated bytes. Staff can access only their own reports; admins can access all. Responses are not publicly cached.
- `f1Content` is deferred by SQLAlchemy: ordinary transaction/file lists must never fetch or serialize image bytes.
- `f1ExpiresAt` is UTC upload time plus 365 days. Reads deny expired images immediately, even before cleanup. Metadata-only legacy rows have no expiry/content and are shown as unavailable.
- A daily Vercel Cron calls `GET /api/maintenance/photos/cleanup` with `Authorization: Bearer <CRON_SECRET>`. Up to ten batches of 100 expired photos are cleared per invocation; `f1PurgedAt` and an audit count are recorded. Repeat invocations are safe. Monitor scheduler failures and backlog.
- Sales reports, original file metadata/hashes, and audit history are retained. SQL data-file allocation may not shrink automatically, and backups retain historical bytes according to their separate policy.
- Capacity estimate: 14 stores x 2 photos/day x 365 = 10,220 photos, approximately 5 GB at 500 KB each or 20 GB at the maximum size, excluding overhead/backups. Provision Azure SQL capacity accordingly. The expected photo count is not an enforced daily quota.

## Local validation and Vercel deployment

1. Use Python 3.12. From the repository root, create a virtual environment and run `pip install -r requirements.txt` (the committed, pinned deployment dependencies). The source constraints are in `backend/requirements.txt`; regenerate the root lock with `uv pip compile backend/requirements.txt --output-file requirements.txt --python-version 3.12`.
2. Copy `backend/.env.example` to the ignored `backend/.env` and configure the database. Generate independent random session, QR, and scheduler secrets. Do not copy real values into source control.
3. Configure `SESSION_SECRET` (at least 32 characters), `QR_HMAC_SECRET`, `LINE_CHANNEL_ID` (LINE Login channel ID, not LIFF ID), and `CRON_SECRET`. The frontend LIFF ID is configured in `app.html`; its LINE Login channel must match the backend. Enable the LIFF `openid` scope and set its endpoint to the deployed `/app.html`.
4. Locally only: `SESSION_COOKIE_SECURE=false`, `DEV_LOGIN_ENABLED=true`, and explicit `CORS_ORIGINS` matching the static server. Run `cd backend && uvicorn app.main:app --reload`; separately serve the frontend on port 8080. Use the same hostname (`localhost` or `127.0.0.1`) for frontend and API so SameSite cookies work. Dev login uses real database personnel and never falls back to mocks.
5. On Vercel, keep the project root at the repository root, set `SESSION_COOKIE_SECURE=true` and `DEV_LOGIN_ENABLED=false`, and set the variables in the intended environment. Add exact production/preview origins to `CORS_ORIGINS`; do not use `*`. Vercel dev-login requests are rejected even if accidentally enabled. Do not include `.env` files in deployments.
6. Only the three explicitly allowlisted static assets (`index.html`, `app.html`, `support.js`) and the native Python ASGI function are public build outputs. Database scripts/backend source are not static files. `/api/health` is liveness only and does not establish DB readiness.
7. Verify the project's function duration budget accommodates Azure serverless resume (the connector can spend up to roughly 270 seconds across login timeouts/retries), and validate cold starts before release. Configure a suitable duration in the Vercel project/plan rather than relying on an unsupported builder setting.
8. Configure Azure SQL firewall/network access for the intended Vercel deployment using the organization's network policy. Never broadly open the database as a testing shortcut.

Authentication sends a LIFF ID token to `/api/auth/login` for server verification with LINE, then uses an eight-hour signed HttpOnly cookie. `/api/auth/me` restores the session; `/api/auth/logout` clears it and audits logout. Current personnel role/status is loaded on each request. Cookies are cleared client-side on logout; signed tokens otherwise expire after eight hours (there is no server-side session-revocation registry). Cookie-authenticated mutations require a trusted `Origin`, including requests from API tools.

Database-free checks:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/frontend.test.cjs
```

An optional browser regression (`node tests/browser-smoke.cjs`) requires Playwright/Chromium and a running static server. Set `BASE_URL` to that server (default `http://127.0.0.1:8765`). It intercepts all API requests with local fixtures and verifies mobile login, decimal entry, compression/upload retry, reload history and authenticated image display; it never uses the real database.

Backend tests use an isolated in-memory SQLite fixture, mocked LINE verification, and prohibit pymssql connections. They verify persisted application behavior, not SQL Server-specific execution. SQL Server sequence/query compilation is also checked; actual migrations, constraints, commit behavior and Thai text still require staging validation.

A clean local Vercel build was verified against a sanitized copy using synthetic local project settings, without deployment or live credentials. Public output was checked to contain only the allowlisted static assets. After linking your real project, run `vercel build` locally before deploying.

Before declaring staging ready, explicitly authorize live checks and verify: reviewed migrations, connectivity, verified LINE login, signed QR scan, durable report/audit writes, reload history, staff isolation/admin management, real photo round trips, expiry and scheduled cleanup. A success banner, mocked test, build, or liveness endpoint alone is not proof of Azure SQL persistence.

## Open questions

1. Should a store have only one report per shift, regardless of who submits? If yes, drop `t1Pid` from `uq_t1Slot`.
2. Must staff be limited to assigned stores? If yes, add a `mod7$_PersonnelStore` (p7PID, s7Sid) link table.
3. Will `t1Status = 'verified'` (admin sign-off) be used? If not, keep only `submitted` and `void`.
