-- KlongthomSales — DDL
-- SQL Server 2022
-- Run once on a fresh database

USE [KlongthomSales];
GO

CREATE TABLE [mod7$_Store] (
    s7Sid       INT IDENTITY(1,1) PRIMARY KEY,
    s7Code      NVARCHAR(20)  NOT NULL UNIQUE,
    s7Name      NVARCHAR(200) NOT NULL,
    s7Active    BIT           NOT NULL DEFAULT 1,
    s7CreatedAt DATETIME2     NOT NULL DEFAULT GETDATE(),
    s7UpdatedAt DATETIME2     NOT NULL DEFAULT GETDATE()
);
GO

CREATE TABLE [mod7$_Personnel] (
    p7PID       INT IDENTITY(1,1) PRIMARY KEY,
    p7Sid       INT           NOT NULL REFERENCES [mod7$_Store](s7Sid),
    p7Name      NVARCHAR(200) NOT NULL,
    p7Role      NVARCHAR(20)  NOT NULL DEFAULT 'staff'
                    CONSTRAINT ck_p7Role CHECK (p7Role IN ('staff','admin')),
    p7User      NVARCHAR(100) NULL,        -- LINE userId
    p7PwdHash   NVARCHAR(255) NULL,
    p7Active    BIT           NOT NULL DEFAULT 1,
    p7CreatedAt DATETIME2     NOT NULL DEFAULT GETDATE(),
    p7UpdatedAt DATETIME2     NOT NULL DEFAULT GETDATE()
);
GO

CREATE TABLE [mod1$_Transaction] (
    t1TID       INT IDENTITY(1,1) PRIMARY KEY,
    t1Sid       INT            NOT NULL REFERENCES [mod7$_Store](s7Sid),
    t1Pid       INT            NOT NULL REFERENCES [mod7$_Personnel](p7PID),
    t1Shift     NVARCHAR(20)   NOT NULL
                    CONSTRAINT ck_t1Shift CHECK (t1Shift IN ('morning','afternoon','evening')),
    t1PayMethod NVARCHAR(20)   NOT NULL
                    CONSTRAINT ck_t1PayMethod CHECK (t1PayMethod IN ('cash','card','transfer','qr')),
    t1PayStatus NVARCHAR(20)   NOT NULL DEFAULT 'paid'
                    CONSTRAINT ck_t1PayStatus CHECK (t1PayStatus IN ('pending','paid','refunded','void')),
    t1Sub       DECIMAL(12,2)  NOT NULL DEFAULT 0,
    t1Disc      DECIMAL(12,2)  NOT NULL DEFAULT 0,
    t1Tax       DECIMAL(12,2)  NOT NULL DEFAULT 0,
    t1Total     DECIMAL(12,2)  NOT NULL,
    t1Note      NVARCHAR(500)  NULL,
    t1CreatedAt DATETIME2      NOT NULL DEFAULT GETDATE(),
    t1UpdatedAt DATETIME2      NOT NULL DEFAULT GETDATE()
);
GO

CREATE TABLE [mod1$_TxnFile] (
    f1FID       INT IDENTITY(1,1) PRIMARY KEY,
    f1TID       INT            NOT NULL REFERENCES [mod1$_Transaction](t1TID) ON DELETE CASCADE,
    f1Pid       INT            NULL REFERENCES [mod7$_Personnel](p7PID) ON DELETE SET NULL,
    f1Path      NVARCHAR(500)  NOT NULL,
    f1MimeType  NVARCHAR(100)  NULL,
    f1Tag       NVARCHAR(20)   NOT NULL DEFAULT 'receipt'
                    CONSTRAINT ck_f1Tag CHECK (f1Tag IN ('receipt','slip','product','other')),
    f1CreatedAt DATETIME2      NOT NULL DEFAULT GETDATE()
);
GO

CREATE TABLE [mod9$_Logging] (
    l9LID       INT IDENTITY(1,1) PRIMARY KEY,
    l9Type      NVARCHAR(20)   NOT NULL
                    CONSTRAINT ck_l9Type CHECK (l9Type IN ('info','warning','error','audit','pageview','click')),
    l9Page      NVARCHAR(200)  NULL,
    l9Component NVARCHAR(100)  NULL,
    l9SessionID NVARCHAR(100)  NULL,
    l9Sid       INT            NULL REFERENCES [mod7$_Store](s7Sid) ON DELETE SET NULL,
    l9Pid       INT            NULL REFERENCES [mod7$_Personnel](p7PID) ON DELETE SET NULL,
    l9Detail    NVARCHAR(2000) NULL,
    l9CreatedAt DATETIME2      NOT NULL DEFAULT GETDATE()
);
GO
