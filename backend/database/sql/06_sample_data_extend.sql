-- KlongthomSales — extend the sample data up to now
-- Run on a database loaded with 02/03. Continues the same deterministic pattern
-- (same stores, staff, shifts, amounts formula, ~5% missing, ~70% photos,
-- ~2/3 with expense) from the day after the latest report up to the current
-- Bangkok time; shifts whose submit time has not happened yet are skipped.
-- Safe to re-run: existing slots are never duplicated.
-- Reports older than 7 days are 'verified' by the admin; newer ones 'submitted'.
-- Photo rows are metadata only (no bytes), like the rows from 02.

SET XACT_ABORT ON;
SET NOCOUNT ON;

DECLARE @admin INT = (SELECT p7PID FROM [mod7$_Personnel] WHERE p7EmpCode = N'ADM001');
IF @admin IS NULL
    THROW 50060, N'Sample personnel not found — load 02_sample_data.sql first.', 1;

DECLARE @nowUtc DATETIME2(0) = SYSUTCDATETIME();
DECLARE @to     DATE = CAST(DATEADD(HOUR, 7, @nowUtc) AS DATE);          -- Bangkok today
DECLARE @from   DATE = DATEADD(DAY, 1, (SELECT MAX(t1Date) FROM [mod1$_Transaction]));
DECLARE @verifyUntil DATE = DATEADD(DAY, -7, @to);

IF @from IS NULL OR @from > @to
BEGIN
    SELECT 'nothing to add' AS result, @from AS [from], @to AS [to];
    RETURN;
END;

DECLARE @cover TABLE (code NVARCHAR(20), shift NVARCHAR(15), emp NVARCHAR(20));
INSERT INTO @cover VALUES
 (N'A1',N'afternoon',N'EMP003'), (N'A1',N'morning',N'EMP003'),
 (N'A2',N'afternoon',N'EMP002'), (N'A3',N'afternoon',N'EMP001'),
 (N'D1',N'afternoon',N'EMP004'), (N'D1',N'morning',N'EMP004'),
 (N'D1.1',N'afternoon',N'EMP004'), (N'D2',N'afternoon',N'EMP005'),
 (N'H1',N'afternoon',N'EMP006'), (N'H1',N'evening',N'EMP001'),
 (N'K3',N'afternoon',N'EMP007'), (N'K4',N'afternoon',N'EMP007'),
 (N'K8',N'afternoon',N'EMP008'), (N'K8',N'morning',N'EMP008'),
 (N'K9',N'afternoon',N'EMP009'), (N'SB',N'afternoon',N'EMP011'),
 (N'X1',N'afternoon',N'EMP010'), (N'X8',N'afternoon',N'EMP010'), (N'X8',N'evening',N'EMP002');

DECLARE @new TABLE (t1TID INT PRIMARY KEY);

BEGIN TRANSACTION;

;WITH days AS (
    SELECT @from AS d
    UNION ALL SELECT DATEADD(DAY, 1, d) FROM days WHERE d < @to
), slots AS (
    SELECT s.s7Sid, s.s7Code, s.s7QrVer, c.shift, p.p7PID, days.d,
           ABS(CAST(CAST(HASHBYTES('MD5', CONCAT(s.s7Code, '|', days.d, '|', c.shift)) AS BINARY(4)) AS INT) % 1000003) AS h
    FROM @cover c
    JOIN [mod7$_Store] s     ON s.s7Code = c.code AND s.s7Status = 1
    JOIN [mod7$_Personnel] p ON p.p7EmpCode = c.emp AND p.p7Status = 1
    CROSS JOIN days
), rows AS (
    SELECT *,
           DATEADD(MINUTE, (h % 40) + CASE shift WHEN 'morning' THEN 240 WHEN 'afternoon' THEN 690 ELSE 900 END,
                   CAST(d AS DATETIME2(0))) AS createdAt
    FROM slots
)
INSERT INTO [mod1$_Transaction]
    (t1TNo, t1Sid, t1Pid, t1Date, t1Shift, t1Cash, t1Transfer, t1Expense, t1Status, t1Note, t1QrVer,
     t1VerifiedBy, t1VerifiedAt, t1CreatedAt)
OUTPUT inserted.t1TID INTO @new
SELECT
    CONCAT(s7Code, '-', FORMAT(d, 'yyyyMMdd'), '-', CASE shift WHEN 'morning' THEN 'M' WHEN 'afternoon' THEN 'A' ELSE 'E' END),
    s7Sid, p7PID, d, shift,
    CAST(((CASE shift WHEN 'morning' THEN 1800 ELSE 3200 END) + (h % 3400)) / 100 * 100 AS DECIMAL(12,2)),
    CAST((400 + (h / 7) % 2800) / 100 * 100 AS DECIMAL(12,2)),
    CASE WHEN h % 3 <> 0 THEN (100 + h % 500) / 50 * 50 ELSE 0 END,
    CASE WHEN d <= @verifyUntil THEN N'verified' ELSE N'submitted' END,
    CASE h % 9 WHEN 0 THEN N'ลูกค้าโอนเกินมา 100 คืนเป็นเงินสดแล้ว' WHEN 1 THEN N'ฝนตก ปิดร้านเร็ว' END,
    s7QrVer,
    CASE WHEN d <= @verifyUntil THEN @admin END,
    CASE WHEN d <= @verifyUntil THEN DATEADD(HOUR, 27, CAST(d AS DATETIME2(0))) END,
    createdAt
FROM rows r
WHERE h % 20 <> 0                       -- ~5% missing reports
  AND createdAt <= @nowUtc              -- only shifts that have already happened
  AND NOT EXISTS (SELECT 1 FROM [mod1$_Transaction] t
                  WHERE t.t1Sid = r.s7Sid AND t.t1Date = r.d AND t.t1Shift = r.shift AND t.t1Status <> N'void')
OPTION (MAXRECURSION 400);

-- evidence photo metadata (~70%)
INSERT INTO [mod1$_TxnFile] (f1TID, f1Pid, f1FileName, f1Path, f1MimeType, f1Size, f1Sha256, f1Tag, f1CreatedAt)
SELECT t.t1TID, t.t1Pid,
       CONCAT('slip_', t.t1TNo, '.jpg'),
       CONCAT('evidence/', FORMAT(t.t1Date, 'yyyy/MM/dd'), '/', t.t1TNo, '-1.jpg'),
       N'image/jpeg',
       180000 + (t.t1TID * 7919) % 400000,
       CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT('sample-slip|', t.t1TNo)), 2),
       N'slip',
       t.t1CreatedAt
FROM [mod1$_Transaction] t JOIN @new n ON n.t1TID = t.t1TID
WHERE (t.t1TID * 37) % 10 < 7;

-- audit log: one login per staff per day, one create per report, verifies
INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9SessionID, l9Pid, l9Sid, l9NewVal, l9CreatedAt)
SELECT N'audit', N'auth', N'login', N'/login', N'btn_line_login',
       LOWER(CONVERT(CHAR(36), CAST(HASHBYTES('MD5', CONCAT(t.t1Pid, '|', t.t1Date)) AS UNIQUEIDENTIFIER))),
       t.t1Pid, MIN(t.t1Sid), N'{"method":"line"}', DATEADD(MINUTE, -3, MIN(t.t1CreatedAt))
FROM [mod1$_Transaction] t JOIN @new n ON n.t1TID = t.t1TID
GROUP BY t.t1Pid, t.t1Date;

INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9SessionID, l9Pid, l9Sid,
                             l9RefTable, l9RefID, l9NewVal, l9CreatedAt)
SELECT N'audit', N'transaction', N'create', N'/form', N'btn_submit',
       LOWER(CONVERT(CHAR(36), CAST(HASHBYTES('MD5', CONCAT(t.t1Pid, '|', t.t1Date)) AS UNIQUEIDENTIFIER))),
       t.t1Pid, t.t1Sid, N'mod1$_Transaction', t.t1TID,
       CONCAT('{"t1TNo":"', t.t1TNo, '","t1Cash":', t.t1Cash, ',"t1Transfer":', t.t1Transfer,
              ',"t1Expense":', t.t1Expense, ',"t1Status":"submitted"}'),
       t.t1CreatedAt
FROM [mod1$_Transaction] t JOIN @new n ON n.t1TID = t.t1TID;

INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9Pid, l9Sid,
                             l9RefTable, l9RefID, l9OldVal, l9NewVal, l9CreatedAt)
SELECT N'audit', N'transaction', N'verify', N'/admin', N'btn_verify', @admin, t.t1Sid,
       N'mod1$_Transaction', t.t1TID, N'{"t1Status":"submitted"}', N'{"t1Status":"verified"}', t.t1VerifiedAt
FROM [mod1$_Transaction] t JOIN @new n ON n.t1TID = t.t1TID
WHERE t.t1Status = N'verified';

COMMIT;

SELECT @from AS [from], @to AS [to], COUNT(*) AS added_reports FROM @new;
