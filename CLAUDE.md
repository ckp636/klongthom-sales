# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Files
| Path | What it is |
|---|---|
| `app.html` | The app (staff mobile screens + admin dashboard), served by Vercel and opened from LINE (LIFF) |
| `index.html` | Landing page; embeds `app.html` in an iframe preview |
| `support.js` | Claude Design runtime used by `app.html` — generated, do not edit |
| `api/index.py` | Vercel entry point: wraps the FastAPI app with Mangum |
| `vercel.json` | Routes `/api/*` to `api/index.py`, everything else is static |
| `backend/` | FastAPI + SQLAlchemy API and SQL scripts (see Backend) |
| `docs/database-design.md` | Database design and rationale |

## How to run the frontend
Serve the repo root with any static server and open `app.html`:
```
npx serve .
# or
python -m http.server 8080
```
On `localhost` the app talks to the API at `http://127.0.0.1:8000` (`API_BASE`); in production it uses the same origin.

## Frontend architecture (`app.html`)
A **Claude Design** single-file component: the HTML template and the `<script type="text/x-dc" data-dc-script>` block (a `class Component extends DCLogic`) live together.
- `state` — reactive state (mutate via `this.setState(...)`)
- `renderVals()` — returns the flat object of every value the template can reference; add a key here before using it in the template
- Event handlers are class arrow functions
- Template directives: `<sc-if value="{{expr}}">`, `<sc-for list="{{arr}}" as="item" hint-placeholder-count="N">`; `{{expr}}` interpolation; inline styles are full CSS strings from `renderVals()`

**Two top-level modes** (`state.mode`):
- `staff` — mobile screens `scan → login → form → history → historyDetail`. The store comes from a scanned QR (`?shop=<code>&sig=<sig>`; LINE's scanner in LIFF, camera + jsQR in a browser)
- `admin` — dashboard with date filter, summary cards, charts and list / by-employee / by-store tables, plus store management. Shown only when `isAdminUser`

**Login:** in LIFF, the LINE profile's `userId` goes to `POST /api/auth/login`. In DEV_MODE the login screen calls `/api/auth/login-dev` and falls back to mock users if the API isn't running.

**Data:** login and form submit use the API. History and admin screens still read the mock arrays `state.allHistory` / `state.submissionsToday` (derived views like `adminFiltered`, `groupedByEmployee` are built in `renderVals()`).

### DEV_MODE
`DEV_MODE` is true on `localhost`/`127.0.0.1`/empty hostname or with `?dev=1`. It shows the dev login tools and skips LIFF.

---

## Backend
> Full schema rationale: `docs/database-design.md`.

### Stack
- Python 3.12 · FastAPI · SQLAlchemy 2.0 (**sync**) · pymssql · Pydantic v2 · deployed on Vercel via `api/index.py` (Mangum)
- DB: **Azure SQL** `cs-azure.database.windows.net`, database `klongthom-sales` (serverless — first connect after idle fails with 40613 while it resumes; `database.py` retries)
- pymssql needs `DB_TDS_VERSION=7.4` for Azure SQL

### Run locally
```
cd backend
cp .env.example .env   # fill in DB credentials; .env is git-ignored
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Settings (`app/core/config.py`): `DB_*`, `DEV_LOGIN_ENABLED` (enables `/api/auth/login-dev`, never in prod), `QR_HMAC_SECRET` (when set, submissions must carry a valid store QR signature).

### Project Structure (backend)
```
backend/
  app/
    models/         # SQLAlchemy ORM models
    schemas/        # Pydantic request/response schemas
    routers/        # FastAPI routers
    services/       # log_service (audit), security (password hash, QR HMAC)
    repositories/   # DB query layer
    core/
      config.py     # Settings (pydantic-settings, reads backend/.env)
      database.py   # Engine, Session, get_db
  database/sql/
    01_schema.sql         # build tables on an empty DB (refuses to run if tables exist)
    02_sample_data.sql    # sample data, empty schema only
    03_sample_expense.sql # sample expenses
  seed.py                 # runs 01 → 02 → 03 against an empty DB
```
Schema changes are plain SQL scripts (no migration tool). Add a new numbered script for each change and apply it to Azure by hand.

### DB Naming Convention
Column = **[entity][mod][Column]** camelCase — prefix บอก origin ตาราง

| Prefix | Table | ตัวอย่าง |
|--------|-------|---------|
| `s7` | mod7$_Store | s7Sid, s7Code, s7QrVer |
| `p7` | mod7$_Personnel | p7PID, p7Sid, p7LineUID, p7Role |
| `t1` | mod1$_Transaction | t1TID, t1Sid, t1Pid, t1Date, t1Shift |
| `f1` | mod1$_TxnFile | f1FID, f1TID, f1Path, f1MimeType |
| `l9` | mod9$_Logging | l9LID, l9Page, l9Component, l9SessionID |

### Table Names — contain `$`, always quote in raw SQL
```sql
[mod7$_Store], [mod7$_Personnel], [mod1$_Transaction], [mod1$_TxnFile], [mod9$_Logging]
```
In SQLAlchemy: `__tablename__ = quoted_name("mod7$_Store", True)`

### Relationships
```
mod7$_Store (s7Sid)
  ├─ 1:N  mod7$_Personnel   p7Sid → s7Sid   (optional home store)
  └─ 1:N  mod1$_Transaction t1Sid → s7Sid

mod7$_Personnel (p7PID)
  ├─ 1:N  mod1$_Transaction t1Pid / t1VerifiedBy / t1VoidBy → p7PID
  └─ 1:N  mod1$_TxnFile     f1Pid → p7PID

mod1$_Transaction (t1TID)
  └─ 1:N  mod1$_TxnFile     f1TID → t1TID  (ON DELETE CASCADE)

mod9$_Logging — no FKs; l9Pid, l9Sid, l9RefTable + l9RefID are soft references
```

### Key Columns
- One `mod1$_Transaction` row = one **shift report** (staff · store · business date · shift)
- `t1Shift` 'morning','afternoon','evening' = เช้า / เย็น / ค่ำ
- `t1Cash`, `t1Transfer`, `t1Expense` DECIMAL(12,2) ≥ 0; `t1Total` = computed net (cash + transfer − expense) — ห้ามใช้ FLOAT สำหรับเงิน
- `t1Status` 'submitted' → 'verified' (admin), or 'void' (needs t1VoidBy/At/Reason). Amounts are never edited: void + resubmit
- Filtered unique index `uq_t1Slot` (t1Sid, t1Date, t1Shift, t1Pid) WHERE status <> 'void' blocks double submits
- `t1Date` = Bangkok business date (DATE); all `*CreatedAt/*UpdatedAt` are UTC
- `p7LineUID` = LINE userId (login); `p7User`/`p7PwdHash` optional (scrypt via `services/security.py`)
- `f1Path` เก็บ path บน storage เท่านั้น ไม่เก็บ binary ใน DB
- `l9OldVal`/`l9NewVal` must be JSON (pass dicts to `LogCreate`); mod9$_Logging is append-only — a trigger rejects UPDATE/DELETE

### Coding Rules
- Sync `Session` from `get_db` (commits per request); use `db.begin_nested()` when an expected IntegrityError must not undo the rest of the request
- Boolean filters: `col == True` (not `.is_(True)` — renders `IS 1`, invalid on SQL Server)
- Log table has a trigger → `implicit_returning=False` on the model (SQL Server forbids OUTPUT without INTO)
- ไม่ expose `p7PwdHash` ใน response schema ใดๆ
- ใช้ `from decimal import Decimal` ไม่ใช้ float สำหรับเงิน
- ทุก action ที่ admin/staff ทำต้อง write ลง mod9$_Logging (`log_service.write(db, LogCreate(...), request)`)

### API (prefix `/api`)
- `POST /auth/login` {line_user_id} · `POST /auth/login-dev` {role | p7PID} (DEV only)
- `GET /transactions` (sid, pid, date_from, date_to, status, include_void) → history / admin tables
- `GET /transactions/summary?group_by=store|employee|date` → admin totals
- `POST /transactions` {storeCode, qrSig, t1Pid, t1Date, t1Shift, t1Cash, t1Transfer, t1Expense, t1Note} → form submit
- `PATCH /transactions/{id}` (note only) · `POST /transactions/{id}/void` · `POST /transactions/{id}/verify`
- `GET|POST /transactions/{id}/files` → evidence photo metadata (upload to storage not built yet)
- `GET|POST|PATCH /stores` · `GET /stores/{id}/qr` · `POST /stores/{id}/qr/rotate`
- `GET|POST|PATCH /personnel`

### Not done yet
- No real auth: the API trusts `t1Pid` / `byPid` / `line_user_id` from the client. Verify LIFF ID tokens and issue a session before production.
- Evidence photo upload to object storage; app.html history/admin screens still read mock `state.allHistory`.
