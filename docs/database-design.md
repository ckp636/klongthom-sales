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
| `mod1$_TxnFile` | an evidence photo | Metadata only; the file lives in object storage. `f1Sha256` catches the same slip uploaded twice. Allowed MIME types and a 10 MB cap are enforced. `f1Path` is unique. |
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
| `evidencePhoto` | `mod1$_TxnFile` row (`f1Tag = 'slip'`) |
| `qrSig` | verified server-side against HMAC(`s7Code`, `s7QrVer`); not stored |

## Build and sample data

Database: Azure SQL `cs-azure.database.windows.net`, **`klongthom-sales`** (serverless: the first connection after an idle period can fail with error 40613 while it resumes, so retry). Connection details are in the git-ignored `backend/.env`.

1. `01_schema.sql` builds tables, indexes and the log trigger. It refuses to run if the tables already exist.
2. `02_sample_data.sql` loads 14 stores, 11 staff + 1 admin (LINE IDs `LINE_TEST_001…011`, `LINE_TEST_ADMIN`) and 21 days of shift reports (2026-10-18 → 11-07), plus photos and audit rows. It runs only on empty tables and produces the same data every time.
3. `03_sample_expense.sql` gives about two thirds of the sample reports an expense.

`cd backend && python seed.py` runs all three in order. FreeTDS/pymssql needs `tds_version="7.4"` (`DB_TDS_VERSION`) to connect to Azure SQL.

## Open questions

1. Should a store have only one report per shift, regardless of who submits? If yes, drop `t1Pid` from `uq_t1Slot`.
2. Must staff be limited to assigned stores? If yes, add a `mod7$_PersonnelStore` (p7PID, s7Sid) link table.
3. Will `t1Status = 'verified'` (admin sign-off) be used? If not, keep only `submitted` and `void`.
