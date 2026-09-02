# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
## How to run
Open `Sales App.dc.html` directly in a browser (double-click, or serve with any static file server). The file is self-contained — `support.js` bootstraps React 18 from unpkg and mounts the component. No build step required.
For local serving (recommended, avoids file:// CORS issues with image-slot.js):
```
npx serve .
# or
python -m http.server 8080
```
## Architecture
This is a **Claude Design** prototype — a single-file component system where HTML template and JavaScript logic live together in `Sales App.dc.html`.
### Runtime (`support.js`)
- Generated/compiled Claude Design runtime — do not edit
- Loads React 18 from unpkg, provides `DCLogic` base class
- Template directives: `<sc-if value="{{expr}}">`, `<sc-for list="{{arr}}" as="item">`, `<x-import>` for external components
- `{{expr}}` interpolation binds template to values returned from `renderVals()`
### Main component (`Sales App.dc.html`)
The `<script type="text/x-dc" data-dc-script>` block contains a `class Component extends DCLogic` with:
- `state` — reactive state object (mutate via `this.setState(...)`)
- `renderVals()` — returns flat object of all values the template can reference
- Event handlers as class arrow functions
**Two top-level modes**, toggled by `state.mode`:
- `staff` — mobile phone mockup (412px wide), screens: `scan → login → form → history → historyDetail`
- `admin` — full-width desktop dashboard with date filter, summary cards, bar chart, and 3 table views (list / by employee / by store)
The admin top-bar toggle button is gated on `isAdminUser`. The login role-simulation panel is gated on `isDev` (auto-detected from `localhost`/`127.0.0.1`/empty hostname, or override `DEV_MODE` manually).
### External components
- **`image-slot.js`** — custom element `<image-slot>` for evidence photo upload. Persists drops to `.image-slots.state.json` sidecar. Used in the form screen via `<x-import component-from-global-scope="image-slot" from="./image-slot.js">`.
- **`android-frame.jsx`** — Android device frame components (not currently imported by the app).
### Mock data
All data lives in `state.allHistory` and `state.submissionsToday` arrays inside the component. `renderVals()` derives `adminFiltered`, `groupedByEmployee`, `groupedByStore`, `filteredHistory`, etc. from those arrays at render time. No backend yet.
## Key patterns
- To conditionally show UI: `<sc-if value="{{boolVal}}">...</sc-if>` where `boolVal` comes from `renderVals()`
- To iterate: `<sc-for list="{{arr}}" as="item" hint-placeholder-count="N">` — `hint-placeholder-count` controls skeleton count during streaming
- Inline styles are CSS strings resolved from `renderVals()` (e.g. `style="{{periodStyle}}"` where `periodStyle` is a full CSS string)
- Modals use `scrollY` state + `position:absolute; top:${scrollY}px` workaround because `position:fixed` doesn't compose with scrollable containers in this setup
## DEV_MODE
`DEV_MODE` is a class property auto-set from `location.hostname`. To force it on/off, change the line in the class:
```js
DEV_MODE = true;  // always show dev tools
DEV_MODE = false; // always hide dev tools
```

---

## Backend (Planned)
> ส่วนนี้สำหรับ Claude Code เมื่อเริ่มสร้าง backend — ปัจจุบัน app ยังใช้ mock data ใน state

### Stack
- Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · Alembic · aiomysql · Pydantic v2

### Project Structure (backend)
```
backend/
  app/
    models/         # SQLAlchemy ORM models
    schemas/        # Pydantic request/response schemas
    routers/        # FastAPI routers
    services/       # Business logic
    repositories/   # DB query layer
    core/
      config.py     # Settings (pydantic-settings)
      database.py   # AsyncEngine, AsyncSession
  database/
    migrations/     # Alembic versions
    sql/            # Raw DDL files
```

### DB Naming Convention
Column = **[entity][mod][Column]** camelCase — prefix บอก origin ตาราง

| Prefix | Table | ตัวอย่าง |
|--------|-------|---------|
| `s7` | mod7$_Store | s7Sid, s7Name, s7CreatedAt |
| `p7` | mod7$_Personnel | p7PID, p7Sid, p7Role, p7User |
| `t1` | mod1$_Transaction | t1TID, t1Sid, t1Pid, t1Shift |
| `f1` | mod1$_TxnFile | f1FID, f1TID, f1Path, f1MimeType |
| `l9` | mod9$_Logging | l9LID, l9Page, l9Component, l9SessionID |

### Table Names — contain `$`, always quote in raw SQL
```sql
`mod7$_Store`, `mod7$_Personnel`, `mod1$_Transaction`,
`mod1$_TxnFile`, `mod9$_Logging`
```
In SQLAlchemy: `__tablename__ = "mod7$_Store"` (Python string, no escaping needed)

### Relationships
```
mod7$_Store (s7Sid)
  ├─ 1:N  mod7$_Personnel  p7Sid → s7Sid
  ├─ 1:N  mod1$_Transaction t1Sid → s7Sid
  └─ 1:N  mod9$_Logging    l9Sid → s7Sid  (ON DELETE SET NULL)

mod7$_Personnel (p7PID)
  ├─ 1:N  mod1$_Transaction t1Pid → p7PID
  ├─ 1:N  mod1$_TxnFile    f1Pid → p7PID  (ON DELETE SET NULL)
  └─ 1:N  mod9$_Logging    l9Pid → p7PID  (ON DELETE SET NULL)

mod1$_Transaction (t1TID)
  └─ 1:N  mod1$_TxnFile   f1TID → t1TID  (ON DELETE CASCADE)
```

### Key Columns
- `t1Shift` ENUM('morning','afternoon','evening') — รอบเช้า/เย็น/ค่ำ
- `t1PayMethod` ENUM('cash','card','transfer','qr')
- `t1PayStatus` ENUM('pending','paid','refunded','void')
- `t1Sub/Disc/Tax/Total` DECIMAL(12,2) — ห้ามใช้ FLOAT สำหรับเงิน
- `f1Path` เก็บ path บน storage เท่านั้น ไม่เก็บ binary ใน DB
- `f1Tag` ENUM('receipt','slip','product','other')
- `l9Type` ENUM('info','warning','error','audit','pageview','click')
- `l9Page` — route ที่เปิด เช่น `/report/daily`
- `l9Component` — ชื่อปุ่ม เช่น `btn_report`, `btn_void`
- `l9SessionID` — UUID ต่อ 1 login session
- mod9$_Logging เป็น append-only ห้าม UPDATE/DELETE

### Coding Rules
- async/await ตลอด (AsyncSession)
- ไม่ expose `p7PwdHash` ใน response schema ใดๆ
- ใช้ `from decimal import Decimal` ไม่ใช้ float สำหรับเงิน
- ทุก action ที่ admin/staff ทำต้อง write ลง mod9$_Logging

### Frontend → Backend Migration Plan
เมื่อพร้อมต่อ API ให้แทนที่ mock data ใน `state.allHistory` / `state.submissionsToday`
ด้วย fetch call ไปยัง FastAPI endpoints ที่ตรงกัน:
- `GET /api/transactions` → `adminFiltered`
- `POST /api/transactions` → form screen submit
- `GET /api/transactions/{id}/files` → image-slot evidence photos