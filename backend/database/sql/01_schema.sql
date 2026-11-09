-- KlongthomSales — schema
-- Azure SQL / SQL Server 2022 · database [klongthom-sales]
-- Design notes: docs/database-design.md
--
-- Builds every table, index and the log trigger on an empty database.
-- Refuses to run if any of the tables already exist (never drops anything).
-- All timestamps are UTC (SYSUTCDATETIME()).
-- Business date (t1Date) is the Asia/Bangkok calendar date chosen in the app.

SET XACT_ABORT ON;
GO

-- ── guard ─────────────────────────────────────────────────────────────
IF OBJECT_ID(N'[mod7$_Store]') IS NOT NULL OR OBJECT_ID(N'[mod7$_Personnel]') IS NOT NULL
   OR OBJECT_ID(N'[mod1$_Transaction]') IS NOT NULL OR OBJECT_ID(N'[mod1$_TxnFile]') IS NOT NULL
   OR OBJECT_ID(N'[mod9$_Logging]') IS NOT NULL
    THROW 50001, N'Schema already exists — this script only builds an empty database.', 1;
GO

-- ── mod7$_Store ───────────────────────────────────────────────────────
-- One row per shop. s7Code is what the QR code carries (?shop=A3&sig=...).
-- s7QrVer is mixed into the HMAC so a leaked QR can be revoked by bumping it;
-- the HMAC key itself lives in app settings, never in the DB.
CREATE TABLE [mod7$_Store] (
    s7Sid        INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_s7 PRIMARY KEY,
    s7Code       NVARCHAR(20)  NOT NULL CONSTRAINT uq_s7Code UNIQUE,
    s7Name       NVARCHAR(100) NOT NULL,
    s7Type       NVARCHAR(20)  NOT NULL CONSTRAINT df_s7Type DEFAULT N'retail',
    s7Addr       NVARCHAR(500) NULL,
    s7Phone      NVARCHAR(20)  NULL,
    s7TaxID      NVARCHAR(20)  NULL,
    s7QrVer      INT           NOT NULL CONSTRAINT df_s7QrVer DEFAULT 1,
    s7Status     BIT           NOT NULL CONSTRAINT df_s7Status DEFAULT 1,
    s7CreatedAt  DATETIME2(0)  NOT NULL CONSTRAINT df_s7CreatedAt DEFAULT SYSUTCDATETIME(),
    s7UpdatedAt  DATETIME2(0)  NULL
);
GO

-- ── mod7$_Personnel ───────────────────────────────────────────────────
-- Staff log in with LINE (p7LineUID); admins may also have a password.
-- p7Sid is an optional home store: staff collect at any store they scan.
CREATE TABLE [mod7$_Personnel] (
    p7PID        INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_p7 PRIMARY KEY,
    p7Sid        INT           NULL CONSTRAINT fk_p7_s7 REFERENCES [mod7$_Store](s7Sid),
    p7EmpCode    NVARCHAR(20)  NOT NULL CONSTRAINT uq_p7EmpCode UNIQUE,
    p7LineUID    NVARCHAR(64)  NULL,
    p7User       NVARCHAR(50)  NULL,
    p7PwdHash    NVARCHAR(255) NULL,
    p7FName      NVARCHAR(50)  NOT NULL,
    p7LName      NVARCHAR(50)  NOT NULL CONSTRAINT df_p7LName DEFAULT N'',
    p7Nick       NVARCHAR(50)  NULL,
    p7Role       NVARCHAR(20)  NOT NULL CONSTRAINT df_p7Role DEFAULT N'staff'
                     CONSTRAINT ck_p7Role CHECK (p7Role IN (N'staff', N'admin')),
    p7Phone      NVARCHAR(20)  NULL,
    p7Email      NVARCHAR(100) NULL,
    p7Status     BIT           NOT NULL CONSTRAINT df_p7Status DEFAULT 1,
    p7LastLogin  DATETIME2(0)  NULL,
    p7CreatedAt  DATETIME2(0)  NOT NULL CONSTRAINT df_p7CreatedAt DEFAULT SYSUTCDATETIME(),
    p7UpdatedAt  DATETIME2(0)  NULL,
    -- must be able to log in somehow
    CONSTRAINT ck_p7Login CHECK (p7LineUID IS NOT NULL OR (p7User IS NOT NULL AND p7PwdHash IS NOT NULL))
);
GO
CREATE UNIQUE INDEX uq_p7LineUID ON [mod7$_Personnel](p7LineUID) WHERE p7LineUID IS NOT NULL;
CREATE UNIQUE INDEX uq_p7User    ON [mod7$_Personnel](p7User)    WHERE p7User    IS NOT NULL;
GO

-- ── mod1$_Transaction ─────────────────────────────────────────────────
-- One row = one shift submission: a staff member's cash + transfer total
-- for one store on one business date and shift (the staff form screen).
-- Shift mapping: เช้า=morning · เย็น=afternoon · ค่ำ=evening
CREATE TABLE [mod1$_Transaction] (
    t1TID        INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_t1 PRIMARY KEY,
    t1TNo        NVARCHAR(30)  NOT NULL CONSTRAINT uq_t1TNo UNIQUE,   -- e.g. A3-20261108-A-0001
    t1Sid        INT           NOT NULL CONSTRAINT fk_t1_s7 REFERENCES [mod7$_Store](s7Sid),
    t1Pid        INT           NOT NULL CONSTRAINT fk_t1_p7 REFERENCES [mod7$_Personnel](p7PID),
    t1Date       DATE          NOT NULL,
    t1Shift      NVARCHAR(15)  NOT NULL
                     CONSTRAINT ck_t1Shift CHECK (t1Shift IN (N'morning', N'afternoon', N'evening')),
    t1Cash       DECIMAL(12,2) NOT NULL CONSTRAINT df_t1Cash     DEFAULT 0
                     CONSTRAINT ck_t1Cash CHECK (t1Cash >= 0),
    t1Transfer   DECIMAL(12,2) NOT NULL CONSTRAINT df_t1Transfer DEFAULT 0
                     CONSTRAINT ck_t1Transfer CHECK (t1Transfer >= 0),
    t1Expense    DECIMAL(12,2) NOT NULL CONSTRAINT df_t1Expense  DEFAULT 0
                     CONSTRAINT ck_t1Expense CHECK (t1Expense >= 0),     -- (หัก) ค่าใช้จ่าย
    t1Total      AS (t1Cash + t1Transfer - t1Expense) PERSISTED,         -- ยอดสุทธิ (net)
    t1Status     NVARCHAR(15)  NOT NULL CONSTRAINT df_t1Status DEFAULT N'submitted'
                     CONSTRAINT ck_t1Status CHECK (t1Status IN (N'submitted', N'verified', N'void')),
    t1Note       NVARCHAR(500) NULL,
    t1QrVer      INT           NULL,          -- QR version verified at submit time
    t1VerifiedBy INT           NULL CONSTRAINT fk_t1_verify REFERENCES [mod7$_Personnel](p7PID),
    t1VerifiedAt DATETIME2(0)  NULL,
    t1VoidBy     INT           NULL CONSTRAINT fk_t1_void   REFERENCES [mod7$_Personnel](p7PID),
    t1VoidAt     DATETIME2(0)  NULL,
    t1VoidReason NVARCHAR(200) NULL,
    t1CreatedAt  DATETIME2(0)  NOT NULL CONSTRAINT df_t1CreatedAt DEFAULT SYSUTCDATETIME(),
    t1UpdatedAt  DATETIME2(0)  NULL,
    CONSTRAINT ck_t1Void CHECK (
        (t1Status =  N'void' AND t1VoidBy IS NOT NULL AND t1VoidAt IS NOT NULL AND t1VoidReason IS NOT NULL)
     OR (t1Status <> N'void' AND t1VoidBy IS NULL     AND t1VoidAt IS NULL)
    ),
    CONSTRAINT ck_t1Verify CHECK (t1Status <> N'verified' OR (t1VerifiedBy IS NOT NULL AND t1VerifiedAt IS NOT NULL))
);
GO
-- No double submission: one live row per staff · store · date · shift.
-- A voided row frees the slot so staff can resubmit a correction.
CREATE UNIQUE INDEX uq_t1Slot ON [mod1$_Transaction](t1Sid, t1Date, t1Shift, t1Pid)
    WHERE t1Status <> N'void';
-- Admin dashboard: date range → group by store / employee
CREATE INDEX ix_t1Date      ON [mod1$_Transaction](t1Date, t1Sid)  INCLUDE (t1Pid, t1Shift, t1Cash, t1Transfer, t1Expense, t1Status);
-- Staff history screen: my submissions in a date range
CREATE INDEX ix_t1Pid_Date  ON [mod1$_Transaction](t1Pid, t1Date)  INCLUDE (t1Sid, t1Shift, t1Cash, t1Transfer, t1Expense, t1Status);
GO

-- ── mod1$_TxnFile ─────────────────────────────────────────────────────
-- Evidence photos. Binary lives in object storage; only the path is stored.
CREATE TABLE [mod1$_TxnFile] (
    f1FID        INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_f1 PRIMARY KEY,
    f1TID        INT           NOT NULL CONSTRAINT fk_f1_t1 REFERENCES [mod1$_Transaction](t1TID) ON DELETE CASCADE,
    f1Pid        INT           NULL     CONSTRAINT fk_f1_p7 REFERENCES [mod7$_Personnel](p7PID),
    f1FileName   NVARCHAR(255) NOT NULL,
    f1Path       NVARCHAR(500) NOT NULL CONSTRAINT uq_f1Path UNIQUE,
    f1MimeType   NVARCHAR(100) NOT NULL
                     CONSTRAINT ck_f1Mime CHECK (f1MimeType IN (N'image/jpeg', N'image/png', N'image/webp', N'image/heic', N'application/pdf')),
    f1Size       INT           NULL CONSTRAINT ck_f1Size CHECK (f1Size IS NULL OR f1Size BETWEEN 1 AND 10485760),
    f1Sha256     CHAR(64)      NULL,          -- detect the same slip uploaded twice
    f1Tag        NVARCHAR(20)  NOT NULL CONSTRAINT df_f1Tag DEFAULT N'slip'
                     CONSTRAINT ck_f1Tag CHECK (f1Tag IN (N'receipt', N'slip', N'product', N'other')),
    f1CreatedAt  DATETIME2(0)  NOT NULL CONSTRAINT df_f1CreatedAt DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_f1TID    ON [mod1$_TxnFile](f1TID);
CREATE INDEX ix_f1Sha256 ON [mod1$_TxnFile](f1Sha256) WHERE f1Sha256 IS NOT NULL;
GO

-- ── mod9$_Logging ─────────────────────────────────────────────────────
-- Append-only audit + activity log. No FKs on purpose: a log row must
-- outlive whatever it refers to, and inserts must never fail on a FK.
CREATE TABLE [mod9$_Logging] (
    l9LID        BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT pk_l9 PRIMARY KEY,
    l9Type       NVARCHAR(20)  NOT NULL
                     CONSTRAINT ck_l9Type CHECK (l9Type IN (N'info', N'warning', N'error', N'audit', N'pageview', N'click')),
    l9Module     NVARCHAR(20)  NOT NULL,      -- auth · transaction · personnel · store
    l9Action     NVARCHAR(100) NOT NULL,      -- create · update · void · login · ...
    l9Page       NVARCHAR(200) NULL,
    l9Component  NVARCHAR(100) NULL,
    l9SessionID  NVARCHAR(64)  NULL,
    l9Pid        INT           NULL,
    l9Sid        INT           NULL,
    l9RefTable   NVARCHAR(50)  NULL,
    l9RefID      INT           NULL,
    l9OldVal     NVARCHAR(MAX) NULL CONSTRAINT ck_l9OldJson CHECK (l9OldVal IS NULL OR ISJSON(l9OldVal) = 1),
    l9NewVal     NVARCHAR(MAX) NULL CONSTRAINT ck_l9NewJson CHECK (l9NewVal IS NULL OR ISJSON(l9NewVal) = 1),
    l9IP         NVARCHAR(45)  NULL,
    l9UA         NVARCHAR(255) NULL,
    l9CreatedAt  DATETIME2(3)  NOT NULL CONSTRAINT df_l9CreatedAt DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX ix_l9CreatedAt ON [mod9$_Logging](l9CreatedAt);
CREATE INDEX ix_l9Ref       ON [mod9$_Logging](l9RefTable, l9RefID) WHERE l9RefID IS NOT NULL;
CREATE INDEX ix_l9Pid       ON [mod9$_Logging](l9Pid, l9CreatedAt)  WHERE l9Pid IS NOT NULL;
GO
CREATE TRIGGER tr_l9_AppendOnly ON [mod9$_Logging]
INSTEAD OF UPDATE, DELETE
AS
BEGIN
    THROW 50009, N'mod9$_Logging is append-only', 1;
END;
GO
