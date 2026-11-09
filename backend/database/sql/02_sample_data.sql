-- KlongthomSales — sample data for schema v2
-- Runs only on an empty schema (after 01_schema.sql). Deterministic:
-- amounts come from a hash of store/date/shift, so every run gives the same data.
--
-- What you get:
--   14 stores (the prototype's STORES list), 11 staff + 1 admin (LINE logins)
--   21 business days 2026-10-18 … 2026-11-07, ~5% of slots skipped (missing reports)
--   shifts: every store เย็น (afternoon); D1/K8/A1 also เช้า (morning); H1/X8 also ค่ำ (evening)
--   reports up to 2026-10-31 are 'verified' by the admin; later ones 'submitted'
--   one voided report (typo 54,000) + its corrected resubmission — A3 · 2026-11-05 · afternoon
--   ~70% of reports have an evidence slip photo; audit log rows for logins, creates, verifies, the void

SET XACT_ABORT ON;
SET NOCOUNT ON;

IF EXISTS (SELECT 1 FROM [mod7$_Store]) OR EXISTS (SELECT 1 FROM [mod1$_Transaction])
    THROW 50002, N'Tables are not empty — sample data loads only into a fresh schema.', 1;

BEGIN TRANSACTION;

-- ── stores ────────────────────────────────────────────────────────────
INSERT INTO [mod7$_Store] (s7Code, s7Name, s7Type) VALUES
 (N'A1', N'กอล์ฟ', N'retail'), (N'A2', N'นิ่ม (เพลง)', N'retail'), (N'A3', N'ต่อ', N'retail'),
 (N'D1', N'กร', N'retail'), (N'D1.1', N'กร แก้ว ผ้าปูโต๊ะ', N'retail'), (N'D2', N'จัด', N'retail'),
 (N'H1', N'บุญมี', N'retail'), (N'K3', N'เจน', N'retail'), (N'K4', N'อ้อ', N'retail'),
 (N'K8', N'เสก', N'retail'), (N'K9', N'น้ำหอม', N'retail'), (N'SB', N'ป้าตุ้ย', N'retail'),
 (N'X1', N'หนุ่ย', N'retail'), (N'X8', N'นนท์', N'retail');

-- ── personnel (LINE_TEST_* match the DEV login IDs) ───────────────────
INSERT INTO [mod7$_Personnel] (p7Sid, p7EmpCode, p7LineUID, p7FName, p7LName, p7Nick, p7Role)
SELECT s.s7Sid, v.code, v.uid, v.fname, v.lname, v.nick, v.role
FROM (VALUES
 (N'EMP001', N'LINE_TEST_001',   N'สมชาย',     N'ใจดี',      N'ชาย',   N'staff', N'A3'),
 (N'EMP002', N'LINE_TEST_002',   N'วันดี',      N'ศรีสุข',     N'ดี',    N'staff', N'A2'),
 (N'EMP003', N'LINE_TEST_003',   N'คำแพง',     N'สายบัว',    N'แพง',  N'staff', N'A1'),
 (N'EMP004', N'LINE_TEST_004',   N'อองมิน',     N'',          NULL,    N'staff', N'D1'),
 (N'EMP005', N'LINE_TEST_005',   N'จันทร์เพ็ญ',  N'ทองดี',     N'เพ็ญ',  N'staff', N'D2'),
 (N'EMP006', N'LINE_TEST_006',   N'มยุรี',       N'แก้วมณี',    N'ยุ',    N'staff', N'H1'),
 (N'EMP007', N'LINE_TEST_007',   N'ทองสุข',     N'แสงจันทร์',  N'สุข',   N'staff', N'K3'),
 (N'EMP008', N'LINE_TEST_008',   N'บัวลอย',     N'คำมี',       N'บัว',   N'staff', N'K8'),
 (N'EMP009', N'LINE_TEST_009',   N'สมหญิง',     N'ใจงาม',     N'หญิง',  N'staff', N'K9'),
 (N'EMP010', N'LINE_TEST_010',   N'คำสิงห์',     N'วงศ์ษา',     N'สิงห์',  N'staff', N'X1'),
 (N'EMP011', N'LINE_TEST_011',   N'ประยูร',     N'มั่นคง',      N'ยูร',   N'staff', N'SB'),
 (N'ADM001', N'LINE_TEST_ADMIN', N'อรทัย',      N'จัดการ',     N'อร',    N'admin', NULL)
) v(code, uid, fname, lname, nick, role, home)
LEFT JOIN [mod7$_Store] s ON s.s7Code = v.home;

DECLARE @admin INT = (SELECT p7PID FROM [mod7$_Personnel] WHERE p7EmpCode = N'ADM001');

-- who collects where: home-store staff, plus cover for the 3 stores with no home staff
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

-- ── shift reports ─────────────────────────────────────────────────────
;WITH days AS (
    SELECT CAST('2026-10-18' AS DATE) AS d
    UNION ALL SELECT DATEADD(DAY, 1, d) FROM days WHERE d < '2026-11-07'
), slots AS (
    SELECT s.s7Sid, s.s7Code, c.shift, p.p7PID, days.d,
           ABS(CAST(CAST(HASHBYTES('MD5', CONCAT(s.s7Code, '|', days.d, '|', c.shift)) AS BINARY(4)) AS INT) % 1000003) AS h
    FROM @cover c
    JOIN [mod7$_Store] s     ON s.s7Code = c.code
    JOIN [mod7$_Personnel] p ON p.p7EmpCode = c.emp
    CROSS JOIN days
)
INSERT INTO [mod1$_Transaction]
    (t1TNo, t1Sid, t1Pid, t1Date, t1Shift, t1Cash, t1Transfer, t1Status, t1Note, t1QrVer,
     t1VerifiedBy, t1VerifiedAt, t1CreatedAt)
SELECT
    CONCAT(s7Code, '-', FORMAT(d, 'yyyyMMdd'), '-', CASE shift WHEN 'morning' THEN 'M' WHEN 'afternoon' THEN 'A' ELSE 'E' END),
    s7Sid, p7PID, d, shift,
    -- morning shifts are smaller; round to 100 baht like real counts
    CAST(((CASE shift WHEN 'morning' THEN 1800 ELSE 3200 END) + (h % 3400)) / 100 * 100 AS DECIMAL(12,2)),
    CAST((400 + (h / 7) % 2800) / 100 * 100 AS DECIMAL(12,2)),
    CASE WHEN d <= '2026-10-31' THEN N'verified' ELSE N'submitted' END,
    CASE h % 9 WHEN 0 THEN N'ลูกค้าโอนเกินมา 100 คืนเป็นเงินสดแล้ว' WHEN 1 THEN N'ฝนตก ปิดร้านเร็ว' END,
    1,
    CASE WHEN d <= '2026-10-31' THEN @admin END,
    CASE WHEN d <= '2026-10-31' THEN DATEADD(HOUR, 27, CAST(d AS DATETIME2(0))) END,
    -- UTC submit time: morning 11:00, afternoon 18:30, evening 22:00 Bangkok (UTC+7)
    DATEADD(MINUTE, (h % 40) + CASE shift WHEN 'morning' THEN 240 WHEN 'afternoon' THEN 690 ELSE 900 END,
            CAST(d AS DATETIME2(0)))
FROM slots
WHERE h % 20 <> 0                                                    -- ~5% missing reports
  AND NOT (s7Code = N'A3' AND d = '2026-11-05' AND shift = N'afternoon')  -- added below
OPTION (MAXRECURSION 100);

-- void + correction: A3 · 2026-11-05 · afternoon (typed 54000 instead of 5400)
DECLARE @a3 INT = (SELECT s7Sid FROM [mod7$_Store] WHERE s7Code = N'A3');
DECLARE @emp1 INT = (SELECT p7PID FROM [mod7$_Personnel] WHERE p7EmpCode = N'EMP001');
INSERT INTO [mod1$_Transaction]
    (t1TNo, t1Sid, t1Pid, t1Date, t1Shift, t1Cash, t1Transfer, t1Status, t1Note, t1QrVer,
     t1VoidBy, t1VoidAt, t1VoidReason, t1CreatedAt, t1UpdatedAt)
VALUES (N'A3-20261105-A-V1', @a3, @emp1, '2026-11-05', N'afternoon', 54000, 2200, N'void', NULL, 1,
        @admin, '2026-11-05T12:05:00', N'พิมพ์เงินสดผิด (54000 → 5400)', '2026-11-05T11:41:00', '2026-11-05T12:05:00');
INSERT INTO [mod1$_Transaction]
    (t1TNo, t1Sid, t1Pid, t1Date, t1Shift, t1Cash, t1Transfer, t1Status, t1Note, t1QrVer, t1CreatedAt)
VALUES (N'A3-20261105-A', @a3, @emp1, '2026-11-05', N'afternoon', 5400, 2200, N'submitted',
        N'ส่งใหม่แทนรายการที่ยกเลิก', 1, '2026-11-05T12:09:00');

-- ── evidence photos (~70%) ────────────────────────────────────────────
INSERT INTO [mod1$_TxnFile] (f1TID, f1Pid, f1FileName, f1Path, f1MimeType, f1Size, f1Sha256, f1Tag, f1CreatedAt)
SELECT t.t1TID, t.t1Pid,
       CONCAT('slip_', t.t1TNo, '.jpg'),
       CONCAT('evidence/', FORMAT(t.t1Date, 'yyyy/MM/dd'), '/', t.t1TNo, '-1.jpg'),
       N'image/jpeg',
       180000 + (t.t1TID * 7919) % 400000,
       CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT('sample-slip|', t.t1TNo)), 2),
       N'slip',
       t.t1CreatedAt
FROM [mod1$_Transaction] t
WHERE (t.t1TID * 37) % 10 < 7;

-- ── audit / activity log ──────────────────────────────────────────────
-- staff login once per day they submitted
INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9SessionID, l9Pid, l9Sid, l9NewVal, l9CreatedAt)
SELECT N'audit', N'auth', N'login', N'/login', N'btn_line_login',
       LOWER(CONVERT(CHAR(36), CAST(HASHBYTES('MD5', CONCAT(t.t1Pid, '|', t.t1Date)) AS UNIQUEIDENTIFIER))),
       t.t1Pid, MIN(t.t1Sid), N'{"method":"line"}', DATEADD(MINUTE, -3, MIN(t.t1CreatedAt))
FROM [mod1$_Transaction] t
GROUP BY t.t1Pid, t.t1Date;

-- one create row per report, same session as that day's login
INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9SessionID, l9Pid, l9Sid,
                             l9RefTable, l9RefID, l9NewVal, l9CreatedAt)
SELECT N'audit', N'transaction', N'create', N'/form', N'btn_submit',
       LOWER(CONVERT(CHAR(36), CAST(HASHBYTES('MD5', CONCAT(t.t1Pid, '|', t.t1Date)) AS UNIQUEIDENTIFIER))),
       t.t1Pid, t.t1Sid, N'mod1$_Transaction', t.t1TID,
       CONCAT('{"t1TNo":"', t.t1TNo, '","t1Cash":', t.t1Cash, ',"t1Transfer":', t.t1Transfer, ',"t1Status":"submitted"}'),
       t.t1CreatedAt
FROM [mod1$_Transaction] t;

-- admin verifies
INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9Pid, l9Sid,
                             l9RefTable, l9RefID, l9OldVal, l9NewVal, l9CreatedAt)
SELECT N'audit', N'transaction', N'verify', N'/admin', N'btn_verify', @admin, t.t1Sid,
       N'mod1$_Transaction', t.t1TID, N'{"t1Status":"submitted"}', N'{"t1Status":"verified"}', t.t1VerifiedAt
FROM [mod1$_Transaction] t
WHERE t.t1Status = N'verified';

-- the void
INSERT INTO [mod9$_Logging] (l9Type, l9Module, l9Action, l9Page, l9Component, l9Pid, l9Sid,
                             l9RefTable, l9RefID, l9OldVal, l9NewVal, l9CreatedAt)
SELECT N'audit', N'transaction', N'void', N'/admin', N'btn_void', @admin, t.t1Sid,
       N'mod1$_Transaction', t.t1TID, N'{"t1Status":"submitted"}',
       CONCAT('{"t1Status":"void","t1VoidReason":"', t.t1VoidReason, '"}'), t.t1VoidAt
FROM [mod1$_Transaction] t
WHERE t.t1Status = N'void';

COMMIT;

SELECT 'stores' AS what, COUNT(*) AS n FROM [mod7$_Store]
UNION ALL SELECT 'personnel', COUNT(*) FROM [mod7$_Personnel]
UNION ALL SELECT 'transactions', COUNT(*) FROM [mod1$_Transaction]
UNION ALL SELECT 'files', COUNT(*) FROM [mod1$_TxnFile]
UNION ALL SELECT 'logs', COUNT(*) FROM [mod9$_Logging];
